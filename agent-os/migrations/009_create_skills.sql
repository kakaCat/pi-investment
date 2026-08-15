-- Migration: Create Skills and Skill Versions tables
-- Created: 2026-08-15
-- Purpose: Skill Hub - store skills with versioning

-- Drop existing tables if they exist (for clean migration)
DROP TABLE IF EXISTS skill_versions CASCADE;
DROP TABLE IF EXISTS skills CASCADE;

-- Skills table
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    category VARCHAR(100),
    owner VARCHAR(100) NOT NULL,
    current_version_id UUID,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_skills_name ON skills(name);
CREATE INDEX idx_skills_owner ON skills(owner);
CREATE INDEX idx_skills_status ON skills(status);
CREATE INDEX idx_skills_category ON skills(category);

-- Skill Versions table
CREATE TABLE skill_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    version VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    author VARCHAR(100),
    commit_message TEXT,
    parent_version_id UUID REFERENCES skill_versions(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,
    UNIQUE(skill_id, version)
);

CREATE INDEX idx_skill_versions_skill_id ON skill_versions(skill_id);
CREATE INDEX idx_skill_versions_created_at ON skill_versions(created_at DESC);
CREATE INDEX idx_skill_versions_content_hash ON skill_versions(content_hash);

-- Add foreign key constraint from skills to skill_versions
ALTER TABLE skills
    ADD CONSTRAINT fk_skills_current_version
    FOREIGN KEY (current_version_id)
    REFERENCES skill_versions(id);

-- Add comments
COMMENT ON TABLE skills IS 'Skill registry with metadata';
COMMENT ON TABLE skill_versions IS 'Skill version history with content';
COMMENT ON COLUMN skills.current_version_id IS 'Points to the active version in skill_versions';
COMMENT ON COLUMN skill_versions.content_hash IS 'SHA256 hash of content for deduplication';
COMMENT ON COLUMN skill_versions.parent_version_id IS 'Points to the previous version for history tracking';
