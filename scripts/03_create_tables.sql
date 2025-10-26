-- JourneyOn: Create tables (PostgreSQL)
-- Connect to the 'journeyon' database before running.
-- Ensure enum type 'trip_stage_enum' exists (see 02_create_types.sql).

-- users
CREATE TABLE IF NOT EXISTS public.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT,
    display_name VARCHAR(128),
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users (email);

-- trips
CREATE TABLE IF NOT EXISTS public.trips (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    origin VARCHAR(255),
    origin_lat DOUBLE PRECISION,
    origin_lng DOUBLE PRECISION,
    destination VARCHAR(255),
    destination_lat DOUBLE PRECISION,
    destination_lng DOUBLE PRECISION,
    start_date DATE,
    duration_days INTEGER,
    budget NUMERIC(10,2),
    currency VARCHAR(8) NOT NULL DEFAULT 'CNY',
    current_stage trip_stage_enum NOT NULL DEFAULT 'pre',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    preferences JSONB,
    agent_context JSONB,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- trip_stages
CREATE TABLE IF NOT EXISTS public.trip_stages (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES public.trips(id) ON DELETE CASCADE,
    stage_name VARCHAR(8) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    assigned_agent VARCHAR(128),
    confirmed_at TIMESTAMP WITH TIME ZONE,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_trip_stage UNIQUE (trip_id, stage_name)
);

-- itinerary_items
CREATE TABLE IF NOT EXISTS public.itinerary_items (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES public.trips(id) ON DELETE CASCADE,
    day INTEGER NOT NULL,
    start_time VARCHAR(32),
    end_time VARCHAR(32),
    kind VARCHAR(32),
    title VARCHAR(255),
    location VARCHAR(255),
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    details TEXT
);

-- tasks
CREATE TABLE IF NOT EXISTS public.tasks (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES public.trips(id) ON DELETE CASCADE,
    stage VARCHAR(8) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 1,
    assigned_to VARCHAR(64),
    due_date DATE,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- conversations
CREATE TABLE IF NOT EXISTS public.conversations (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES public.trips(id) ON DELETE CASCADE,
    stage VARCHAR(8) NOT NULL,
    role VARCHAR(16) NOT NULL,
    message TEXT NOT NULL,
    message_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- kb_entries
CREATE TABLE IF NOT EXISTS public.kb_entries (
    id SERIAL PRIMARY KEY,
    trip_id INTEGER REFERENCES public.trips(id) ON DELETE SET NULL,
    source VARCHAR(64),
    title VARCHAR(255),
    content TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding_id VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- user_tags
CREATE TABLE IF NOT EXISTS public.user_tags (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    tag VARCHAR(64) NOT NULL,
    weight DOUBLE PRECISION,
    source_trip_id INTEGER REFERENCES public.trips(id) ON DELETE SET NULL
);

-- audit_logs
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES public.users(id) ON DELETE SET NULL,
    trip_id INTEGER REFERENCES public.trips(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    detail TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);