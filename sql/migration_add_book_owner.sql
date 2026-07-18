-- Add ownership so each book belongs to a user
ALTER TABLE books
    ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_books_owner_id ON books(owner_id);
