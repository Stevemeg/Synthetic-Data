"""FastAPI is the sole supported HTTP interface."""

from .main import create_app

__all__ = ["create_app"]
