"""Demo script — run with: python main.py"""

from datetime import datetime
from pawpal_system import DailyPlan, Owner, Pet, ScheduledTask, Scheduler, Task

# ---------------------------------------------------------------------------
# Setup: owner with two pets and tasks added intentionally out of order
# ---------------------------------------------------------------------------

owner = Owner(name="Jordan", available_minutes=90)

mochi = Pet(name="Mochi", species="dog", age_years=3)
mochi.add_task(Task("Brushing",     duration_minutes=15, priority="low",    frequency="weekly"))
mochi.add_task(Task("Morning walk", duration_minutes=30, priority="high",   frequency="daily"))
mochi.add_task(Task("Fetch / play", duration_minutes=20, priority="medium", frequency="daily"))
mochi.add_task(Task("Breakfast",    duration_minutes=10, priority="high",   frequency="daily"))

noodle = Pet(name="Noodle", species="cat", age_years=5)
noodle.add_task(Task("Interactive play", duration_minutes=15, priority="medium", frequency="daily"))
noodle.add_task(Task("Litter box",       duration_minutes=5,  priority="high",   frequency="daily"))
noodle.add_task(Task("Feeding",          duration_minutes=5,  priority="high",   frequency="daily"))

owner.add_pet(mochi)
owner.add_pet(noodle)

scheduler = Scheduler(owner=owner, start_hour=8)

# ---------------------------------------------------------------------------
# 1. Normal daily plan
# ---------------------------------------------------------------------------
print("=" * 55)
print("1. DAILY PLAN")
print("=" * 55)
plan = scheduler.build_plan()
print(plan.summary())

# ---------------------------------------------------------------------------
# 2. Sorting — tasks ordered by duration (shortest first)
# ---------------------------------------------------------------------------
print("\n" + "=" * 55)
print("2. SORTING: all tasks by duration (shortest first)")
print("=" * 55)
all_tasks = owner.get_all_tasks()
sorted_tasks = scheduler.sort_by_time(all_tasks)
for t in sorted_tasks:
    print(f"  {t.duration_minutes:3} min  {t.title}")

# ---------------------------------------------------------------------------
# 3. Filtering — pending tasks for Mochi only
# ---------------------------------------------------------------------------
print("\n" + "=" * 55)
print("3. FILTERING: pending tasks for Mochi")
print("=" * 55)
mochi_pending = scheduler.filter_tasks(pet_name="Mochi", completed=False)
for task, pet in mochi_pending:
    print(f"  [{pet.name}] {task.title} ({task.duration_minutes} min, {task.priority})")

# ---------------------------------------------------------------------------
# 4. Recurring tasks — mark daily tasks complete, advance to next occurrence
# ---------------------------------------------------------------------------
print("\n" + "=" * 55)
print("4. RECURRING TASKS: advance daily tasks after completion")
print("=" * 55)
# Mark all scheduled tasks complete
for st in plan.scheduled:
    st.task.mark_complete()

print("  Before advance_recurring_tasks():")
for pet in owner.pets:
    for t in pet.tasks:
        status = "✓ completed" if t.completed else "○ pending"
        print(f"    [{pet.name}] {t.title} — {status}, due {t.due_date}")

new_tasks = scheduler.advance_recurring_tasks()
print(f"\n  {len(new_tasks)} task(s) rolled forward to next occurrence:")
for t in new_tasks:
    print(f"    {t.title} — now due {t.due_date} (frequency: {t.frequency})")

# ---------------------------------------------------------------------------
# 5. Conflict detection — manually place two overlapping tasks
# ---------------------------------------------------------------------------
print("\n" + "=" * 55)
print("5. CONFLICT DETECTION: two tasks at the same start time")
print("=" * 55)
conflict_owner = Owner(name="Test", available_minutes=60)
pet_a = Pet("Rex", "dog")
conflict_owner.add_pet(pet_a)

t1 = Task("Walk",     duration_minutes=30, priority="high")
t2 = Task("Grooming", duration_minutes=20, priority="medium")
overlap_time = datetime.today().replace(hour=9, minute=0, second=0, microsecond=0)

# Manually inject both tasks at the same start time to force a conflict
conflict_plan = DailyPlan(owner=conflict_owner)
conflict_plan.scheduled.append(ScheduledTask(task=t1, pet=pet_a, start_time=overlap_time, reason="demo"))
conflict_plan.scheduled.append(ScheduledTask(task=t2, pet=pet_a, start_time=overlap_time, reason="demo"))

conflict_checker = Scheduler(conflict_owner)
warnings = conflict_checker.detect_conflicts(conflict_plan)
if warnings:
    for w in warnings:
        print(f"  {w}")
else:
    print("  No conflicts detected.")
