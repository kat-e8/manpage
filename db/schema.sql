-- CoderCommands MCP System
-- Postgres schema: canonical store for command-reference data normalized
-- out of coder_commands.xlsx.
--
-- Applied once at container init (mounted into the official postgres image's
-- /docker-entrypoint-initdb.d/, which runs it automatically on first boot of
-- an empty data volume).

CREATE TABLE IF NOT EXISTS commands (
    id            SERIAL PRIMARY KEY,
    topic         TEXT NOT NULL,          -- sheet name, e.g. 'sql', 'docker', 'ansible'
    section       TEXT,                   -- optional group header row, e.g. 'IMAGE MANAGEMENT'
    command       TEXT NOT NULL,          -- the command / syntax itself
    description   TEXT,                   -- what it does
    extra         TEXT,                   -- supplementary notes/flags, may be multi-line
    row_order     INTEGER NOT NULL,       -- original position within the sheet, for browse_<topic>
    -- Field-weighted: a match in the command itself outranks the same word
    -- showing up incidentally in a description or a footnote-style extra
    -- note. Default ts_rank weights for A/B/C/D are 1.0/0.4/0.2/0.1, so a
    -- command-field match counts for up to 10x a section-field match.
    -- Added after live testing showed an unweighted vector letting an
    -- unrelated row win purely by repeating query words in its extra text
    -- (see coderCommands_Plan chat record, "fix the ranking").
    search_vector TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(command, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(extra, '')), 'C') ||
        setweight(to_tsvector('english', coalesce(section, '')), 'D')
    ) STORED
);

CREATE INDEX IF NOT EXISTS commands_search_idx ON commands USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS commands_topic_idx  ON commands (topic);

-- One row per full sync pass. Written by the sync service (Step 4) so a
-- systems engineer can audit "when did the DB last agree with the xlsx"
-- without inspecting container logs -- analogous to an event/alarm log.
CREATE TABLE IF NOT EXISTS sync_runs (
    id           SERIAL PRIMARY KEY,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    xlsx_mtime   TIMESTAMPTZ,             -- modified-time of the source file at trigger time
    topics_synced INTEGER,
    rows_synced  INTEGER,
    status       TEXT NOT NULL DEFAULT 'running',  -- running | success | failed
    error        TEXT
);
