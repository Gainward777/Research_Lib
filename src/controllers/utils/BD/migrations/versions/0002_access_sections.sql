CREATE TABLE library_sections (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL CHECK (domain IN ('memento', 'research')),
    key TEXT NOT NULL,
    title TEXT NOT NULL,
    read_policy TEXT NOT NULL CHECK (
        read_policy IN ('public', 'authenticated', 'restricted')
    ),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain, key)
);

INSERT INTO library_sections(id, domain, key, title, read_policy)
VALUES
    ('sec_research_main', 'research', 'main', 'Main research library', 'authenticated'),
    ('sec_memento_unassigned', 'memento', '_unassigned', 'Unassigned Memento', 'restricted');

CREATE TABLE access_tokens (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    public_prefix TEXT NOT NULL UNIQUE,
    token_hash TEXT NOT NULL UNIQUE,
    subject_type TEXT NOT NULL CHECK (
        subject_type IN ('developer', 'agent', 'ci', 'telegram', 'service')
    ),
    expires_at TEXT,
    revoked_at TEXT,
    last_used_at TEXT,
    created_by_token_id TEXT REFERENCES access_tokens(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE token_grants (
    token_id TEXT NOT NULL REFERENCES access_tokens(id) ON DELETE CASCADE,
    section_id TEXT REFERENCES library_sections(id) ON DELETE CASCADE,
    permission TEXT NOT NULL CHECK (
        permission IN ('read', 'publish', 'admin', 'system_admin')
    ),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(token_id, section_id, permission),
    CHECK (
        (permission = 'system_admin' AND section_id IS NULL)
        OR
        (permission <> 'system_admin' AND section_id IS NOT NULL)
    )
);

CREATE TABLE auth_audit_events (
    id TEXT PRIMARY KEY,
    actor_token_id TEXT REFERENCES access_tokens(id),
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    section_id TEXT REFERENCES library_sections(id),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE library_items ADD COLUMN section_id TEXT REFERENCES library_sections(id);
UPDATE library_items SET section_id = 'sec_research_main' WHERE section_id IS NULL;

ALTER TABLE uploads ADD COLUMN section_id TEXT REFERENCES library_sections(id);
UPDATE uploads SET section_id = 'sec_research_main' WHERE section_id IS NULL;

ALTER TABLE ingest_jobs ADD COLUMN section_id TEXT REFERENCES library_sections(id);
UPDATE ingest_jobs
SET section_id = COALESCE(
    (SELECT section_id FROM library_items WHERE library_items.id = ingest_jobs.item_id),
    'sec_research_main'
)
WHERE section_id IS NULL;

ALTER TABLE idempotency_receipts RENAME TO idempotency_receipts_legacy;

CREATE TABLE idempotency_receipts (
    key TEXT NOT NULL,
    section_id TEXT NOT NULL REFERENCES library_sections(id),
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    response_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(key, section_id)
);

INSERT INTO idempotency_receipts(
    key, section_id, payload_hash, status, response_json, created_at, updated_at
)
SELECT
    key, 'sec_research_main', payload_hash, status, response_json, created_at, updated_at
FROM idempotency_receipts_legacy;

DROP TABLE idempotency_receipts_legacy;

CREATE INDEX idx_library_items_section ON library_items(section_id);
CREATE INDEX idx_uploads_section ON uploads(section_id);
CREATE INDEX idx_ingest_jobs_section ON ingest_jobs(section_id);
CREATE INDEX idx_token_grants_section ON token_grants(section_id, permission);
CREATE UNIQUE INDEX idx_token_grants_system_admin
ON token_grants(token_id, permission) WHERE section_id IS NULL;
CREATE INDEX idx_access_tokens_active ON access_tokens(public_prefix, revoked_at, expires_at);

CREATE TRIGGER require_library_item_section
BEFORE INSERT ON library_items
WHEN NEW.section_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'library_items.section_id is required');
END;

CREATE TRIGGER require_upload_section
BEFORE INSERT ON uploads
WHEN NEW.section_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'uploads.section_id is required');
END;

CREATE TRIGGER require_ingest_job_section
BEFORE INSERT ON ingest_jobs
WHEN NEW.section_id IS NULL
BEGIN
    SELECT RAISE(ABORT, 'ingest_jobs.section_id is required');
END;
