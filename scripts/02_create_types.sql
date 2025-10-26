-- JourneyOn: Create required enum types
-- Connect to the 'journeyon' database before running.

-- trip_stage_enum: used by trips.current_stage
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'trip_stage_enum'
    ) THEN
        CREATE TYPE trip_stage_enum AS ENUM ('pre', 'on', 'post');
    END IF;
END
$$;