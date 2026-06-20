-- Users table
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,                -- bcrypt hash
    role        TEXT NOT NULL DEFAULT 'user', -- enum: user, admin
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Projects table
CREATE TABLE projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    owner_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- API keys table (one‑to‑many: project → api_key)
CREATE TABLE api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    key_hash    TEXT NOT NULL,                -- SHA‑256 hash of the raw key
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ,                   -- nullable (no expiry = never)
    revoked     BOOLEAN NOT NULL DEFAULT FALSE
);

-- Daily quota tracking (per project)
CREATE TABLE usage_quota (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    day         DATE NOT NULL,                -- UTC day
    token_count BIGINT NOT NULL DEFAULT 0,
    UNIQUE (project_id, day)
);

-- Indexes for fast look‑ups
CREATE INDEX idx_users_email      ON users(email);
CREATE INDEX idx_projects_owner   ON projects(owner_id);
CREATE INDEX idx_api_keys_proj    ON api_keys(project_id);
CREATE INDEX idx_usage_quota_proj ON usage_quota(project_id, day);
