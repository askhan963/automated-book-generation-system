-- RLS policies for outline_templates table
ALTER TABLE outline_templates ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if re-running
DROP POLICY IF EXISTS "outline_templates_api_all" ON outline_templates;

-- Allow API (anon/authenticated key) full access to backend tables
CREATE POLICY "outline_templates_api_all" ON outline_templates
    FOR ALL
    USING (true)
    WITH CHECK (true);