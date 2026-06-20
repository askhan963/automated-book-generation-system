-- Add analytics fields to books table for writing style tracking
ALTER TABLE books ADD COLUMN IF NOT EXISTS genre TEXT;
ALTER TABLE books ADD COLUMN IF NOT EXISTS tone TEXT;
ALTER TABLE books ADD COLUMN IF NOT EXISTS audience TEXT;
ALTER TABLE books ADD COLUMN IF NOT EXISTS length TEXT;