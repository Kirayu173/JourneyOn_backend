-- JourneyOn: Create role and database (PostgreSQL)
-- Run this as a superuser (e.g., postgres).

-- Create application role if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'app'
    ) THEN
        CREATE ROLE app LOGIN PASSWORD 'secret';
    END IF;
END
$$;

-- Create database if not exists and assign owner
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_database WHERE datname = 'journeyon'
    ) THEN
        CREATE DATABASE journeyon OWNER app;
    END IF;
END
$$;

-- Grant privileges (optional if owner is app)
GRANT ALL PRIVILEGES ON DATABASE journeyon TO app;