-- Run this in the Supabase SQL Editor

CREATE TYPE stage_status AS ENUM (
    'pending_notes',
    'pending_review',
    'outline_review',
    'approved',
    'no_notes_needed'
);

CREATE TYPE book_phase AS ENUM (
    'outline',
    'chapters',
    'completed'
);

CREATE TABLE books (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    initial_notes   TEXT,
    outline         JSONB,
    outline_status              stage_status NOT NULL DEFAULT 'pending_review',
    final_review_notes_status   stage_status NOT NULL DEFAULT 'pending_review',
    phase                       book_phase NOT NULL DEFAULT 'outline',
    human_notes                 TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chapters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id         UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chapter_number  INT NOT NULL,
    title           TEXT NOT NULL,
    content         TEXT,
    summary         TEXT,
    status          stage_status NOT NULL DEFAULT 'pending_review',
    human_notes     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (book_id, chapter_number)
);

CREATE INDEX idx_chapters_book_id ON chapters(book_id);
CREATE INDEX idx_chapters_book_number ON chapters(book_id, chapter_number);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER books_updated_at
    BEFORE UPDATE ON books
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER chapters_updated_at
    BEFORE UPDATE ON chapters
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
