import argparse
import signal
from threading import Event

from dotenv import load_dotenv

from backend.app.config import ROOT, Settings
from backend.app.core.logging import configure_logging, log_event
from backend.app.core.worker_metrics import serve
from backend.app.db.session import Database
from backend.app.services.lifecycle import purge_once
from backend.app.storage.factory import artifact_store
from backend.app.workers.runner import Worker


def main():
    parser = argparse.ArgumentParser(description="PostgreSQL-backed MedSynth Guard worker")
    parser.add_argument("--once", action="store_true", help="Claim at most one job and exit")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    database = Database(settings)
    stop = Event()

    def shutdown(signum, frame):
        stop.set()
        log_event("worker_shutdown_requested")

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    worker = None
    metrics_server = None
    try:
        try:
            store = artifact_store(settings)
            store.ready()
            database.ready()
            worker = Worker(settings, database, store)
        except Exception as error:
            log_event("worker_startup_failed", exception_type=type(error).__name__)
            raise SystemExit(1) from None
        log_event("worker_started", worker_id=worker.worker_id)
        metrics_server = serve(settings.worker_metrics_port, settings.metrics_token)
        while not stop.is_set():
            try:
                worked = purge_once(database, store) or worker.run_once()
            except Exception as error:
                log_event("worker_poll_failed", exception_type=type(error).__name__)
                if args.once:
                    raise SystemExit(1) from None
                worked = False
            if args.once:
                break
            if not worked:
                stop.wait(settings.job_poll_interval)
    finally:
        if metrics_server:
            metrics_server.shutdown()
            metrics_server.server_close()
        database.dispose()
        log_event("worker_stopped", worker_id=worker.worker_id if worker else None)


if __name__ == "__main__":
    main()
