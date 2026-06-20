-- Add template storage for outline templates
CREATE TABLE IF NOT EXISTS outline_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    template_json JSONB NOT NULL,  -- Stores the outline structure
    category TEXT,  -- e.g., 'fiction', 'non-fiction', 'academic', etc.
    is_public BOOLEAN DEFAULT TRUE,  -- Whether template is available to all users
    created_by UUID,  -- Reference to user who created it (if we have user table)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create index for faster lookup by category
CREATE INDEX IF NOT EXISTS idx_outline_templates_category ON outline_templates(category);

-- Create index for public templates
CREATE INDEX IF NOT EXISTS idx_outline_templates_public ON outline_templates(is_public) WHERE is_public = TRUE;

-- Auto-update updated_at trigger
DROP TRIGGER IF EXISTS outline_templates_updated_at ON outline_templates;
CREATE OR REPLACE FUNCTION set_updated_at_outline_templates()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER outline_templates_updated_at
    BEFORE UPDATE ON outline_templates
    FOR EACH ROW EXECUTE FUNCTION set_updated_at_outline_templates();