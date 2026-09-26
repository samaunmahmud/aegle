-- Rate-limit buckets shared by every core-api instance, so limits hold however many
-- replicas run. Not tenant data: keys are "<bucket>|user:<sub>" or "<bucket>|ip:<addr>".
CREATE TABLE rate_limit_buckets (
    key        text PRIMARY KEY,
    tokens     double precision NOT NULL,
    updated_at timestamptz NOT NULL
);

-- Token bucket: holds up to p_capacity tokens, refilling at p_per_second. Takes one token
-- and returns 0 if available; otherwise takes nothing and returns the seconds until one is.
-- The row lock serialises concurrent callers for the same key across all instances.
CREATE FUNCTION rate_limit_acquire(p_key text, p_capacity double precision, p_per_second double precision)
RETURNS double precision LANGUAGE plpgsql AS $$
DECLARE
    b         rate_limit_buckets;
    now_ts    timestamptz;
    available double precision;
BEGIN
    INSERT INTO rate_limit_buckets (key, tokens, updated_at)
    VALUES (p_key, p_capacity, clock_timestamp())
    ON CONFLICT (key) DO NOTHING;

    SELECT * INTO b FROM rate_limit_buckets WHERE key = p_key FOR UPDATE;
    now_ts := clock_timestamp();   -- after the lock, so waiting never counts twice
    available := LEAST(p_capacity,
                       b.tokens + GREATEST(0, extract(epoch FROM now_ts - b.updated_at)) * p_per_second);

    IF available >= 1 THEN
        UPDATE rate_limit_buckets SET tokens = available - 1, updated_at = now_ts WHERE key = p_key;
        RETURN 0;
    END IF;
    UPDATE rate_limit_buckets SET tokens = available, updated_at = now_ts WHERE key = p_key;
    RETURN (1 - available) / p_per_second;
END $$;
