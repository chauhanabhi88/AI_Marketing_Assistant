-- Migration v2: Add chat_sessions table and link conversations
-- Run ONCE against your existing database.
-- The chat_sessions table is created automatically by SQLAlchemy on startup,
-- so you only need to run the ALTER TABLE below for the existing conversations table.

-- Step 1: (Auto-created by SQLAlchemy on next startup — shown here for reference)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id           INT UNSIGNED              NOT NULL AUTO_INCREMENT,
    user_type    ENUM('company', 'agent')  NOT NULL,
    user_id      INT UNSIGNED              NOT NULL,
    title        VARCHAR(255)              NOT NULL DEFAULT 'New Chat',
    created_at   DATETIME                  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME                  NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_sessions_user    (user_type, user_id),
    KEY idx_sessions_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Step 2: Add session_id to existing conversations table
ALTER TABLE conversations
    ADD COLUMN session_id INT UNSIGNED DEFAULT NULL AFTER id,
    ADD KEY idx_conversations_session (session_id),
    ADD CONSTRAINT fk_conversations_session
        FOREIGN KEY (session_id) REFERENCES chat_sessions (id)
        ON DELETE CASCADE;
