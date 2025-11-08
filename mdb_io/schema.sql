PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ===============================================================================================
-- Cages: unchanged (simple & clean)
CREATE TABLE IF NOT EXISTS cages (
    cage_id TEXT PRIMARY KEY,
    room TEXT NOT NULL,
    rack TEXT,
    created_at DATETIME DEFAULT (datetime('now'))
);

-- ===============================================================================================
CREATE TABLE IF NOT EXISTS mice (
    id TEXT PRIMARY KEY NOT NULL CHECK (length(id) > 0),
    type TEXT NOT NULL CHECK (type IN ('breeding', 'experiment')),
    
    sex TEXT NOT NULL CHECK (sex IN ('M', 'F')),
    strain TEXT NOT NULL DEFAULT 'C57BL/6J',
    genotype TEXT NOT NULL DEFAULT 'wt',
    birthDate DATE NOT NULL,
    death_date DATE,
    cause_of_death TEXT,
    
    cage_id TEXT NOT NULL REFERENCES cages(cage_id),
    markings TEXT,
    notes TEXT,
    
    -- Breeder info merged in
    is_breeder BOOLEAN NOT NULL DEFAULT 0,
    set_date DATE DEFAULT (date('now')),
    last_litter_date DATE,
    num_litters INTEGER DEFAULT 0,
    breeder_status TEXT DEFAULT 'active' 
        CHECK (breeder_status IN ('active', 'retired', 'pregnant')),
    
    age INTEGER GENERATED ALWAYS AS (
        CAST(julianday(IFNULL(death_date, 'now')) - julianday(birthDate) AS INTEGER)
    ) STORED,
    days_since_last_litter INTEGER GENERATED ALWAYS AS (
        CAST(julianday('now') - julianday(IFNULL(last_litter_date, set_date)) AS INTEGER)
    ) STORED,

    created_at DATETIME DEFAULT (datetime('now')),
    updated_at DATETIME DEFAULT (datetime('now'))
);

-- Trigger for updated_at
CREATE TRIGGER IF NOT EXISTS tr_mice_updated_at
AFTER UPDATE ON mice
BEGIN
    UPDATE mice SET updated_at = datetime('now') WHERE id = OLD.id;
END;

-- ===============================================================================================
CREATE TABLE IF NOT EXISTS experiments (
    experiment_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mouse_id TEXT NOT NULL REFERENCES mice(id) ON DELETE CASCADE,
    experiment_id TEXT NOT NULL,  -- e.g., 'MWM-2025'
    cohort TEXT,
    protocol TEXT,
    start_date DATE NOT NULL,
    end_date DATE,
    outcome TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT (datetime('now'))
);

-- ===============================================================================================
CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_run_id INTEGER NOT NULL REFERENCES experiments(experiment_run_id) ON DELETE CASCADE,
    session_date DATE NOT NULL DEFAULT (date('now')),
    task TEXT NOT NULL,
    duration_sec INTEGER,
    outcome TEXT,
    data_file TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT (datetime('now'))
);

-- ===============================================================================================
CREATE TABLE IF NOT EXISTS session_participants (
    session_id INTEGER NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    mouse_id TEXT NOT NULL REFERENCES mice(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'subject' CHECK (role IN ('subject', 'stimulus', 'observer')),
    PRIMARY KEY (session_id, mouse_id)
);

CREATE TRIGGER IF NOT EXISTS tr_sp_insert_check
BEFORE INSERT ON session_participants
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'mouse_id not enrolled in the session''s experiment')
    WHERE NOT EXISTS (
        SELECT 1
        FROM experiments e
        JOIN sessions s ON e.experiment_run_id = s.experiment_run_id
        WHERE e.mouse_id = NEW.mouse_id
          AND s.session_id = NEW.session_id
    );
END;

CREATE TRIGGER IF NOT EXISTS tr_sp_update_check
BEFORE UPDATE ON session_participants
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'mouse_id not enrolled in the session''s experiment')
    WHERE NOT EXISTS (
        SELECT 1
        FROM experiments e
        JOIN sessions s ON e.experiment_run_id = s.experiment_run_id
        WHERE e.mouse_id = NEW.mouse_id
          AND s.session_id = NEW.session_id
    );
END;

-- ===============================================================================================
CREATE TABLE IF NOT EXISTS mouse_experiment_summary (
    mouse_id TEXT PRIMARY KEY REFERENCES mice(id) ON DELETE CASCADE,
    total_experiments INTEGER DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    last_experiment_date DATE,
    last_session_date DATE
);

CREATE TRIGGER IF NOT EXISTS tr_experiments_upsert_summary
AFTER INSERT ON experiments
BEGIN
    INSERT INTO mouse_experiment_summary (mouse_id, total_experiments, last_experiment_date)
    VALUES (NEW.mouse_id, 1, NEW.start_date)
    ON CONFLICT(mouse_id) DO UPDATE SET
        total_experiments = total_experiments + 1,
        last_experiment_date = MAX(last_experiment_date, NEW.start_date);
END;

CREATE TRIGGER IF NOT EXISTS tr_experiments_delete_summary
AFTER DELETE ON experiments
BEGIN
    UPDATE mouse_experiment_summary
    SET 
        total_experiments = MAX(0, total_experiments - 1),
        last_experiment_date = (
            SELECT MAX(start_date) FROM experiments WHERE mouse_id = OLD.mouse_id
        )
    WHERE mouse_id = OLD.mouse_id;
END;

CREATE TRIGGER IF NOT EXISTS tr_sp_insert_summary
AFTER INSERT ON session_participants
BEGIN
    INSERT INTO mouse_experiment_summary (mouse_id, total_sessions, last_session_date)
    VALUES (NEW.mouse_id, 1, (SELECT session_date FROM sessions WHERE session_id = NEW.session_id))
    ON CONFLICT(mouse_id) DO UPDATE SET
        total_sessions = total_sessions + 1,
        last_session_date = MAX(last_session_date, (SELECT session_date FROM sessions WHERE session_id = NEW.session_id));
END;

CREATE TRIGGER IF NOT EXISTS tr_sp_delete_summary
AFTER DELETE ON session_participants
BEGIN
    UPDATE mouse_experiment_summary
    SET 
        total_sessions = MAX(0, total_sessions - 1),
        last_session_date = (
            SELECT MAX(s.session_date)
            FROM session_participants sp
            JOIN sessions s ON sp.session_id = s.session_id
            WHERE sp.mouse_id = OLD.mouse_id
        )
    WHERE mouse_id = OLD.mouse_id;
END;

-- ===============================================================================================
CREATE INDEX IF NOT EXISTS idx_mice_cage_id ON mice(cage_id);
CREATE INDEX IF NOT EXISTS idx_mice_birthDate ON mice(birthDate);
CREATE INDEX IF NOT EXISTS idx_experiments_mouse ON experiments(mouse_id);
CREATE INDEX IF NOT EXISTS idx_sessions_exp_run ON sessions(experiment_run_id);
CREATE INDEX IF NOT EXISTS idx_session_participants_mouse ON session_participants(mouse_id);
CREATE INDEX IF NOT EXISTS idx_session_participants_session ON session_participants(session_id);
CREATE INDEX IF NOT EXISTS idx_mice_type ON mice(type);

-- ===============================================================================================
CREATE TABLE IF NOT EXISTS pending_actions (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL CHECK (
        action_type IN (
            'cage_move', 'wean', 'euthanize', 'implant_chip',
            'mark_ear', 'mark_toe', 'assign_experiment',
            'retire_breeder', 'cull_litter', 'vet_check', 'defer_move'
        )
    ),
    mouse_id TEXT NOT NULL REFERENCES mice(id) ON DELETE CASCADE,
    old_cage_id TEXT REFERENCES cages(cage_id),
    new_cage_id TEXT REFERENCES cages(cage_id),
    details TEXT,
    planned_at DATETIME DEFAULT (datetime('now')),
    executed_at DATETIME,
    executor TEXT,
    notes TEXT,

    observed_status TEXT CHECK (observed_status IN (
        'as_planned', 'mouse_missing', 'mouse_dead', 'mouse_pregnant',
        'wrong_sex', 'wrong_marking', 'cage_mismatch', 'other'
    )),
    observed_notes TEXT,
    corrected_action_type TEXT,
    corrected_new_cage_id TEXT REFERENCES cages(cage_id),
    corrected_details TEXT
);

CREATE INDEX IF NOT EXISTS idx_pending_unexecuted ON pending_actions(executed_at) 
WHERE executed_at IS NULL;

CREATE VIEW IF NOT EXISTS reconciliation_queue AS
SELECT 
    action_id,
    action_type,
    mouse_id,
    old_cage_id,
    new_cage_id,
    details,
    observed_status,
    observed_notes
FROM pending_actions
WHERE executed_at IS NULL
  AND (observed_status IS NOT NULL OR observed_notes IS NOT NULL);

-- ===============================================================================================
CREATE TABLE IF NOT EXISTS db_info (key TEXT PRIMARY KEY, value TEXT);
INSERT OR REPLACE INTO db_info (key, value) VALUES ('schema_version', '5.0');