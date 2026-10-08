"""Redis. Used for the project catalogue and for the live reveal counter,
which is read on every spin and does not belong in Postgres."""
import json
import os

import redis

_client = None


def client():
    global _client
    if _client is None:
        _client = redis.Redis.from_url(os.environ.get("REDIS_URL", ""), decode_responses=True)
    return _client


def get_json(key):
    raw = client().get(key)
    return json.loads(raw) if raw else None


def set_json(key, value, ttl=3600):
    client().set(key, json.dumps(value), ex=ttl)


def drop(key):
    client().delete(key)


def incr_reveal(run_id):
    """How many groups of this run have been revealed. One atomic counter."""
    return client().incr(f"run:{run_id}:revealed")


def reveal_count(run_id):
    v = client().get(f"run:{run_id}:revealed")
    return int(v) if v else 0


def reset_reveals(run_id):
    client().delete(f"run:{run_id}:revealed")
