from __future__ import annotations

import sys
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

# Ensure project root is on sys.path when running as a script
# Run from repo root: `python scripts/create_tables.py`

try:
    from app.core.config import settings
    from app.db.models import Base  # imports all models
except Exception as import_err:
    print("Import error: run from project root and ensure dependencies installed.", file=sys.stderr)
    raise


def main() -> None:
    url = settings.DATABASE_URL
    print(f"Connecting to database: {url}")

    engine = create_engine(url, pool_pre_ping=True)
    try:
        Base.metadata.create_all(bind=engine)
        print("All tables created successfully.")
    except SQLAlchemyError as e:
        print(f"Error creating tables: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()