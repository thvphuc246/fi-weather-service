CREATE TABLE IF NOT EXISTS observation (
    place text NOT NULL,
    ts timestamptz NOT NULL,
    param text NOT NULL,
    value double precision NOT NULL,
    PRIMARY KEY (place, ts, param)
);

-- Latest forecast only: each fetch overwrites the same (place, ts, param).
CREATE TABLE IF NOT EXISTS forecast (
    place text NOT NULL,
    ts timestamptz NOT NULL,
    param text NOT NULL,
    value double precision NOT NULL,
    PRIMARY KEY (place, ts, param)
);
