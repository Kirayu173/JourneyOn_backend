from __future__ import annotations

from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """Standard API envelope used by the backend."""
    code: int
    msg: str
    data: Optional[T] = None