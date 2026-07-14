-- ==============================================================================
-- EchoStack Database Schema & Vector Indexes Initialization Script (init.sql)
-- ==============================================================================

-- 1. Enable pgvector extension for high-dimensional vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create Roles table mapping system permissions
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL,
    permissions JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- 3. Create Users table (Core authentication references)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id INT REFERENCES roles(id) ON DELETE RESTRICT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create User Profiles table (Context variables queried as agent tools)
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    usage_tier VARCHAR(50) NOT NULL DEFAULT 'standard'
);

-- 5. Create User Analytics table (Populated by PySpark distributed batches)
CREATE TABLE IF NOT EXISTS user_analytics (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    total_interactions INT NOT NULL DEFAULT 0,
    top_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Create Documents tracking table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    file_name VARCHAR(555) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Create Vector Knowledge table for RAGFlow parsing outputs
CREATE TABLE IF NOT EXISTS vector_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(3072) NOT NULL -- Optimized for OpenAI text-embedding-3-large / Cohere v3 / custom models
);

-- 8. Create Hierarchical Navigable Small World (HNSW) Index for Cosine Similarity search
CREATE INDEX IF NOT EXISTS idx_vector_knowledge_hnsw_cosine 
ON vector_knowledge 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ==============================================================================
-- Seeds and Default System Data Initialization
-- ==============================================================================

-- Seed default RBAC roles
INSERT INTO roles (role_name, permissions) VALUES 
('admin', '{"can_access_admin_tools": true, "can_query_analytics": true, "can_write_knowledge": true, "can_chat_live": true}'),
('premium', '{"can_access_admin_tools": false, "can_query_analytics": true, "can_write_knowledge": true, "can_chat_live": true}'),
('standard', '{"can_access_admin_tools": false, "can_query_analytics": false, "can_write_knowledge": false, "can_chat_live": true}')
ON CONFLICT (role_name) DO NOTHING;
