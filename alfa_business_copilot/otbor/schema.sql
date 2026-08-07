
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS document_type (
    document_type_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name                          TEXT NOT NULL UNIQUE,
    description                   TEXT
);

CREATE TABLE IF NOT EXISTS client (
    client_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name                  TEXT NOT NULL,
    birth_date                  DATE NOT NULL,
    entity_type                 TEXT NOT NULL,
    inn                          TEXT,
    industry_code               TEXT,
    business_registered_at      DATE,
    region_code                  TEXT,
    is_student                   INTEGER NOT NULL DEFAULT 0,
    created_at                   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                   TEXT NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT chk_client_entity_type
        CHECK (entity_type IN ('ИП', 'ООО', 'самозанятый', 'физлицо')),
    CONSTRAINT chk_client_is_student
        CHECK (is_student IN (0, 1))
);

CREATE TABLE IF NOT EXISTS raw_program_source (
    source_row_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id                   TEXT NOT NULL UNIQUE,          -- строковый id из CSV (fsi-start-1) — не ключ БД, а внешний код
    source_type                    TEXT NOT NULL DEFAULT 'csv_manual',
    name_raw                       TEXT NOT NULL,
    organizer_raw                  TEXT,
    level_raw                       TEXT,
    type_raw                        TEXT,
    audience_text                  TEXT,
    age_text                        TEXT,
    amount_min_raw                 INTEGER,
    amount_max_raw                 INTEGER,
    cofinancing_text               TEXT,
    window_text                    TEXT,
    status_text                    TEXT,
    is_permanent_intake_raw       TEXT,
    submission_channel_raw        TEXT,
    key_conditions_text            TEXT,
    stop_factors_text              TEXT,
    source_url                      TEXT,
    verified_label                  TEXT,
    note_text                       TEXT,
    imported_at                     TEXT NOT NULL DEFAULT (datetime('now')),
    snapshot_date                   DATE NOT NULL,

    CONSTRAINT chk_raw_source_type
        CHECK (source_type IN ('csv_manual', 'api', 'parsing', 'synthetic'))
);

CREATE TABLE IF NOT EXISTS support_program (
    program_id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_source_id                  INTEGER UNIQUE,
    name                            TEXT NOT NULL,
    organizer                      TEXT,
    level                           TEXT NOT NULL,
    type                            TEXT NOT NULL,
    amount_min                     INTEGER,
    amount_max                     INTEGER,
    cofinancing_required           INTEGER NOT NULL DEFAULT 0,
    age_min                         INTEGER,
    age_max                         INTEGER,
    age_parse_confidence           TEXT NOT NULL DEFAULT 'unparsed',
    entity_type_allowed            TEXT,
    industry_allowed                TEXT,
    business_age_min_years         REAL,
    is_permanent_intake            INTEGER NOT NULL DEFAULT 0,
    deadline_date                   DATE,
    is_open                         INTEGER NOT NULL DEFAULT 0,
    status_checked_at              DATE,
    submission_channel             TEXT,
    stop_factors_text              TEXT,
    notes_text                     TEXT,
    last_verified_at               DATE,
    created_at                      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                      TEXT NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT fk_support_program_raw_source
        FOREIGN KEY (raw_source_id) REFERENCES raw_program_source (source_row_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_support_program_level
        CHECK (level IN ('federal', 'regional', 'mixed')),
    CONSTRAINT chk_support_program_type
        CHECK (type IN ('grant', 'credit', 'guarantee', 'leasing', 'subsidy', 'nonfinancial')),
    CONSTRAINT chk_support_program_cofinancing
        CHECK (cofinancing_required IN (0, 1)),
    CONSTRAINT chk_support_program_age_confidence
        CHECK (age_parse_confidence IN ('parsed', 'manual_review', 'unparsed')),
    CONSTRAINT chk_support_program_entity_type_json
        CHECK (entity_type_allowed IS NULL OR json_valid(entity_type_allowed)),
    CONSTRAINT chk_support_program_industry_json
        CHECK (industry_allowed IS NULL OR json_valid(industry_allowed)),
    CONSTRAINT chk_support_program_permanent_intake
        CHECK (is_permanent_intake IN (0, 1)),
    CONSTRAINT chk_support_program_is_open
        CHECK (is_open IN (0, 1)),
    CONSTRAINT chk_support_program_channel
        CHECK (submission_channel IN ('bank', 'gosuslugi', 'fund_platform', 'regional_office', 'other')),
    CONSTRAINT chk_support_program_amount_range
        CHECK (amount_min IS NULL OR amount_max IS NULL OR amount_min <= amount_max),
    CONSTRAINT chk_support_program_age_range
        CHECK (age_min IS NULL OR age_max IS NULL OR age_min <= age_max)
);

CREATE TABLE IF NOT EXISTS required_document (
    document_id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id                     INTEGER NOT NULL,
    document_type_id               INTEGER NOT NULL,
    is_generatable_by_bank        INTEGER NOT NULL DEFAULT 0,
    description                    TEXT,
    source                          TEXT NOT NULL DEFAULT 'manual_entry',

    CONSTRAINT fk_required_document_program
        FOREIGN KEY (program_id) REFERENCES support_program (program_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_required_document_document_type
        FOREIGN KEY (document_type_id) REFERENCES document_type (document_type_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_required_document_generatable
        CHECK (is_generatable_by_bank IN (0, 1)),
    CONSTRAINT chk_required_document_source
        CHECK (source IN ('manual_entry', 'parsed_from_source'))
);

CREATE TABLE IF NOT EXISTS client_document (
    document_id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id                      INTEGER NOT NULL,
    document_type_id               INTEGER NOT NULL,
    status                          TEXT NOT NULL DEFAULT 'missing',
    updated_at                      TEXT NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT fk_client_document_client
        FOREIGN KEY (client_id) REFERENCES client (client_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_client_document_document_type
        FOREIGN KEY (document_type_id) REFERENCES document_type (document_type_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_client_document_status
        CHECK (status IN ('missing', 'uploaded', 'verified'))
);

CREATE TABLE IF NOT EXISTS eligibility_check (
    check_id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id                       INTEGER NOT NULL,
    program_id                      INTEGER NOT NULL,
    is_eligible                     INTEGER NOT NULL,
    reason_text                     TEXT,
    checked_at                      TEXT NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT fk_eligibility_check_client
        FOREIGN KEY (client_id) REFERENCES client (client_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_eligibility_check_program
        FOREIGN KEY (program_id) REFERENCES support_program (program_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_eligibility_check_is_eligible
        CHECK (is_eligible IN (0, 1)),
    CONSTRAINT uq_eligibility_check
        UNIQUE (client_id, program_id, checked_at)
);

CREATE TABLE IF NOT EXISTS application (
    application_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id                       INTEGER NOT NULL,
    program_id                      INTEGER NOT NULL,
    status                           TEXT NOT NULL DEFAULT 'draft',
    draft_text                      TEXT,
    submission_channel              TEXT,
    created_at                       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                       TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_at                     TEXT,
    decision_at                      TEXT,

    CONSTRAINT fk_application_client
        FOREIGN KEY (client_id) REFERENCES client (client_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_application_program
        FOREIGN KEY (program_id) REFERENCES support_program (program_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_application_status
        CHECK (status IN ('draft', 'ready', 'sent', 'approved', 'rejected'))
);


CREATE INDEX IF NOT EXISTS idx_support_program_raw_source   ON support_program(raw_source_id);
CREATE INDEX IF NOT EXISTS idx_support_program_is_open      ON support_program(is_open);
CREATE INDEX IF NOT EXISTS idx_support_program_level_type   ON support_program(level, type);

CREATE INDEX IF NOT EXISTS idx_required_document_program    ON required_document(program_id);
CREATE INDEX IF NOT EXISTS idx_required_document_doc_type   ON required_document(document_type_id);

CREATE INDEX IF NOT EXISTS idx_client_document_client       ON client_document(client_id);
CREATE INDEX IF NOT EXISTS idx_client_document_doc_type     ON client_document(document_type_id);

CREATE INDEX IF NOT EXISTS idx_eligibility_check_client     ON eligibility_check(client_id);
CREATE INDEX IF NOT EXISTS idx_eligibility_check_program    ON eligibility_check(program_id);

CREATE INDEX IF NOT EXISTS idx_application_client           ON application(client_id);
CREATE INDEX IF NOT EXISTS idx_application_program          ON application(program_id);
CREATE INDEX IF NOT EXISTS idx_application_status           ON application(status);

-- ============================================================
-- Триггеры — автообновление updated_at
-- ============================================================
CREATE TRIGGER IF NOT EXISTS trg_client_updated_at
AFTER UPDATE ON client
BEGIN
    UPDATE client SET updated_at = datetime('now') WHERE client_id = NEW.client_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_support_program_updated_at
AFTER UPDATE ON support_program
BEGIN
    UPDATE support_program SET updated_at = datetime('now') WHERE program_id = NEW.program_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_application_updated_at
AFTER UPDATE ON application
BEGIN
    UPDATE application SET updated_at = datetime('now') WHERE application_id = NEW.application_id;
END;
