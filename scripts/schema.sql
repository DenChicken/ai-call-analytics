CREATE TABLE IF NOT EXISTS sources (
    id          SMALLSERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    cursor      TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agents (
    id            BIGSERIAL PRIMARY KEY,
    source_id     SMALLINT NOT NULL REFERENCES sources(id),
    external_id   TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    first_name    TEXT,
    last_name     TEXT,
    second_name   TEXT,
    email         TEXT,
    profile_link  TEXT,
    synced_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS calls (
    id                BIGSERIAL PRIMARY KEY,
    source_id         SMALLINT NOT NULL REFERENCES sources(id),
    external_id       TEXT NOT NULL,
    agent_id          BIGINT REFERENCES agents(id),
    started_at        TIMESTAMPTZ NOT NULL,
    duration_seconds  INTEGER NOT NULL,
    direction         TEXT NOT NULL,
    client_number     TEXT,
    subject           TEXT,
    crm_link          TEXT,
    audio_path        TEXT NOT NULL,
    raw               JSONB NOT NULL DEFAULT '{}'::jsonb,
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS calls_agent_started_idx ON calls (agent_id, started_at DESC);
CREATE INDEX IF NOT EXISTS calls_started_idx ON calls (started_at DESC);

CREATE TABLE IF NOT EXISTS processing_jobs (
    call_id     BIGINT PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,
    status      TEXT NOT NULL DEFAULT 'pending',
    attempts    SMALLINT NOT NULL DEFAULT 0,
    error_code  TEXT,
    last_error  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT processing_jobs_status_check CHECK (
        status IN ('pending', 'transcribed', 'done', 'failed')
    ),
    CONSTRAINT processing_jobs_error_code_check CHECK (
        error_code IS NULL OR error_code IN (
            'audio_missing', 'asr_empty', 'transcript_empty', 'llm_truncated',
            'llm_prompt_too_long', 'llm_invalid_output', 'no_criteria',
            'no_call_types', 'unknown'
        )
    )
);

CREATE INDEX IF NOT EXISTS processing_jobs_status_idx ON processing_jobs (status, updated_at);

CREATE TABLE IF NOT EXISTS criteria (
    code         TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    description  TEXT NOT NULL,
    position     SMALLINT NOT NULL,
    enabled      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS call_types (
    code         TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    description  TEXT NOT NULL,
    position     SMALLINT NOT NULL,
    enabled      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS analyses (
    call_id             BIGINT PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,
    call_type           TEXT NOT NULL REFERENCES call_types(code),
    summary             TEXT NOT NULL,
    strengths           JSONB NOT NULL DEFAULT '[]'::jsonb,
    weaknesses          JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendations     JSONB NOT NULL DEFAULT '[]'::jsonb,
    asr_model           TEXT NOT NULL,
    analysis_model      TEXT NOT NULL,
    prompt_label        TEXT NOT NULL,
    processing_seconds  INTEGER NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS analyses_created_idx ON analyses (created_at DESC);

CREATE TABLE IF NOT EXISTS asr_results (
    call_id     BIGINT PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,
    model       TEXT NOT NULL,
    language    TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    plain       TEXT NOT NULL,
    raw         JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS criterion_scores (
    call_id         BIGINT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    criterion_code  TEXT NOT NULL REFERENCES criteria(code),
    score           SMALLINT NOT NULL,
    PRIMARY KEY (call_id, criterion_code),
    CONSTRAINT criterion_scores_score_check CHECK (score IN (0, 1))
);

CREATE INDEX IF NOT EXISTS criterion_scores_code_idx ON criterion_scores (criterion_code, call_id);

CREATE TABLE IF NOT EXISTS users (
    id             SMALLSERIAL PRIMARY KEY,
    login          TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     SMALLINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS sessions_expires_idx ON sessions (expires_at);
