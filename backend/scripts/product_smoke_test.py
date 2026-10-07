"""Phase 5 real API/worker/report/restart workflow with generated fake data only."""

from backend.scripts.create_demo_project import restart_check, workflow
from backend.scripts.platform_smoke_test import main

if __name__ == "__main__":
    main(workflow, restart_check)
