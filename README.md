# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Smarter Scheduling

The scheduler includes four algorithmic improvements beyond basic priority ordering:

| Feature | Method | What it does |
|---|---|---|
| **Sorting** | `Scheduler.sort_by_time(tasks)` | Returns tasks sorted ascending by `duration_minutes` using a `lambda` key, so the lightest work items are always visible first |
| **Filtering** | `Scheduler.filter_tasks(pet_name, completed)` | Returns `(task, pet)` pairs filtered by pet name and/or completion status — combinable in any way |
| **Recurring tasks** | `Task.next_occurrence()` + `Scheduler.advance_recurring_tasks()` | When a `daily`/`weekly` task is marked complete, `next_occurrence()` creates a fresh copy with `due_date + timedelta` and `advance_recurring_tasks()` swaps it in place across all pets |
| **Conflict detection** | `Scheduler.detect_conflicts(plan)` | Performs a pairwise O(n²) overlap check on all scheduled time windows and returns warning strings (rather than raising exceptions) for any pair whose intervals intersect |

## Testing PawPal+

Run the full test suite from the project root:

```bash
python -m pytest
```

Or with verbose output to see each test name:

```bash
python -m pytest tests/test_pawpal.py -v
```

### What the tests cover

| Category | # Tests | What is verified |
|---|---|---|
| **Task lifecycle** | 3 | `mark_complete()` changes status; completed tasks are excluded from the plan; `reset()` restores pending state |
| **Pet task management** | 4 | `add_task()` increases count; all added tasks appear; `remove_task()` shrinks list; `pending_tasks()` excludes completed |
| **Owner aggregation** | 4 | `add_pet()` registers pets; `get_all_tasks()` merges across pets; `get_pending_tasks()` skips completed; `find_pet()` is case-insensitive |
| **Core scheduling** | 5 | Plan built from owner's pets; time budget enforced; high priority scheduled first; completed tasks skipped; tasks excluded correctly |
| **Sorting** | 2 | Tasks sorted ascending by `duration_minutes`; empty list handled |
| **Filtering** | 4 | Filter by pet name; filter by status; combined filters; non-existent pet returns empty |
| **Recurring tasks** | 6 | Daily advances +1 day; weekly advances +7 days; as-needed returns None; next occurrence resets `completed`; `advance_recurring_tasks()` swaps tasks in place; as-needed tasks not replaced |
| **Conflict detection** | 4 | Exact overlap flagged; sequential tasks (no gap) pass; partial overlap flagged; empty plan returns no warnings |
| **Edge cases** | 8 | Chronological start-time order; no pets → empty plan; pet with no tasks; `available_minutes=0` skips all; empty sort list; non-existent pet filter; case-insensitive pet filter; exact budget fill |

### Confidence level

★★★★☆ (4/5)

The scheduler's core invariants — priority ordering, time budget enforcement, recurring task rollover, and conflict detection — are all covered with both happy-path and edge-case tests. The main gap is integration-level testing of the Streamlit UI layer (which is not yet tested) and multi-pet parallel scheduling scenarios.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.
