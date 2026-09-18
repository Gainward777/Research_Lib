INSERT OR IGNORE INTO library_sections(
    id, domain, key, title, read_policy, status
)
VALUES (
    'sec_research_quarantine',
    'research',
    '_quarantine',
    'Unclassified materials quarantine',
    'restricted',
    'active'
);

CREATE TABLE section_backfill_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'running', 'completed', 'failed')
    ),
    report_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO section_backfill_state(id, status)
VALUES (1, 'pending');
