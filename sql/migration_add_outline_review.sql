-- Run once if books table already exists without outline_review
ALTER TYPE stage_status ADD VALUE IF NOT EXISTS 'outline_review';
