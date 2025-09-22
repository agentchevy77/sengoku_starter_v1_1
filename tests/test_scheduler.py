from optipanel.runtime.scheduler import Job, Scheduler


def test_scheduler_stride_and_backoff_sequence():
    jobs = {
        "prime": Job("prime", stride=1),
        "secondary": Job("secondary", stride=2),
    }
    sched = Scheduler(jobs, soft_cap=5, cooldown=2)

    # tick 0: both should fire
    step0 = sched.step(used_lines=1)
    assert step0 == {"tick": 0, "backoff": False, "due": ["prime", "secondary"]}

    # tick 1: overload triggers backoff, prime suppressed
    step1 = sched.step(used_lines=10)
    assert step1 == {"tick": 1, "backoff": True, "due": []}

    # tick 2: cooldown active, secondary runs, prime skipped
    step2 = sched.step(used_lines=1)
    assert step2 == {"tick": 2, "backoff": True, "due": ["secondary"]}

    # tick 3: cooldown still draining, nothing due (secondary not yet due)
    step3 = sched.step(used_lines=1)
    assert step3 == {"tick": 3, "backoff": True, "due": []}

    # tick 4: cooldown complete, both jobs resume
    step4 = sched.step(used_lines=1)
    assert step4 == {"tick": 4, "backoff": False, "due": ["prime", "secondary"]}


def test_scheduler_backoff_skips_prime():
    sched = Scheduler(
        {"prime": Job("prime", 1), "secondary": Job("secondary", 2)},
        soft_cap=10,
        cooldown=2,
    )

    out0 = sched.step(used_lines=20)
    assert out0["backoff"] is True
    assert "prime" not in out0["due"]

    out1 = sched.step(used_lines=5)
    assert out1["backoff"] is True
    assert "prime" not in out1["due"]

    out2 = sched.step(used_lines=5)
    assert out2["backoff"] is True

    out3 = sched.step(used_lines=5)
    assert out3["backoff"] is False


def test_scheduler_stride_behavior():
    sched = Scheduler(
        {"prime": Job("prime", 1), "secondary": Job("secondary", 3)},
        soft_cap=99,
        cooldown=0,
    )
    dues = []
    for _ in range(6):
        out = sched.step(used_lines=0)
        dues.append(out["due"])

    assert "secondary" in dues[0]
    assert "secondary" in dues[3]
    assert "secondary" not in dues[1]
    assert "secondary" not in dues[2]
