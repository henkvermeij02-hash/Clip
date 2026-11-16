from app import db, jobs
from app.jobs import JobError

calls = {"flaky": 0}


@jobs.register("test_ok", label="ok")
def _ok(ctx):
    ctx.progress(0.5, "halfway")
    return {"value": ctx.payload.get("x")}


@jobs.register("test_fail", label="fail")
def _fail(ctx):
    raise JobError("Known problem")


@jobs.register("test_flaky", label="flaky")
def _flaky(ctx):
    calls["flaky"] += 1
    raise RuntimeError("boom")


def _force_due(job_id):
    with db.connect() as conn:
        conn.execute("UPDATE jobs SET run_after = NULL WHERE id = ?", (job_id,))


def test_job_succeeds_and_stores_result():
    job, created = jobs.enqueue("test_ok", payload={"x": 7})
    assert created
    assert jobs.run_next_job()
    done = jobs.get(job["id"])
    assert done["status"] == "succeeded" and done["result"] == {"value": 7} and done["progress"] == 1.0


def test_dedupe_key_prevents_duplicate_jobs():
    a, created_a = jobs.enqueue("test_ok", dedupe_key="same")
    b, created_b = jobs.enqueue("test_ok", dedupe_key="same")
    assert created_a and not created_b and a["id"] == b["id"]
    jobs.run_next_job()
    c, created_c = jobs.enqueue("test_ok", dedupe_key="same")  # allowed once the first finished
    assert created_c and c["id"] != a["id"]


def test_known_error_fails_without_retry():
    job, _ = jobs.enqueue("test_fail")
    jobs.run_next_job()
    failed = jobs.get(job["id"])
    assert failed["status"] == "failed" and failed["error"] == "Known problem" and failed["attempts"] == 1


def test_unexpected_error_retries_then_fails():
    calls["flaky"] = 0
    job, _ = jobs.enqueue("test_flaky", max_attempts=2)
    jobs.run_next_job()
    assert jobs.get(job["id"])["status"] == "queued"
    assert not jobs.run_next_job()  # waiting for back-off delay
    _force_due(job["id"])
    jobs.run_next_job()
    final = jobs.get(job["id"])
    assert final["status"] == "failed" and calls["flaky"] == 2 and "boom" in final["error"]


def test_interrupted_jobs_resume_after_restart():
    job, _ = jobs.enqueue("test_ok")
    with db.connect() as conn:  # simulate a crash mid-job
        conn.execute("UPDATE jobs SET status = 'running', attempts = 1 WHERE id = ?", (job["id"],))
    assert jobs.recover_interrupted() == 1
    assert jobs.get(job["id"])["status"] == "queued"
    jobs.run_next_job()
    assert jobs.get(job["id"])["status"] == "succeeded"


def test_cancel_and_retry():
    job, _ = jobs.enqueue("test_ok")
    assert jobs.cancel(job["id"])["status"] == "cancelled"
    assert not jobs.run_next_job()
    assert jobs.retry(job["id"])["status"] == "queued"
    jobs.run_next_job()
    assert jobs.get(job["id"])["status"] == "succeeded"
