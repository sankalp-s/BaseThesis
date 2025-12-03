-- PostgreSQL Database Schema for Production Memory System

-- ==================== Users Table ====================

CREATE TABLE users (
    user_id VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    conversation_count INTEGER DEFAULT 0,
    feedback_count INTEGER DEFAULT 0,
    plan_type VARCHAR(50) DEFAULT 'free',
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_users_last_active ON users(last_active);

-- ==================== Conversations Table ====================

CREATE TABLE conversations (
    conversation_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(user_id),
    turn_count INTEGER NOT NULL,
    processing_time_ms FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    summary JSONB,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_created_at ON conversations(created_at);

-- ==================== Memory Items Table ====================

CREATE TABLE memory_items (
    item_id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    user_id VARCHAR(255) REFERENCES users(user_id),
    content TEXT NOT NULL,
    retention_level VARCHAR(50) NOT NULL, -- long_term, short_term, immediate
    importance_score FLOAT NOT NULL,
    turn_number INTEGER NOT NULL,
    reasoning TEXT,
    categories JSONB, -- Array of categories
    entity_links JSONB, -- Array of linked entity IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP, -- For short-term memories
    
    CONSTRAINT valid_retention CHECK (retention_level IN ('long_term', 'short_term', 'immediate'))
);

CREATE INDEX idx_memory_items_conversation ON memory_items(conversation_id);
CREATE INDEX idx_memory_items_user ON memory_items(user_id);
CREATE INDEX idx_memory_items_retention ON memory_items(retention_level);
CREATE INDEX idx_memory_items_importance ON memory_items(importance_score);
CREATE INDEX idx_memory_items_expires ON memory_items(expires_at);

-- ==================== Entities Table ====================

CREATE TABLE entities (
    entity_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(user_id),
    entity_type VARCHAR(50) NOT NULL, -- person, location, medical_condition, etc.
    canonical_name VARCHAR(500) NOT NULL,
    importance_score FLOAT DEFAULT 0.0,
    first_mentioned_turn INTEGER,
    last_mentioned_turn INTEGER,
    mention_count INTEGER DEFAULT 0,
    attributes JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_entities_user ON entities(user_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_importance ON entities(importance_score);

-- ==================== Entity Mentions Table ====================

CREATE TABLE entity_mentions (
    mention_id SERIAL PRIMARY KEY,
    entity_id VARCHAR(255) REFERENCES entities(entity_id) ON DELETE CASCADE,
    conversation_id VARCHAR(255) REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    mention_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_entity_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX idx_entity_mentions_conversation ON entity_mentions(conversation_id);

-- ==================== Feedback Table ====================

CREATE TABLE feedback (
    feedback_id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(user_id),
    conversation_id VARCHAR(255) REFERENCES conversations(conversation_id),
    statement TEXT NOT NULL,
    actual_retention VARCHAR(50) NOT NULL,
    expected_retention VARCHAR(50) NOT NULL,
    feedback_type VARCHAR(50) NOT NULL, -- forgot_important, remembered_trivial, correct, wrong_category
    categories JSONB,
    importance_score FLOAT,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_feedback_user ON feedback(user_id);
CREATE INDEX idx_feedback_type ON feedback(feedback_type);
CREATE INDEX idx_feedback_processed ON feedback(processed);
CREATE INDEX idx_feedback_created ON feedback(created_at);

-- ==================== User Weights Table (Adaptive Learning) ====================

CREATE TABLE user_weights (
    weight_id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE CASCADE,
    pattern_name VARCHAR(255) NOT NULL,
    weight_adjustment FLOAT DEFAULT 0.0,
    feedback_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, pattern_name)
);

CREATE INDEX idx_user_weights_user ON user_weights(user_id);

-- ==================== A/B Tests Table ====================

CREATE TABLE ab_tests (
    test_id VARCHAR(255) PRIMARY KEY,
    test_name VARCHAR(255) NOT NULL,
    variants JSONB NOT NULL, -- JSON object with variant configurations
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    winner VARCHAR(255),
    results JSONB DEFAULT '{}'
);

CREATE INDEX idx_ab_tests_active ON ab_tests(active);

-- ==================== A/B Test Assignments Table ====================

CREATE TABLE ab_test_assignments (
    assignment_id SERIAL PRIMARY KEY,
    test_id VARCHAR(255) REFERENCES ab_tests(test_id) ON DELETE CASCADE,
    user_id VARCHAR(255) REFERENCES users(user_id),
    variant VARCHAR(255) NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(test_id, user_id)
);

CREATE INDEX idx_ab_assignments_test ON ab_test_assignments(test_id);
CREATE INDEX idx_ab_assignments_user ON ab_test_assignments(user_id);

-- ==================== API Keys Table ====================

CREATE TABLE api_keys (
    key_id SERIAL PRIMARY KEY,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) REFERENCES users(user_id),
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    expires_at TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    rate_limit INTEGER DEFAULT 1000, -- requests per hour
    request_count INTEGER DEFAULT 0
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_active ON api_keys(active);

-- ==================== Analytics Table ====================

CREATE TABLE analytics_events (
    event_id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) REFERENCES users(user_id),
    event_type VARCHAR(100) NOT NULL, -- conversation_analyzed, feedback_submitted, etc.
    event_data JSONB,
    processing_time_ms FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analytics_user ON analytics_events(user_id);
CREATE INDEX idx_analytics_type ON analytics_events(event_type);
CREATE INDEX idx_analytics_created ON analytics_events(created_at);

-- ==================== Views ====================

-- User activity summary
CREATE VIEW user_activity_summary AS
SELECT 
    u.user_id,
    u.conversation_count,
    u.feedback_count,
    COUNT(DISTINCT c.conversation_id) as total_conversations,
    COUNT(DISTINCT mi.item_id) as total_memory_items,
    COUNT(DISTINCT e.entity_id) as total_entities,
    AVG(c.processing_time_ms) as avg_processing_time,
    MAX(c.created_at) as last_conversation_at
FROM users u
LEFT JOIN conversations c ON u.user_id = c.user_id
LEFT JOIN memory_items mi ON u.user_id = mi.user_id
LEFT JOIN entities e ON u.user_id = e.user_id
GROUP BY u.user_id, u.conversation_count, u.feedback_count;

-- Memory retention stats
CREATE VIEW memory_retention_stats AS
SELECT 
    user_id,
    retention_level,
    COUNT(*) as count,
    AVG(importance_score) as avg_importance,
    MIN(importance_score) as min_importance,
    MAX(importance_score) as max_importance
FROM memory_items
GROUP BY user_id, retention_level;

-- Feedback effectiveness
CREATE VIEW feedback_effectiveness AS
SELECT 
    user_id,
    feedback_type,
    COUNT(*) as count,
    AVG(importance_score) as avg_importance_score
FROM feedback
GROUP BY user_id, feedback_type;

-- ==================== Functions ====================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to relevant tables
CREATE TRIGGER update_conversations_updated_at 
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entities_updated_at 
    BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-expire short-term memories
CREATE OR REPLACE FUNCTION set_memory_expiration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.retention_level = 'short_term' THEN
        -- Expire after 1 hour
        NEW.expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour';
    ELSIF NEW.retention_level = 'immediate' THEN
        -- Expire immediately
        NEW.expires_at = CURRENT_TIMESTAMP;
    ELSE
        -- Long-term memories don't expire
        NEW.expires_at = NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_memory_item_expiration 
    BEFORE INSERT ON memory_items
    FOR EACH ROW EXECUTE FUNCTION set_memory_expiration();

-- ==================== Maintenance ====================

-- Delete expired immediate memories (run periodically)
CREATE OR REPLACE FUNCTION cleanup_expired_memories()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM memory_items 
    WHERE expires_at IS NOT NULL 
    AND expires_at < CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ==================== Sample Queries ====================

-- Get user's long-term memories
-- SELECT * FROM memory_items 
-- WHERE user_id = 'user_001' 
-- AND retention_level = 'long_term' 
-- ORDER BY importance_score DESC 
-- LIMIT 10;

-- Get entities for a user
-- SELECT * FROM entities 
-- WHERE user_id = 'user_001' 
-- ORDER BY importance_score DESC;

-- Get feedback statistics
-- SELECT feedback_type, COUNT(*) as count 
-- FROM feedback 
-- WHERE user_id = 'user_001' 
-- GROUP BY feedback_type;

-- Get active A/B tests
-- SELECT * FROM ab_tests 
-- WHERE active = TRUE;

-- ==================== Indexes for Performance ====================

-- Full-text search on memory content
CREATE INDEX idx_memory_items_content_fts ON memory_items USING gin(to_tsvector('english', content));

-- JSONB indexes for fast category lookup
CREATE INDEX idx_memory_items_categories ON memory_items USING gin(categories);
CREATE INDEX idx_entities_attributes ON entities USING gin(attributes);

-- ==================== Comments ====================

COMMENT ON TABLE memory_items IS 'Stores individual memory items with retention classifications';
COMMENT ON TABLE entities IS 'Tracks entities mentioned across conversations';
COMMENT ON TABLE feedback IS 'User feedback for adaptive learning';
COMMENT ON TABLE user_weights IS 'User-specific learned importance weights';
COMMENT ON TABLE ab_tests IS 'A/B test configurations and results';
