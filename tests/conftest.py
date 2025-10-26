import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure repository root and app package are importable
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
for p in (str(ROOT), str(APP)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Default test environment
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("LOG_LEVEL", "debug")

from app.main import app  # noqa: E402

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c