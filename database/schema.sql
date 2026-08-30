-- ============================================================
-- LUMINA — PostgreSQL Schema
-- Matches all INSERT / SELECT / UPDATE in the existing codebase
-- Run via: python -m database.models
-- ============================================================

-- ── Users ────────────────────────────────────────────────────
-- individual.py inserts: username, email, user_type
-- auth.py reads: user_id, username, password_hash, user_type
-- app.py reads:  user["user_type"]  to choose sidebar options
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    user_type VARCHAR(20) DEFAULT 'individual', -- individual | researcher
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- ── Subjects / Profiles ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS subjects (
    subject_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users (user_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    relation VARCHAR(255),
    platform VARCHAR(100),
    consent_status BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── Sessions ─────────────────────────────────────────────────
-- individual.py inserts: user_id, platform, data_file_path
-- results.py   selects: session_id, upload_date, platform
-- model.py     selects: user_id FROM sessions WHERE session_id
CREATE TABLE IF NOT EXISTS sessions (
    session_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users (user_id) ON DELETE CASCADE,
    subject_id INTEGER REFERENCES subjects (subject_id) ON DELETE CASCADE,
    platform VARCHAR(50),
    data_file_path VARCHAR(500),
    upload_date TIMESTAMP DEFAULT NOW()
);

-- ── Text Samples ──────────────────────────────────────────────
-- parser.py inserts: session_id, text_content, language_detected,
--                    source_type, sample_date, sample_month
CREATE TABLE IF NOT EXISTS text_samples (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions (session_id) ON DELETE CASCADE,
    text_content TEXT NOT NULL,
    language_detected VARCHAR(20) DEFAULT 'unknown',
    source_type VARCHAR(50),
    platform VARCHAR(50),
    sample_date VARCHAR(50),
    sample_month VARCHAR(7) -- YYYY-MM
);

-- ── NLP Scores ────────────────────────────────────────────────
-- extractor.py  inserts: session_id, ttr_score, complexity_score, coherence_score
-- classifier.py updates: risk_class, confidence_score, coherence_score
-- results.py   selects: ttr_score, complexity_score, coherence_score,
--                        risk_class, confidence_score
-- model.py     selects: ttr_score, complexity_score, risk_class, confidence_score
CREATE TABLE IF NOT EXISTS nlp_scores (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions (session_id) ON DELETE CASCADE UNIQUE,
    ttr_score NUMERIC(8, 4),
    complexity_score NUMERIC(8, 4),
    coherence_score NUMERIC(8, 4),
    repetition_score NUMERIC(8, 4),
    avg_word_length NUMERIC(8, 4),
    avg_sentence_length NUMERIC(8, 4),
    sample_count INTEGER DEFAULT 0,
    risk_score NUMERIC(8, 4),
    risk_class VARCHAR(20), -- HC | MCI | AD_Risk
    confidence_score NUMERIC(8, 4),
    duplicates_removed INTEGER DEFAULT 0
);

-- ── SNA Scores ────────────────────────────────────────────────
-- network.py  inserts: session_id, posting_frequency, network_size,
--                      interaction_diversity, withdrawal_score, dm_contact_count
-- results.py  selects: network_size, dm_contact_count, posting_frequency,
--                      interaction_diversity, withdrawal_score
-- model.py    selects: withdrawal_score
CREATE TABLE IF NOT EXISTS sna_scores (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions (session_id) ON DELETE CASCADE UNIQUE,
    posting_frequency NUMERIC(10, 4) DEFAULT 0,
    network_size INTEGER DEFAULT 0,
    interaction_diversity NUMERIC(8, 4) DEFAULT 0,
    withdrawal_score NUMERIC(8, 4) DEFAULT 0,
    dm_contact_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0
);

-- ── ABM Results ───────────────────────────────────────────────
-- model.py's save_abm_to_db (summary dict keys: final_HC, final_MCI,
-- final_AD_Risk, awareness_spread, social_decline)
CREATE TABLE IF NOT EXISTS abm_results (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions (session_id) ON DELETE CASCADE UNIQUE,
    final_hc INTEGER DEFAULT 0,
    final_mci INTEGER DEFAULT 0,
    final_ad_risk INTEGER DEFAULT 0,
    awareness_reached INTEGER DEFAULT 0,
    awareness_spread INTEGER DEFAULT 0,
    social_decline NUMERIC(8, 4) DEFAULT 0,
    mci_progression INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0
);

-- ── Final Risk Results ────────────────────────────────────────
-- model.py inserts: session_id, user_id, final_risk_class, final_score
-- results.py selects: final_risk_class, final_score
CREATE TABLE IF NOT EXISTS risk_results (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions (session_id) ON DELETE CASCADE UNIQUE,
    user_id INTEGER REFERENCES users (user_id) ON DELETE CASCADE,
    final_risk_class VARCHAR(20), -- HC | MCI | AD_Risk
    final_score NUMERIC(8, 4), -- 0.0 to 1.0
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── RAG Knowledge Base ────────────────────────────────────────
-- retriever.py queries: embedding_id, title, content, source
-- embeddings.py inserts via load_knowledge_base_to_db()
CREATE TABLE IF NOT EXISTS rag_documents (
    id SERIAL PRIMARY KEY,
    embedding_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500),
    content TEXT,
    source VARCHAR(500),
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── Environmental & Symptom Scores ───────────────────────────
CREATE TABLE IF NOT EXISTS environmental_scores (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions (session_id) ON DELETE CASCADE UNIQUE,
    -- Lancet 14 Risk Factors (boolean or smallint flags)
    education_less_than_secondary BOOLEAN DEFAULT FALSE,
    hearing_loss BOOLEAN DEFAULT FALSE,
    hypertension BOOLEAN DEFAULT FALSE,
    smoking BOOLEAN DEFAULT FALSE,
    obesity BOOLEAN DEFAULT FALSE,
    depression BOOLEAN DEFAULT FALSE,
    physical_inactivity BOOLEAN DEFAULT FALSE,
    diabetes BOOLEAN DEFAULT FALSE,
    low_social_contact BOOLEAN DEFAULT FALSE,
    excessive_alcohol BOOLEAN DEFAULT FALSE,
    traumatic_brain_injury BOOLEAN DEFAULT FALSE,
    air_pollution BOOLEAN DEFAULT FALSE,
    vision_loss BOOLEAN DEFAULT FALSE,
    high_ldl_cholesterol BOOLEAN DEFAULT FALSE,
    
    -- Self-reported symptom severity (0.0 to 1.0)
    symptom_severity NUMERIC(8, 4) DEFAULT 0.0,
    
    -- Final calculated environmental risk score
    environmental_risk_score NUMERIC(8, 4) DEFAULT 0.0
);

-- ── Indexes ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id);

CREATE INDEX IF NOT EXISTS idx_sessions_upload_date ON sessions (upload_date);

CREATE INDEX IF NOT EXISTS idx_text_samples_session ON text_samples (session_id);

CREATE INDEX IF NOT EXISTS idx_nlp_scores_session ON nlp_scores (session_id);

CREATE INDEX IF NOT EXISTS idx_sna_scores_session ON sna_scores (session_id);

CREATE INDEX IF NOT EXISTS idx_risk_results_user ON risk_results (user_id);

CREATE INDEX IF NOT EXISTS idx_risk_results_created ON risk_results (created_at);

ALTER TABLE sessions
ADD COLUMN IF NOT EXISTS data_file_path VARCHAR(500);

-- ── Analysis Runs ──────────────────────────────────────────────
-- One row per "Run Analysis" button click.
-- Groups 1..N per-file sessions under a single parent run so that
-- uploading 3 ZIP files in one click produces 1 Recent Analysis entry,
-- not 3.
CREATE TABLE IF NOT EXISTS analysis_runs (
    run_id         SERIAL PRIMARY KEY,
    user_id        INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    subject_id     INTEGER REFERENCES subjects(subject_id) ON DELETE SET NULL,
    combined_score NUMERIC(8,4),      -- sample-count-weighted mean of per-file final_scores
    combined_class VARCHAR(20),       -- HC | MCI | AD_Risk derived from combined_score
    platforms      TEXT,              -- comma-separated list, e.g. "instagram, facebook"
    session_count  INTEGER DEFAULT 1, -- how many files were in this run
    created_at     TIMESTAMP DEFAULT NOW()
);

-- Back-link each session to its parent run
ALTER TABLE sessions
ADD COLUMN IF NOT EXISTS run_id INTEGER REFERENCES analysis_runs(run_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_analysis_runs_user    ON analysis_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_created ON analysis_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_run_id       ON sessions(run_id);