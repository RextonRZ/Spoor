from spoor.api.jobs import JobRunner


def test_only_the_newest_finished_jobs_are_kept():
    jr = JobRunner(workers=1, keep=3)
    jobs = [jr.submit("x", "u", lambda j, i=i: i) for i in range(6)]
    for j in jobs:
        j.done.wait(5)
    last = jr.submit("x", "u", lambda j: 99)
    last.done.wait(5)
    assert list(jr.jobs) == [j.job_id for j in jobs[-2:]] + [last.job_id]
    assert all(j.status == "done" for j in jr.jobs.values())
