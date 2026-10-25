import json
import threading

from wispsign.bridge.jobs import JobRunner
from wispsign.errors import WispError


def _run(fn):
    events, done = [], threading.Event()

    def emit(event):
        events.append(event)
        if event["type"] in ("done", "error"):
            done.set()

    job = JobRunner(emit).start(fn)
    assert done.wait(5)
    return job, events


def test_progress_then_done():
    job, events = _run(lambda progress: (progress({"percent": 5}), {"x": 1})[1])
    assert events == [
        {"job": job, "type": "progress", "percent": 5},
        {"job": job, "type": "done", "result": {"x": 1}},
    ]


def test_wisp_error_mapped():
    def boom(progress):
        raise WispError("error.sign_failed", "d", a=1)

    job, events = _run(boom)
    assert events == [
        {
            "job": job,
            "type": "error",
            "error": {"code": "error.sign_failed", "params": {"a": 1}, "detail": "d"},
        }
    ]


def test_unknown_exception_mapped():
    def boom(progress):
        raise RuntimeError("x")

    _, events = _run(boom)
    assert events[0]["error"]["code"] == "error.unknown"


def test_failing_emit_does_not_kill_thread():
    calls = []

    def emit(event):
        calls.append(event)
        raise RuntimeError("ui gone")

    runner = JobRunner(emit)
    runner.start(lambda progress: None)
    for _ in range(100):
        if calls:
            break
        threading.Event().wait(0.05)
    assert calls[0]["type"] == "done"


def test_fast_job_result_retrievable_after_start_returns():
    emitted = []
    runner = JobRunner(emitted.append)
    job = runner.start(lambda progress: 1)
    for _ in range(100):
        if runner.result(job):
            break
        threading.Event().wait(0.02)
    assert runner.result(job) == {"job": job, "type": "done", "result": 1}
    assert runner.result("nope") is None


def test_results_are_bounded():
    from wispsign.bridge import jobs

    runner = JobRunner(lambda e: None)
    for i in range(jobs.MAX_KEPT_RESULTS + 5):
        runner._finish(str(i), {"job": str(i), "type": "done", "result": i})
    assert runner.result("0") is None
    assert runner.result(str(jobs.MAX_KEPT_RESULTS + 4)) is not None


def test_error_params_made_json_safe():
    from datetime import UTC, datetime
    from pathlib import Path

    def boom(progress):
        raise WispError(
            "error.io", "d", p=Path("x"), t=datetime(2026, 1, 1, tzinfo=UTC), o=object()
        )

    _, events = _run(boom)
    params = events[0]["error"]["params"]
    assert params["p"] == "x" and params["t"] == "2026-01-01T00:00:00Z"
    assert isinstance(params["o"], str)
    json.dumps(events[0])


def test_unserializable_result_becomes_error_event():
    _, events = _run(lambda progress: {"x": object()})
    assert [e["type"] for e in events] == ["error"]
    assert events[0]["error"]["code"] == "error.unknown"


def test_done_result_is_jsonable():
    from pathlib import Path

    _, events = _run(lambda progress: {"p": Path("a")})
    assert events[0]["result"] == {"p": "a"}
