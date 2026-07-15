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
    embedding VECTOR(384) NOT NULL -- Optimized for BAAI/bge-small-en-v1.5 (384 dimensions)
);

-- 8. Create Chat Logs table (Source of telemetry processing)
CREATE TABLE IF NOT EXISTS chat_logs (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    message_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. Create Hierarchical Navigable Small World (HNSW) Index for Cosine Similarity search
CREATE INDEX IF NOT EXISTS idx_vector_knowledge_hnsw_cosine 
ON vector_knowledge 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- ==============================================================================
-- Seeds and Default System Data Initialization
-- ==============================================================================

-- Seed default RBAC roles
INSERT INTO roles (id, role_name, permissions) VALUES 
(1, 'admin', '{"can_access_admin_tools": true, "can_query_analytics": true, "can_write_knowledge": true, "can_chat_live": true}'),
(2, 'premium', '{"can_access_admin_tools": false, "can_query_analytics": true, "can_write_knowledge": true, "can_chat_live": true}'),
(3, 'standard', '{"can_access_admin_tools": false, "can_query_analytics": false, "can_write_knowledge": false, "can_chat_live": true}')
ON CONFLICT (id) DO NOTHING;

-- Seed default system user for document processing
INSERT INTO users (id, email, password_hash, role_id) VALUES 
('00000000-0000-0000-0000-000000000000', 'system@echostack.io', '$2b$12$K1dD/vFWhK4o9p/Vn/Tveuz1e2w4p5r15tS/4W/nFw0Z1E5tS1k1q', 1)
ON CONFLICT (email) DO NOTHING;

-- Seed default mock chat logs
INSERT INTO chat_logs (id, user_id, message_text) VALUES 
(1, '00000000-0000-0000-0000-000000000000', 'Hello, how can I configure pgvector HNSW?'),
(2, '00000000-0000-0000-0000-000000000000', 'What is the cosine similarity equation?'),
(3, '00000000-0000-0000-0000-000000000000', 'Explain how KRaft works in Kafka.')
ON CONFLICT (id) DO NOTHING;
