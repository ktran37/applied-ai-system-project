"""Tests for PawPal+ core logic."""

from datetime import datetime, timedelta

import pytest
from pawpal_system import DailyPlan, Owner, Pet, ScheduledTask, Scheduler, Task


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_owner():
    owner = Owner(name="Jordan", available_minutes=120)
    pet = Pet(name="Mochi", species="dog")
    owner.add_pet(pet)
    return owner


@pytest.fixture
def basic_pet():
    return Pet(name="Mochi", species="dog")


# ---------------------------------------------------------------------------
# Task tests
# ---------------------------------------------------------------------------


def test_mark_complete_changes_status():
    """Calling mark_complete() should set completed to True."""
    task = Task("Morning walk", duration_minutes=20)
    assert task.completed is False
    task.mark_complete()
    assert task.completed is True


def test_mark_complete_excludes_task_from_schedule(basic_owner):
    """A completed task should not appear in the generated plan."""
    pet = basic_owner.pets[0]
    task = Task("Walk", duration_minutes=20, priority="high")
    pet.add_task(task)
    task.mark_complete()

    plan = Scheduler(basic_owner).build_plan()
    scheduled_titles = [st.task.title for st in plan.scheduled]
    assert "Walk" not in scheduled_titles


def test_reset_restores_pending_status():
    """reset() should allow a completed task to be scheduled again."""
    task = Task("Walk", duration_minutes=20)
    task.mark_complete()
    task.reset()
    assert task.completed is False


# ---------------------------------------------------------------------------
# Pet / task-addition tests
# ---------------------------------------------------------------------------


def test_add_task_increases_pet_task_count(basic_pet):
    """Adding a task to a Pet should increase its task list length by 1."""
    before = len(basic_pet.tasks)
    basic_pet.add_task(Task("Feeding", duration_minutes=5))
    assert len(basic_pet.tasks) == before + 1


def test_add_multiple_tasks_all_appear(basic_pet):
    """All added tasks should be present on the pet."""
    titles = ["Walk", "Feed", "Play", "Groom"]
    for t in titles:
        basic_pet.add_task(Task(t, duration_minutes=10))
    stored = [t.title for t in basic_pet.tasks]
    assert stored == titles


def test_remove_task_decreases_count(basic_pet):
    """remove_task() should drop the matching task from the pet's list."""
    basic_pet.add_task(Task("Walk", duration_minutes=20))
    basic_pet.add_task(Task("Feed", duration_minutes=5))
    basic_pet.remove_task("Walk")
    assert len(basic_pet.tasks) == 1
    assert basic_pet.tasks[0].title == "Feed"


def test_pending_tasks_excludes_completed(basic_pet):
    """pending_tasks() should return only incomplete tasks."""
    t1 = Task("Walk", duration_minutes=20)
    t2 = Task("Feed", duration_minutes=5)
    t2.mark_complete()
    basic_pet.add_task(t1)
    basic_pet.add_task(t2)
    assert basic_pet.pending_tasks() == [t1]


# ---------------------------------------------------------------------------
# Owner tests
# ---------------------------------------------------------------------------


def test_owner_add_pet_increases_count():
    """add_pet() should register the pet under the owner."""
    owner = Owner(name="Jordan")
    assert len(owner.pets) == 0
    owner.add_pet(Pet("Mochi", "dog"))
    assert len(owner.pets) == 1


def test_owner_get_all_tasks_aggregates_across_pets():
    """get_all_tasks() should return tasks from every pet."""
    owner = Owner(name="Jordan")
    p1 = Pet("Mochi", "dog")
    p2 = Pet("Noodle", "cat")
    p1.add_task(Task("Walk", duration_minutes=20))
    p2.add_task(Task("Feed", duration_minutes=5))
    p2.add_task(Task("Play", duration_minutes=10))
    owner.add_pet(p1)
    owner.add_pet(p2)
    assert len(owner.get_all_tasks()) == 3


def test_owner_get_pending_tasks_skips_completed():
    """get_pending_tasks() should exclude completed tasks from all pets."""
    owner = Owner(name="Jordan")
    pet = Pet("Mochi", "dog")
    t1 = Task("Walk", duration_minutes=20)
    t2 = Task("Feed", duration_minutes=5)
    t2.mark_complete()
    pet.add_task(t1)
    pet.add_task(t2)
    owner.add_pet(pet)
    assert owner.get_pending_tasks() == [t1]


def test_owner_find_pet_returns_correct_pet():
    """find_pet() should return the right Pet by name."""
    owner = Owner(name="Jordan")
    owner.add_pet(Pet("Mochi", "dog"))
    owner.add_pet(Pet("Noodle", "cat"))
    found = owner.find_pet("noodle")  # case-insensitive
    assert found is not None
    assert found.name == "Noodle"


# ---------------------------------------------------------------------------
# Scheduler tests
# ---------------------------------------------------------------------------


def test_scheduler_builds_plan_from_owner_pets():
    """Scheduler should pull tasks from the owner's pets automatically."""
    owner = Owner(name="Jordan", available_minutes=60)
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", duration_minutes=20, priority="high"))
    pet.add_task(Task("Feed", duration_minutes=10, priority="high"))
    owner.add_pet(pet)

    plan = Scheduler(owner).build_plan()
    assert len(plan.scheduled) == 2
    assert plan.total_minutes == 30


def test_scheduler_respects_time_budget():
    """Total scheduled minutes must not exceed owner's available_minutes."""
    owner = Owner(name="Jordan", available_minutes=30)
    pet = Pet("Mochi", "dog")
    for i in range(5):
        pet.add_task(Task(f"Task {i}", duration_minutes=15, priority="medium"))
    owner.add_pet(pet)

    plan = Scheduler(owner).build_plan()
    assert plan.total_minutes <= 30


def test_scheduler_high_priority_first():
    """High-priority tasks should be scheduled before lower-priority ones."""
    owner = Owner(name="Jordan", available_minutes=120)
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Low task",    duration_minutes=10, priority="low"))
    pet.add_task(Task("High task",   duration_minutes=10, priority="high"))
    pet.add_task(Task("Medium task", duration_minutes=10, priority="medium"))
    owner.add_pet(pet)

    plan = Scheduler(owner).build_plan()
    titles = [st.task.title for st in plan.scheduled]
    assert titles.index("High task") < titles.index("Medium task")
    assert titles.index("Medium task") < titles.index("Low task")


def test_scheduler_skips_completed_tasks():
    """Completed tasks should not appear in the scheduled list."""
    owner = Owner(name="Jordan", available_minutes=60)
    pet = Pet("Mochi", "dog")
    done = Task("Old task", duration_minutes=10, priority="high")
    done.mark_complete()
    pet.add_task(done)
    pet.add_task(Task("New task", duration_minutes=10, priority="medium"))
    owner.add_pet(pet)

    plan = Scheduler(owner).build_plan()
    titles = [st.task.title for st in plan.scheduled]
    assert "Old task" not in titles
    assert "New task" in titles


# ---------------------------------------------------------------------------
# Sorting tests
# ---------------------------------------------------------------------------


def test_sort_by_time_returns_ascending_duration():
    """sort_by_time() should order tasks from shortest to longest duration."""
    owner = Owner("Jordan")
    pet = Pet("Mochi", "dog")
    owner.add_pet(pet)
    tasks = [
        Task("Long",   duration_minutes=60),
        Task("Short",  duration_minutes=5),
        Task("Medium", duration_minutes=20),
    ]
    result = Scheduler(owner).sort_by_time(tasks)
    durations = [t.duration_minutes for t in result]
    assert durations == sorted(durations)


def test_sort_by_time_preserves_all_tasks():
    """sort_by_time() should not drop any tasks."""
    owner = Owner("Jordan")
    owner.add_pet(Pet("Mochi", "dog"))
    tasks = [Task(f"Task {i}", duration_minutes=i * 5 + 1) for i in range(6)]
    result = Scheduler(owner).sort_by_time(tasks)
    assert len(result) == len(tasks)


# ---------------------------------------------------------------------------
# Filtering tests
# ---------------------------------------------------------------------------


def test_filter_tasks_by_pet_name():
    """filter_tasks(pet_name=...) should return only that pet's tasks."""
    owner = Owner("Jordan")
    mochi = Pet("Mochi", "dog")
    noodle = Pet("Noodle", "cat")
    mochi.add_task(Task("Walk", duration_minutes=20))
    noodle.add_task(Task("Feed", duration_minutes=5))
    owner.add_pet(mochi)
    owner.add_pet(noodle)

    result = Scheduler(owner).filter_tasks(pet_name="Mochi")
    assert all(pet.name == "Mochi" for _, pet in result)
    assert len(result) == 1


def test_filter_tasks_by_completed_status():
    """filter_tasks(completed=True) should return only completed tasks."""
    owner = Owner("Jordan")
    pet = Pet("Mochi", "dog")
    done = Task("Done", duration_minutes=10)
    done.mark_complete()
    pending = Task("Pending", duration_minutes=10)
    pet.add_task(done)
    pet.add_task(pending)
    owner.add_pet(pet)

    result = Scheduler(owner).filter_tasks(completed=True)
    assert all(task.completed for task, _ in result)
    assert len(result) == 1


def test_filter_tasks_combined():
    """filter_tasks with both pet_name and completed should apply both filters."""
    owner = Owner("Jordan")
    mochi = Pet("Mochi", "dog")
    t1 = Task("Walk", duration_minutes=20)
    t1.mark_complete()
    t2 = Task("Feed", duration_minutes=5)
    mochi.add_task(t1)
    mochi.add_task(t2)
    owner.add_pet(mochi)

    result = Scheduler(owner).filter_tasks(pet_name="Mochi", completed=False)
    titles = [t.title for t, _ in result]
    assert titles == ["Feed"]


# ---------------------------------------------------------------------------
# Recurring task tests
# ---------------------------------------------------------------------------


def test_next_occurrence_daily_advances_one_day():
    """next_occurrence() for a daily task should set due_date to today + 1."""
    from datetime import date, timedelta
    task = Task("Walk", duration_minutes=20, frequency="daily")
    nxt = task.next_occurrence()
    assert nxt is not None
    assert nxt.due_date == task.due_date + timedelta(days=1)


def test_next_occurrence_weekly_advances_seven_days():
    """next_occurrence() for a weekly task should set due_date to today + 7."""
    from datetime import timedelta
    task = Task("Grooming", duration_minutes=15, frequency="weekly")
    nxt = task.next_occurrence()
    assert nxt is not None
    assert nxt.due_date == task.due_date + timedelta(weeks=1)


def test_next_occurrence_as_needed_returns_none():
    """next_occurrence() for an as-needed task should return None."""
    task = Task("Vet visit", duration_minutes=60, frequency="as-needed")
    assert task.next_occurrence() is None


def test_next_occurrence_resets_completed_flag():
    """The new occurrence should start as not completed."""
    task = Task("Walk", duration_minutes=20, frequency="daily")
    task.mark_complete()
    nxt = task.next_occurrence()
    assert nxt is not None
    assert nxt.completed is False


def test_advance_recurring_tasks_replaces_completed_tasks():
    """advance_recurring_tasks() should roll forward completed recurring tasks."""
    from datetime import timedelta
    owner = Owner("Jordan")
    pet = Pet("Mochi", "dog")
    task = Task("Walk", duration_minutes=20, frequency="daily")
    original_due = task.due_date
    pet.add_task(task)
    owner.add_pet(pet)

    task.mark_complete()
    new_tasks = Scheduler(owner).advance_recurring_tasks()

    assert len(new_tasks) == 1
    assert new_tasks[0].completed is False
    assert new_tasks[0].due_date == original_due + timedelta(days=1)


def test_advance_recurring_tasks_skips_as_needed():
    """advance_recurring_tasks() should not replace as-needed tasks."""
    owner = Owner("Jordan")
    pet = Pet("Mochi", "dog")
    task = Task("Vet", duration_minutes=60, frequency="as-needed")
    task.mark_complete()
    pet.add_task(task)
    owner.add_pet(pet)

    new_tasks = Scheduler(owner).advance_recurring_tasks()
    assert len(new_tasks) == 0


# ---------------------------------------------------------------------------
# Conflict detection tests
# ---------------------------------------------------------------------------


def _make_conflict_plan(owner: Owner, pet: Pet, offset_minutes: int = 0) -> DailyPlan:
    """Helper: build a DailyPlan with two overlapping ScheduledTasks."""
    t1 = Task("Task A", duration_minutes=30)
    t2 = Task("Task B", duration_minutes=20)
    base = datetime.today().replace(hour=9, minute=0, second=0, microsecond=0)
    plan = DailyPlan(owner=owner)
    plan.scheduled.append(ScheduledTask(task=t1, pet=pet, start_time=base, reason="test"))
    plan.scheduled.append(
        ScheduledTask(task=t2, pet=pet, start_time=base + timedelta(minutes=offset_minutes), reason="test")
    )
    return plan


def test_detect_conflicts_finds_overlap():
    """detect_conflicts() should flag tasks with overlapping time windows."""
    owner = Owner("Jordan")
    pet = Pet("Rex", "dog")
    owner.add_pet(pet)
    plan = _make_conflict_plan(owner, pet, offset_minutes=0)  # exact same start

    warnings = Scheduler(owner).detect_conflicts(plan)
    assert len(warnings) >= 1
    assert "Conflict" in warnings[0]


def test_detect_conflicts_no_overlap_when_sequential():
    """detect_conflicts() should return no warnings for sequential (non-overlapping) tasks."""
    owner = Owner("Jordan")
    pet = Pet("Rex", "dog")
    owner.add_pet(pet)
    # offset = 30 min, so Task A (30 min) ends exactly when Task B starts
    plan = _make_conflict_plan(owner, pet, offset_minutes=30)

    warnings = Scheduler(owner).detect_conflicts(plan)
    assert warnings == []


def test_detect_conflicts_partial_overlap():
    """detect_conflicts() should catch a partial overlap (Task B starts mid-Task A)."""
    owner = Owner("Jordan")
    pet = Pet("Rex", "dog")
    owner.add_pet(pet)
    # Task A: 9:00–9:30, Task B starts at 9:15 → overlap
    plan = _make_conflict_plan(owner, pet, offset_minutes=15)

    warnings = Scheduler(owner).detect_conflicts(plan)
    assert len(warnings) >= 1


def test_detect_conflicts_empty_plan():
    """detect_conflicts() should return no warnings for an empty plan."""
    owner = Owner("Jordan")
    owner.add_pet(Pet("Rex", "dog"))
    plan = DailyPlan(owner=owner)

    warnings = Scheduler(owner).detect_conflicts(plan)
    assert warnings == []


# ---------------------------------------------------------------------------
# Edge cases — chronological order, empty inputs, zero budget
# ---------------------------------------------------------------------------


def test_scheduled_tasks_are_in_chronological_order():
    """Scheduled tasks in the DailyPlan should be ordered by start_time ascending."""
    owner = Owner("Jordan", available_minutes=120)
    pet = Pet("Mochi", "dog")
    # Add tasks in random priority/duration order
    pet.add_task(Task("Walk",    duration_minutes=30, priority="high"))
    pet.add_task(Task("Feed",    duration_minutes=10, priority="high"))
    pet.add_task(Task("Play",    duration_minutes=20, priority="medium"))
    pet.add_task(Task("Groom",   duration_minutes=15, priority="low"))
    owner.add_pet(pet)

    plan = Scheduler(owner, start_hour=8).build_plan()
    times = [st.start_time for st in plan.scheduled]
    assert times == sorted(times), "Scheduled tasks must be in ascending start_time order"


def test_owner_with_no_pets_produces_empty_plan():
    """An owner with no pets should result in an empty scheduled plan."""
    owner = Owner("Jordan", available_minutes=120)
    plan = Scheduler(owner).build_plan()
    assert plan.scheduled == []
    assert plan.skipped == []


def test_pet_with_no_tasks_does_not_break_scheduling():
    """A pet with an empty task list should not interfere with other pets' scheduling."""
    owner = Owner("Jordan", available_minutes=60)
    empty_pet = Pet("Noodle", "cat")           # no tasks
    active_pet = Pet("Mochi", "dog")
    active_pet.add_task(Task("Walk", duration_minutes=20, priority="high"))
    owner.add_pet(empty_pet)
    owner.add_pet(active_pet)

    plan = Scheduler(owner).build_plan()
    assert len(plan.scheduled) == 1
    assert plan.scheduled[0].task.title == "Walk"


def test_zero_available_minutes_skips_all_tasks():
    """Owner with available_minutes=0 should have every task skipped."""
    owner = Owner("Jordan", available_minutes=0)
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", duration_minutes=30, priority="high"))
    pet.add_task(Task("Feed", duration_minutes=5,  priority="high"))
    owner.add_pet(pet)

    plan = Scheduler(owner).build_plan()
    assert plan.scheduled == []
    assert len(plan.skipped) == 2


def test_sort_by_time_on_empty_list_returns_empty():
    """sort_by_time() on an empty list should return an empty list without error."""
    owner = Owner("Jordan")
    owner.add_pet(Pet("Mochi", "dog"))
    result = Scheduler(owner).sort_by_time([])
    assert result == []


def test_filter_tasks_with_nonexistent_pet_returns_empty():
    """filter_tasks() with a pet name that doesn't exist should return an empty list."""
    owner = Owner("Jordan")
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", duration_minutes=20))
    owner.add_pet(pet)

    result = Scheduler(owner).filter_tasks(pet_name="Ghost")
    assert result == []


def test_filter_tasks_pet_name_is_case_insensitive():
    """filter_tasks() should match pet names regardless of case."""
    owner = Owner("Jordan")
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", duration_minutes=20))
    owner.add_pet(pet)

    lower = Scheduler(owner).filter_tasks(pet_name="mochi")
    upper = Scheduler(owner).filter_tasks(pet_name="MOCHI")
    assert len(lower) == 1
    assert len(upper) == 1


def test_single_task_exactly_fills_budget_is_scheduled():
    """A task whose duration equals available_minutes exactly should be scheduled."""
    owner = Owner("Jordan", available_minutes=45)
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Long walk", duration_minutes=45, priority="high"))
    owner.add_pet(pet)

    plan = Scheduler(owner).build_plan()
    assert len(plan.scheduled) == 1
    assert plan.total_minutes == 45
    assert plan.skipped == []


def test_all_tasks_same_priority_scheduled_shortest_first():
    """When priorities are equal, shorter tasks should be scheduled before longer ones."""
    owner = Owner("Jordan", available_minutes=120)
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Long",   duration_minutes=40, priority="medium"))
    pet.add_task(Task("Short",  duration_minutes=10, priority="medium"))
    pet.add_task(Task("Medium", duration_minutes=25, priority="medium"))
    owner.add_pet(pet)

    plan = Scheduler(owner).build_plan()
    durations = [st.task.duration_minutes for st in plan.scheduled]
    assert durations == sorted(durations), "Equal-priority tasks should be ordered shortest-first"
