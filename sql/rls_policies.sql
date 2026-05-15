-- Run in Supabase SQL Editor after schema.sql
-- Fixes: "new row violates row-level security policy for table books"

ALTER TABLE books ENABLE ROW LEVEL SECURITY;
ALTER TABLE chapters ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if re-running
DROP POLICY IF EXISTS "books_api_all" ON books;
DROP POLICY IF EXISTS "chapters_api_all" ON chapters;

-- Allow API (anon/authenticated key) full access to backend tables
CREATE POLICY "books_api_all" ON books
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "chapters_api_all" ON chapters
    FOR ALL
    USING (true)
    WITH CHECK (true);
