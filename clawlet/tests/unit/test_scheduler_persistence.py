"""Unit tests for scheduler jobs/runs persistence."""

from __future__ import annotations

from datetime import timedelta
import json

import pytest

from clawlet.heartbeat.cron_scheduler import Scheduler
from clawlet.heartbeat.models import ScheduledTask, TaskAction


@pytest.mark.asyncio
async def test_scheduler_persists_jobs_and_runs(tmp_path):
    jobs_file = tmp_path / "cron" / "jobs.json"
    runs_dir = tmp_path / "cron" / "runs"
    state_file = tmp_path / "cron" / "state.json"

    scheduler = Scheduler(
        timezone="UTC",
        jobs_file=str(jobs_file),
        runs_dir=str(runs_dir),
        state_file=str(state_file),
    )

    task = ScheduledTask(
        id="nightly_job",
        name="Nightly job",
        action=TaskAction.AGENT,
        params={"prompt": "Nightly check"},
        interval=timedelta(minutes=30),
    )
    scheduler.add_task(task)

    assert jobs_file.exists()
    jobs_payload = json.loads(jobs_file.read_text(encoding="utf-8"))
    assert "nightly_job" in jobs_payload["jobs"]

    scheduler2 = Scheduler(
        timezone="UTC",
        jobs_file=str(jobs_file),
        runs_dir=str(runs_dir),
        state_file=str(state_file),
    )
    loaded = scheduler2.load_jobs(jobs_file)
    assert loaded == 1

    result = await scheduler2.run_task("nightly_job")
    assert result.success is True
    assert result.status.value == "completed"

    run_entries = scheduler2.list_runs("nightly_job", limit=10)
    assert len(run_entries) == 1
    assert run_entries[0]["job_id"] == "nightly_job"
    assert run_entries[0]["success"] is True
    assert run_entries[0]["trigger"] == "manual"
    assert run_entries[0]["delivery_status"] == "not-requested"
