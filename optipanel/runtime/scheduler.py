from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Job:
    name: str
    stride: int
    last: int = -(10**9)


@dataclass
class State:
    tick: int = 0
    backoff: bool = False
    cooldown_left: int = 0


class Scheduler:
    """Stride-based scheduler with soft-cap aware backoff."""

    def __init__(self, jobs: dict[str, Job], *, soft_cap: int = 20, cooldown: int = 2) -> None:
        self.jobs = jobs
        self.soft_cap = int(soft_cap)
        self.cooldown = int(cooldown)
        self.state = State()

    def _due_jobs(self) -> list[Job]:
        t = self.state.tick
        return [job for job in self.jobs.values() if (t - job.last) >= job.stride]

    def step(self, used_lines: int) -> dict[str, Any]:
        st = self.state
        st.backoff = (used_lines > self.soft_cap) or (st.cooldown_left > 0)
        if used_lines > self.soft_cap:
            st.cooldown_left = self.cooldown
        elif st.cooldown_left > 0:
            st.cooldown_left -= 1

        due = self._due_jobs()
        if st.backoff:
            due = [job for job in due if job.name != "prime"]

        for job in due:
            job.last = st.tick

        out = {"tick": st.tick, "backoff": st.backoff, "due": [job.name for job in due]}
        st.tick += 1
        return out
