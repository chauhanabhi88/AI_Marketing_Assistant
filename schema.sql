-- AI Marketing Strategy Chat Application — MySQL Schema
-- Run this manually if you prefer not to use SQLAlchemy auto-creation.

CREATE DATABASE IF NOT EXISTS ai_marketing_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ai_marketing_db;

-- ── Company users ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS company_users (
    id           INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    name         VARCHAR(100)    NOT NULL,
    email        VARCHAR(150)    NOT NULL,
    password     VARCHAR(255)    NOT NULL,
    company_name VARCHAR(150)    NOT NULL,
    created_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_company_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Agents ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    id         INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    company_id INT UNSIGNED    NOT NULL,
    name       VARCHAR(100)    NOT NULL,
    email      VARCHAR(150)    NOT NULL,
    password   VARCHAR(255)    NOT NULL,
    created_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_agent_email (email),
    KEY idx_agents_company_id (company_id),
    CONSTRAINT fk_agents_company
        FOREIGN KEY (company_id) REFERENCES company_users (id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Conversations ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id         INT UNSIGNED              NOT NULL AUTO_INCREMENT,
    user_type  ENUM('company', 'agent')  NOT NULL,
    user_id    INT UNSIGNED              NOT NULL,
    message    TEXT                      NOT NULL,
    response   TEXT                      NOT NULL,
    created_at DATETIME                  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_conversations_user (user_type, user_id),
    KEY idx_conversations_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
