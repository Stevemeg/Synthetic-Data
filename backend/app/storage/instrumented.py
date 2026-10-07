"""Observe bounded storage operations without recording keys or payloads."""

from time import perf_counter

from ..core.metrics import STORAGE_FAILURES, STORAGE_LATENCY


class ObservedArtifactStore:
    def __init__(self, store, backend):
        self.store = store
        self.backend = backend

    def _call(self, operation, *args):
        start = perf_counter()
        try:
            return getattr(self.store, operation)(*args)
        except Exception:
            STORAGE_FAILURES.labels(operation, self.backend).inc()
            raise
        finally:
            STORAGE_LATENCY.labels(operation, self.backend).observe(perf_counter() - start)

    def put(self, key, source):
        return self._call("put", key, source)

    def get(self, key):
        return self._call("get", key)

    def delete(self, key):
        return self._call("delete", key)

    def exists(self, key):
        return self._call("exists", key)

    def metadata(self, key):
        return self._call("metadata", key)

    def ready(self):
        return self._call("ready")
