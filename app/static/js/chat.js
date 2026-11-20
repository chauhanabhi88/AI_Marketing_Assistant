/* chat.js — multi-session ChatGPT-style interface */

class ChatApp {
  constructor() {
    this.messagesEl   = document.getElementById('chatMessages');
    this.inputEl      = document.getElementById('messageInput');
    this.sendBtn      = document.getElementById('sendBtn');
    this.charCountEl  = document.getElementById('charCount');
    this.sessionList  = document.getElementById('sessionList');
    this.titleEl      = document.getElementById('activeChatTitle');
    this.deleteChatBtn = document.getElementById('deleteChatBtn');
    this.welcomeState = document.getElementById('welcomeState');

    this.currentSessionId = null;
    this.streaming = false;

    this._bindEvents();

    // Auto-load the most recent session if any exists
    const first = this.sessionList.querySelector('.session-item');
    if (first) this._selectSession(parseInt(first.dataset.id));
  }

  // ── Events ──────────────────────────────────────────────────────────────────

  _bindEvents() {
    // Send
    this.sendBtn.addEventListener('click', () => this._send());
    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._send(); }
    });

    // Char counter + auto-grow textarea
    this.inputEl.addEventListener('input', () => {
      this.inputEl.style.height = 'auto';
      this.inputEl.style.height = Math.min(this.inputEl.scrollHeight, 180) + 'px';
      this.charCountEl.textContent = `${this.inputEl.value.length} / 4000`;
    });

    // New chat
    document.getElementById('newChatBtn').addEventListener('click', () => this._newChat());

    // Delete active chat
    this.deleteChatBtn.addEventListener('click', () => this._deleteCurrentSession());

    // Session clicks (delegated)
    this.sessionList.addEventListener('click', (e) => {
      const deleteBtn = e.target.closest('.session-delete-btn');
      if (deleteBtn) {
        e.stopPropagation();
        this._deleteSession(parseInt(deleteBtn.dataset.id));
        return;
      }
      const item = e.target.closest('.session-item');
      if (item) this._selectSession(parseInt(item.dataset.id));
    });

    // Double-click session title → rename
    this.sessionList.addEventListener('dblclick', (e) => {
      const item = e.target.closest('.session-item');
      if (item) this._openRenameModal(parseInt(item.dataset.id));
    });

    // Rename modal save
    document.getElementById('renameSaveBtn').addEventListener('click', () => this._saveRename());
    document.getElementById('renameInput').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this._saveRename();
    });

    // Sidebar toggle
    document.getElementById('sidebarToggle').addEventListener('click', () => this._toggleSidebar());
    document.getElementById('closeSidebar')?.addEventListener('click', () => this._closeSidebar());
    document.getElementById('sidebarBackdrop').addEventListener('click', () => this._closeSidebar());
  }

  // ── Session management ───────────────────────────────────────────────────────

  async _newChat() {
    try {
      const res = await fetch('/chat/sessions/new', { method: 'POST' });
      if (!res.ok) throw new Error('Could not create session');
      const session = await res.json();
      this._prependSessionItem(session);
      this._selectSession(session.id, true);   // true = skip fetch (empty session)
    } catch (err) {
      this._showToast('Failed to create new chat', 'danger');
    }
  }

  async _selectSession(sessionId, empty = false) {
    this.currentSessionId = sessionId;
    this._highlightSession(sessionId);
    this.deleteChatBtn.classList.remove('d-none');

    if (empty) {
      this._clearMessages();
      this._setTitle('New Chat');
      this._enableInput();
      return;
    }

    this._clearMessages();
    this._showLoadingSpinner();

    try {
      const res = await fetch(`/chat/sessions/${sessionId}/messages`);
      if (!res.ok) throw new Error('Could not load messages');
      const data = await res.json();

      this._removeLoadingSpinner();
      this._setTitle(data.session.title);
      this._updateSessionTitle(sessionId, data.session.title);

      if (data.messages.length === 0) {
        this._showWelcome();
      } else {
        this._hideWelcome();
        data.messages.forEach(m => this._appendExchangePair(m.message, m.response, m.created_at));
        this._scrollBottom();
      }
      this._enableInput();
    } catch (err) {
      this._removeLoadingSpinner();
      this._showToast('Failed to load messages', 'danger');
    }
  }

  async _deleteSession(sessionId) {
    if (!confirm('Delete this chat and all its messages?')) return;
    try {
      await fetch(`/chat/sessions/${sessionId}`, { method: 'DELETE' });
      document.querySelector(`.session-item[data-id="${sessionId}"]`)?.remove();

      if (sessionId === this.currentSessionId) {
        this.currentSessionId = null;
        this.deleteChatBtn.classList.add('d-none');
        this._clearMessages();
        this._showWelcome();
        this._setTitle('Select or start a chat');
        this._disableInput();
      }

      this._checkEmptySidebar();
    } catch {
      this._showToast('Failed to delete chat', 'danger');
    }
  }

  _deleteCurrentSession() {
    if (this.currentSessionId) this._deleteSession(this.currentSessionId);
  }

  // ── Rename ───────────────────────────────────────────────────────────────────

  _renameTargetId = null;
  _renameModal = null;

  _openRenameModal(sessionId) {
    const item = this.sessionList.querySelector(`.session-item[data-id="${sessionId}"]`);
    if (!item) return;
    this._renameTargetId = sessionId;
    document.getElementById('renameInput').value =
      item.querySelector('.session-item-title').textContent.trim();
    this._renameModal = new bootstrap.Modal(document.getElementById('renameModal'));
    this._renameModal.show();
    setTimeout(() => document.getElementById('renameInput').select(), 200);
  }

  async _saveRename() {
    const title = document.getElementById('renameInput').value.trim();
    if (!title || !this._renameTargetId) return;

    try {
      const res = await fetch(`/chat/sessions/${this._renameTargetId}/title`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      this._updateSessionTitle(this._renameTargetId, data.title);
      if (this._renameTargetId === this.currentSessionId) this._setTitle(data.title);
      this._renameModal?.hide();
    } catch {
      this._showToast('Failed to rename', 'danger');
    }
  }

  // ── Messaging ────────────────────────────────────────────────────────────────

  async _send() {
    if (this.streaming) return;
    const message = this.inputEl.value.trim();
    if (!message) return;

    // Auto-create a session if none active
    if (!this.currentSessionId) {
      await this._newChat();
      if (!this.currentSessionId) return;
    }

    this._hideWelcome();
    this.streaming = true;
    this.inputEl.value = '';
    this.inputEl.style.height = 'auto';
    this.charCountEl.textContent = '0 / 4000';
    this._setInputDisabled(true);

    this._appendUserBubble(message);
    const aiBubble = this._appendAIBubble();
    let fullText = '';
    let finalTitle = null;

    try {
      const resp = await fetch('/chat/send/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: this.currentSessionId }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      aiBubble.innerHTML = '';  // clear typing dots

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const d = JSON.parse(line.slice(6));
            if (d.error) throw new Error(d.error);
            if (d.session_id && !this.currentSessionId) this.currentSessionId = d.session_id;
            if (d.content) {
              fullText += d.content;
              aiBubble.innerHTML = this._formatMarkdown(fullText);
              this._scrollBottom();
            }
            if (d.done && d.title) finalTitle = d.title;
          } catch (parseErr) {
            if (parseErr.message.includes('JSON')) continue;
            throw parseErr;
          }
        }
      }
    } catch (err) {
      aiBubble.innerHTML = `<span class="text-danger"><i class="bi bi-exclamation-triangle me-1"></i>${this._esc(err.message)}</span>`;
    } finally {
      this.streaming = false;
      this._setInputDisabled(false);
      this.inputEl.focus();

      // Update session title if it changed (first message auto-title)
      if (finalTitle) {
        this._updateSessionTitle(this.currentSessionId, finalTitle);
        this._setTitle(finalTitle);
      }
    }
  }

  // ── DOM helpers ──────────────────────────────────────────────────────────────

  _appendExchangePair(userMsg, aiMsg, createdAt) {
    const time = createdAt ? new Date(createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    // User bubble
    const userRow = document.createElement('div');
    userRow.className = 'chat-row chat-row-user';
    userRow.innerHTML = `
      <div class="chat-bubble user-bubble">${this._esc(userMsg)}</div>
      <div class="chat-meta">${time}</div>`;
    this.messagesEl.appendChild(userRow);
    // AI bubble
    const aiRow = document.createElement('div');
    aiRow.className = 'chat-row chat-row-ai';
    aiRow.innerHTML = `
      <div class="chat-ai-avatar flex-shrink-0"><i class="bi bi-robot"></i></div>
      <div class="chat-bubble ai-bubble markdown-content">${this._formatMarkdown(aiMsg)}</div>`;
    this.messagesEl.appendChild(aiRow);
  }

  _appendUserBubble(text) {
    const row = document.createElement('div');
    row.className = 'chat-row chat-row-user';
    row.innerHTML = `
      <div class="chat-bubble user-bubble">${this._esc(text)}</div>
      <div class="chat-meta">${this._timeStr()}</div>`;
    this.messagesEl.appendChild(row);
    this._scrollBottom();
  }

  _appendAIBubble() {
    const row = document.createElement('div');
    row.className = 'chat-row chat-row-ai';
    row.innerHTML = `
      <div class="chat-ai-avatar flex-shrink-0"><i class="bi bi-robot"></i></div>
      <div class="chat-bubble ai-bubble markdown-content" id="ai-bubble-live">
        <div class="typing-dot"><span></span><span></span><span></span></div>
      </div>`;
    this.messagesEl.appendChild(row);
    this._scrollBottom();
    return row.querySelector('#ai-bubble-live');
  }

  _prependSessionItem(session) {
    const empty = this.sessionList.querySelector('.session-empty-hint');
    if (empty) empty.remove();

    const el = document.createElement('div');
    el.className = 'session-item';
    el.dataset.id = session.id;
    el.title = session.title;
    el.innerHTML = `
      <i class="bi bi-chat-left-text session-item-icon"></i>
      <span class="session-item-title">${this._esc(session.title)}</span>
      <button class="session-delete-btn btn btn-icon" data-id="${session.id}" title="Delete">
        <i class="bi bi-trash3"></i>
      </button>`;
    this.sessionList.prepend(el);
  }

  _highlightSession(sessionId) {
    this.sessionList.querySelectorAll('.session-item').forEach(el => {
      el.classList.toggle('active', parseInt(el.dataset.id) === sessionId);
    });
  }

  _updateSessionTitle(sessionId, title) {
    const el = this.sessionList.querySelector(`.session-item[data-id="${sessionId}"] .session-item-title`);
    if (el) el.textContent = title;
    const item = this.sessionList.querySelector(`.session-item[data-id="${sessionId}"]`);
    if (item) item.title = title;
  }

  _clearMessages() {
    // Keep welcome state, remove chat rows
    this.messagesEl.querySelectorAll('.chat-row, .loading-spinner-row').forEach(el => el.remove());
  }

  _showLoadingSpinner() {
    this._hideWelcome();
    const el = document.createElement('div');
    el.className = 'loading-spinner-row text-center py-5 text-muted';
    el.innerHTML = '<div class="spinner-border spinner-border-sm"></div> Loading…';
    this.messagesEl.appendChild(el);
  }

  _removeLoadingSpinner() {
    this.messagesEl.querySelector('.loading-spinner-row')?.remove();
  }

  _showWelcome()  { this.welcomeState.style.display = ''; }
  _hideWelcome()  { this.welcomeState.style.display = 'none'; }
  _setTitle(t)    { this.titleEl.textContent = t; }
  _scrollBottom() { this.messagesEl.scrollTop = this.messagesEl.scrollHeight; }
  _timeStr()      { return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }

  _enableInput()  { this.inputEl.disabled = false; this.sendBtn.disabled = false; this.inputEl.focus(); }
  _disableInput() { this.inputEl.disabled = true;  this.sendBtn.disabled = true; }

  _setInputDisabled(disabled) {
    this.inputEl.disabled = disabled;
    this.sendBtn.disabled = disabled;
    this.sendBtn.innerHTML = disabled
      ? '<span class="spinner-border spinner-border-sm"></span>'
      : '<i class="bi bi-send-fill"></i>';
  }

  _checkEmptySidebar() {
    if (!this.sessionList.querySelector('.session-item')) {
      const hint = document.createElement('div');
      hint.className = 'session-empty-hint';
      hint.innerHTML = 'No chats yet.<br>Click <strong>New Chat</strong> to begin.';
      this.sessionList.appendChild(hint);
    }
  }

  // ── Sidebar toggle ────────────────────────────────────────────────────────────

  _toggleSidebar() {
    const sidebar = document.getElementById('sessionSidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    const isMobile = window.innerWidth < 768;
    if (isMobile) {
      sidebar.classList.toggle('open');
      backdrop.classList.toggle('show');
    } else {
      sidebar.classList.toggle('collapsed');
    }
  }

  _closeSidebar() {
    document.getElementById('sessionSidebar').classList.remove('open');
    document.getElementById('sidebarBackdrop').classList.remove('show');
  }

  // ── Markdown + utilities ──────────────────────────────────────────────────────

  _esc(str) {
    const d = document.createElement('div');
    d.textContent = String(str);
    return d.innerHTML;
  }

  _formatMarkdown(text) {
    let o = this._esc(text);
    o = o.replace(/```[\w]*\n?([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    o = o.replace(/`([^`]+)`/g, '<code>$1</code>');
    o = o.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    o = o.replace(/__(.*?)__/g, '<strong>$1</strong>');
    o = o.replace(/\*(.*?)\*/g, '<em>$1</em>');
    o = o.replace(/^#{3} (.+)$/gm, '<h3>$1</h3>');
    o = o.replace(/^#{2} (.+)$/gm, '<h2>$1</h2>');
    o = o.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    o = o.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
    o = o.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
    o = o.replace(/(<li>[\s\S]*?<\/li>\n?)+/g, m => `<ul>${m}</ul>`);
    o = o.replace(/\n/g, '<br>');
    o = o.replace(/<pre><code>([\s\S]*?)<\/code><\/pre>/g,
      (_, c) => `<pre><code>${c.replace(/<br>/g, '\n')}</code></pre>`);
    o = o.replace(/<ul>([\s\S]*?)<\/ul>/g,
      (_, c) => `<ul>${c.replace(/<br>/g, '')}</ul>`);
    return o;
  }

  // ── Toast ─────────────────────────────────────────────────────────────────────

  _showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer') || (() => {
      const c = document.createElement('div');
      c.id = 'toastContainer';
      c.style.cssText = 'position:fixed;bottom:1rem;right:1rem;z-index:9999';
      document.body.appendChild(c);
      return c;
    })();
    const t = document.createElement('div');
    t.className = `toast align-items-center text-bg-${type} border-0 show mb-2`;
    t.innerHTML = `<div class="d-flex"><div class="toast-body">${this._esc(message)}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
    container.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }
}

// ── Suggestion prompt helper ──────────────────────────────────────────────────
function useSuggestion(btn) {
  const prompt = btn.querySelector('.sug-sub').textContent.trim();
  const input = document.getElementById('messageInput');
  input.value = prompt;
  input.dispatchEvent(new Event('input'));
  input.focus();
}

document.addEventListener('DOMContentLoaded', () => { window._chat = new ChatApp(); });
