-- Run in Supabase SQL Editor after schema.sql
-- Fixes: "new row violates row-level security policy for table books"

-- Enable RLS on the tables
ALTER TABLE books ENABLE ROW LEVEL SECURITY;
ALTER TABLE chapters ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if re-running
DROP POLICY IF EXISTS "books_api_all" ON books;
DROP POLICY IF EXISTS "chapters_api_all" ON chapters;
DROP POLICY IF EXISTS "users_api_all" ON users;

-- Allow API (anon/authenticated key) full access to backend tables
CREATE POLICY "books_api_all" ON books
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "chapters_api_all" ON chapters
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "users_api_all" ON users
    FOR ALL
    USING (true)
    WITH CHECK (true);