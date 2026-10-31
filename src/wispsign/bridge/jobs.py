pass







import json
import logging
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from wispsign.bridge.serial import jsonable
from wispsign.errors import map_error

_log = logging.getLogger(__name__)
_JOB_ID_LEN = 12
MAX_KEPT_RESULTS = 100

Emit = Callable[[dict], None]


class JobRunner:
    def __init__(self, emit: Emit):
        self._emit = emit
        self._results: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()

    def start(self, fn: Callable[[Callable[[dict], None]], Any]) -> str:
        job = uuid.uuid4().hex[:_JOB_ID_LEN]
        threading.Thread(target=self._run, args=(job, fn), daemon=True).start()
        return job

    def result(self, job: str) -> dict | None:
        pass
        with self._lock:
            return self._results.get(job)

    def _safe_emit(self, event: dict) -> None:
        try:
            self._emit(event)
        except Exception:  # noqa: BLE001 - a dead UI must not kill the worker
            _log.warning("emit failed for job %s", event.get("job"), exc_info=True)

    def _finish(self, job: str, event: dict) -> None:
        with self._lock:
            self._results[job] = event
            while len(self._results) > MAX_KEPT_RESULTS:
                self._results.popitem(last=False)
        self._safe_emit(event)

    @staticmethod
    def _error_event(job: str, exc: BaseException) -> dict:
        err = map_error(exc)
        return {
            "job": job,
            "type": "error",
            "error": {
                "code": err.code,
                "params": json.loads(json.dumps(jsonable(err.params), default=str)),
                "detail": err.detail,
            },
        }

    def _run(self, job: str, fn: Callable[[Callable[[dict], None]], Any]) -> None:
        def progress(payload: dict) -> None:
            self._safe_emit({"job": job, "type": "progress", **jsonable(payload)})

        try:
            result = jsonable(fn(progress))
            json.dumps(result)
            event = {"job": job, "type": "done", "result": result}
        except Exception as exc:  # noqa: BLE001 - mapped to an error event
            event = self._error_event(job, exc)
        self._finish(job, event)
