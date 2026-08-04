from __future__ import annotations

import os

import psycopg2
import psycopg2.extras


def get_connection():
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not dsn:
        raise RuntimeError(
            "No database connection string found. Set DATABASE_URL or POSTGRES_URL "
            "to the pooled Postgres connection string from the Vercel dashboard's "
            "Storage tab."
        )
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
