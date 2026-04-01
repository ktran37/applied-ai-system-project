"""PawPal+ core domain model and scheduling logic."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Literal

Priority = Literal["low", "medium", "high"]
Frequency = Literal["daily", "weekly", "as-needed"]

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """A single pet care activity with timing, priority, frequency, and completion state."""

    title: str
    duration_minutes: int
    priority: Priority = "medium"
    description: str = ""
    frequency: Frequency = "daily"
    completed: bool = False
    due_date: date = field(default_factory=date.today)

    def mark_complete(self) -> None:
        """Mark this task as completed so the scheduler will skip it."""
        self.completed = True

    def reset(self) -> None:
        """Reset completion status (e.g., at the start of a new day)."""
        self.completed = False

    def next_occurrence(self) -> Task | None:
        """Return a new Task copy for the next recurrence, or None if non-recurring.

        Uses timedelta to advance the due_date by 1 day (daily) or 7 days (weekly).
        Returns None for 'as-needed' tasks because they have no fixed cadence.
        """
        if self.frequency == "as-needed":
            return None
        delta = timedelta(days=1) if self.frequency == "daily" else timedelta(weeks=1)
        return replace(self, completed=False, due_date=self.due_date + delta)

    def __str__(self) -> str:
        """Return a short human-readable summary of the task."""
        status = "✓" if self.completed else "○"
        return (
            f"[{status}] {self.title} "
            f"({self.duration_minutes} min, {self.priority}, {self.frequency}, "
            f"due {self.due_date})"
        )


# ---------------------------------------------------------------------------
# Pet
# ---------------------------------------------------------------------------


@dataclass
class Pet:
    """A pet with its own list of care tasks."""

    name: str
    species: str
    age_years: float = 0.0
    notes: str = ""
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task to this pet's task list."""
        self.tasks.append(task)

    def remove_task(self, title: str) -> None:
        """Remove the first task whose title matches (case-insensitive)."""
        self.tasks = [t for t in self.tasks if t.title.lower() != title.lower()]

    def pending_tasks(self) -> list[Task]:
        """Return only tasks that have not yet been completed."""
        return [t for t in self.tasks if not t.completed]

    def __str__(self) -> str:
        """Return a short description of the pet."""
        return f"{self.name} the {self.species} (age {self.age_years})"


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------


@dataclass
class Owner:
    """A pet owner who manages one or more pets and has a daily time budget."""

    name: str
    available_minutes: int = 480
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Register a pet under this owner."""
        self.pets.append(pet)

    def get_all_tasks(self) -> list[Task]:
        """Collect and return every task across all of this owner's pets."""
        return [task for pet in self.pets for task in pet.tasks]

    def get_pending_tasks(self) -> list[Task]:
        """Return all incomplete tasks across all pets."""
        return [task for pet in self.pets for task in pet.pending_tasks()]

    def find_pet(self, name: str) -> Pet | None:
        """Look up a pet by name (case-insensitive); return None if not found."""
        for pet in self.pets:
            if pet.name.lower() == name.lower():
                return pet
        return None

    def __str__(self) -> str:
        """Return the owner's name."""
        return self.name


# ---------------------------------------------------------------------------
# Plan output
# ---------------------------------------------------------------------------


@dataclass
class ScheduledTask:
    """A task placed at a specific time in the daily plan, with a reason."""

    task: Task
    pet: Pet
    start_time: datetime
    reason: str

    @property
    def end_time(self) -> datetime:
        """Compute the end time from start time plus task duration."""
        return self.start_time + timedelta(minutes=self.task.duration_minutes)

    def time_range(self) -> str:
        """Format the start–end window as a readable string."""
        fmt = "%I:%M %p"
        return f"{self.start_time.strftime(fmt)} – {self.end_time.strftime(fmt)}"

    def __str__(self) -> str:
        """Return a single-line summary of the scheduled task."""
        return (
            f"{self.time_range()}  {self.task.title} ({self.pet.name})"
            f"  — {self.task.priority} priority"
        )


@dataclass
class DailyPlan:
    """The output of the Scheduler: ordered scheduled tasks and a list of skipped tasks."""

    owner: Owner
    scheduled: list[ScheduledTask] = field(default_factory=list)
    skipped: list[tuple[Task, Pet, str]] = field(default_factory=list)

    @property
    def total_minutes(self) -> int:
        """Total minutes occupied by scheduled tasks."""
        return sum(st.task.duration_minutes for st in self.scheduled)

    def summary(self) -> str:
        """Return a formatted multi-line schedule suitable for terminal output."""
        lines = [
            f"=== Today's Schedule for {self.owner.name} ===",
            f"Total time: {self.total_minutes} / {self.owner.available_minutes} min",
            "",
        ]
        if self.scheduled:
            lines.append("SCHEDULED:")
            for st in self.scheduled:
                lines.append(f"  {st}")
        else:
            lines.append("  (no tasks scheduled)")

        if self.skipped:
            lines.append("")
            lines.append("SKIPPED:")
            for task, pet, reason in self.skipped:
                lines.append(f"  ✗ {task.title} ({pet.name}) — {reason}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class Scheduler:
    """Greedy priority-based daily scheduler with sorting, filtering, and conflict detection."""

    def __init__(self, owner: Owner, start_hour: int = 8) -> None:
        """Initialise the scheduler with an owner and an optional day-start hour."""
        self.owner = owner
        self.start_hour = start_hour

    # ------------------------------------------------------------------
    # Core plan builder
    # ------------------------------------------------------------------

    def build_plan(self) -> DailyPlan:
        """Build a DailyPlan from all pending tasks across the owner's pets.

        Steps:
        1. Ask the owner for every pending (incomplete) task.
        2. Sort high → medium → low; shorter tasks first within each tier.
        3. Greedily assign tasks to time slots until available_minutes is exhausted.
        4. Attach a human-readable reason to every scheduled and skipped task.
        """
        plan = DailyPlan(owner=self.owner)
        remaining = self.owner.available_minutes
        current_time = datetime.today().replace(
            hour=self.start_hour, minute=0, second=0, microsecond=0
        )

        task_to_pet: dict[int, Pet] = {
            id(task): pet
            for pet in self.owner.pets
            for task in pet.pending_tasks()
        }

        sorted_tasks = sorted(
            self.owner.get_pending_tasks(),
            key=lambda t: (_PRIORITY_ORDER[t.priority], t.duration_minutes),
        )

        for task in sorted_tasks:
            pet = task_to_pet[id(task)]
            if task.duration_minutes > remaining:
                plan.skipped.append(
                    (task, pet, f"only {remaining} min left; needs {task.duration_minutes} min")
                )
                continue
            plan.scheduled.append(
                ScheduledTask(task=task, pet=pet, start_time=current_time, reason=self._explain(task, remaining))
            )
            current_time += timedelta(minutes=task.duration_minutes)
            remaining -= task.duration_minutes

        return plan

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted ascending by duration_minutes using a lambda key.

        Shorter tasks come first so a quick scan reveals the lightest work items.
        Uses Python's sorted() with a lambda to extract the numeric time attribute.
        """
        return sorted(tasks, key=lambda t: t.duration_minutes)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def filter_tasks(
        self,
        *,
        pet_name: str | None = None,
        completed: bool | None = None,
    ) -> list[tuple[Task, Pet]]:
        """Return (task, pet) pairs filtered by optional pet name and/or completion status.

        Both filters are optional and combinable:
        - pet_name: case-insensitive match against Pet.name
        - completed: True returns only done tasks; False returns only pending ones
        """
        results = []
        for pet in self.owner.pets:
            if pet_name is not None and pet.name.lower() != pet_name.lower():
                continue
            for task in pet.tasks:
                if completed is not None and task.completed != completed:
                    continue
                results.append((task, pet))
        return results

    # ------------------------------------------------------------------
    # Recurring tasks
    # ------------------------------------------------------------------

    def advance_recurring_tasks(self) -> list[Task]:
        """Complete recurring tasks and replace them with their next occurrence.

        For every completed daily/weekly task across all pets:
        1. Call task.next_occurrence() to get a fresh copy with the next due_date.
        2. Remove the completed task and append the new one to the same pet.

        Returns the list of newly created next-occurrence tasks.
        """
        new_tasks: list[Task] = []
        for pet in self.owner.pets:
            replacements: list[tuple[int, Task]] = []
            for idx, task in enumerate(pet.tasks):
                if task.completed and task.frequency != "as-needed":
                    nxt = task.next_occurrence()
                    if nxt is not None:
                        replacements.append((idx, nxt))
            # Apply replacements in reverse order to keep indices stable
            for idx, nxt in reversed(replacements):
                pet.tasks[idx] = nxt
                new_tasks.append(nxt)
        return new_tasks

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def detect_conflicts(self, plan: DailyPlan) -> list[str]:
        """Check for overlapping time windows in a DailyPlan and return warning strings.

        Uses a lightweight O(n²) pairwise check: two slots conflict when
        one starts before the other ends (i.e. their intervals overlap).
        Returns warning messages rather than raising exceptions so the
        caller can display them without crashing.
        """
        warnings: list[str] = []
        items = plan.scheduled
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if a.start_time < b.end_time and b.start_time < a.end_time:
                    warnings.append(
                        f"⚠ Conflict: '{a.task.title}' ({a.pet.name}) {a.time_range()}"
                        f" overlaps '{b.task.title}' ({b.pet.name}) {b.time_range()}"
                    )
        return warnings

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _explain(self, task: Task, remaining: int) -> str:
        """Generate a human-readable reason for why a task was scheduled."""
        phrases = {
            "high":   "High priority — scheduled first.",
            "medium": "Medium priority — fits the available window.",
            "low":    "Low priority — included with remaining time.",
        }
        return f"{phrases[task.priority]} ({remaining} min left before this task)"
