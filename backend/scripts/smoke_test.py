"""Compatibility entry point; Phase 2 smoke requires migrated PostgreSQL."""

from .platform_smoke_test import main

if __name__ == "__main__":
    main()
