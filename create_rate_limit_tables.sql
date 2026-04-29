-- Create rate_limit_counters table
CREATE TABLE IF NOT EXISTS rate_limit_counters (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL,
    endpoint    VARCHAR(120) NOT NULL,
    window_day  DATE NOT NULL,
    count       INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_rl_tenant_endpoint_day UNIQUE (tenant_id, endpoint, window_day)
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_rl_tenant_day
    ON rate_limit_counters (tenant_id, window_day);

-- Disable RLS
ALTER TABLE rate_limit_counters DISABLE ROW LEVEL SECURITY;

-- Create usage_events table if not exists
CREATE TABLE IF NOT EXISTS usage_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     TEXT NOT NULL,
    endpoint_path TEXT NOT NULL,
    status_code   INTEGER NOT NULL,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_usage_events_tenant_date
    ON usage_events (tenant_id, created_at);

-- Disable RLS
ALTER TABLE usage_events DISABLE ROW LEVEL SECURITY;
