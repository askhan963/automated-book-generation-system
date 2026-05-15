-- Run once if books table exists without final_review_notes_status
ALTER TABLE books
    ADD COLUMN IF NOT EXISTS final_review_notes_status stage_status NOT NULL DEFAULT 'pending_review';
