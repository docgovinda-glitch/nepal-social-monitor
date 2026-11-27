-- Multi-user authentication, admin approval workflow, and per-user Green API assignments

CREATE TABLE IF NOT EXISTS app_users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    approved_at TIMESTAMP WITH TIME ZONE,
    approved_by INTEGER
);

CREATE INDEX IF NOT EXISTS idx_app_users_status ON app_users (status);

CREATE TABLE IF NOT EXISTS user_greenapi_configs (
    user_id INTEGER PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
    api_url TEXT NOT NULL DEFAULT '',
    id_instance TEXT NOT NULL DEFAULT '',
    token_instance_enc TEXT NOT NULL DEFAULT '',
    sending_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by INTEGER
);

ALTER TABLE whatsapp_sent_log ADD COLUMN IF NOT EXISTS sent_by_user_id INTEGER;
ALTER TABLE whatsapp_sent_log ADD COLUMN IF NOT EXISTS sent_by_username TEXT DEFAULT '';
