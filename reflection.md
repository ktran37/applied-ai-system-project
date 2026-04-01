# PawPal+ Project Reflection

## 1. System Design

**Core user actions**

Three things a user needs to be able to do with PawPal+:

1. **Enter owner and pet information** — provide a name, species, and the amount of time available for pet care today. This sets the constraints the scheduler works within.
2. **Add and manage care tasks** — create tasks with a title, duration, priority level (high / medium / low), and recurrence frequency, and remove tasks that are no longer needed.
3. **Generate and view a daily care plan** — ask the system to schedule the tasks, then see which tasks were chosen, in what order, with what time slots, and why — as well as which tasks were skipped and the reason. Conflict warnings are surfaced immediately if two tasks overlap.

---

**a. Initial design**

The initial UML included four core classes:

- **Owner** — holds the pet owner's name and the total minutes available for pet care that day. It acts as the source of the time constraint fed into the scheduler.
- **Pet** — holds the animal's name, species, and age. In the initial design, pet was mostly a label passed to the scheduler alongside a flat task list.
- **Task** — a single care activity with a title, duration in minutes, and a priority level (`low`, `medium`, or `high`). Initially a passive data object with no logic.
- **Scheduler** — the only class with real behavior. It received an Owner, a Pet, and a list of Tasks, then produced a **DailyPlan** containing ordered **ScheduledTask** objects (each with a start time and a human-readable reason) plus a list of skipped tasks with explanations.

**b. Design changes**

Several significant changes emerged during implementation:

1. **Pet became the owner of tasks** — originally tasks were a flat list passed directly to the Scheduler. Moving `tasks: list[Task]` onto `Pet` made ownership clear, enabled `pet.pending_tasks()`, and made the multi-pet scenario natural: the Scheduler just asks the Owner for all pets, then each pet for its tasks.
2. **Owner became a container for pets** — adding `pets: list[Pet]` with `add_pet()` and `get_all_tasks()` meant the Scheduler needed only one entry point (`owner`), simplifying the constructor from `Scheduler(owner, pet, tasks)` to `Scheduler(owner)`.
3. **Task gained lifecycle state** — adding `completed`, `due_date`, `frequency`, `mark_complete()`, and `next_occurrence()` transformed Task from a passive record into an active domain object that participates in recurring task rollover.
4. **DailyPlan grew a `skipped` list and a `pet` reference per entry** — the original design stored only scheduled tasks. The UI needed to explain skipped tasks, and with multiple pets, each `ScheduledTask` needed to carry its `pet` reference.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers two constraints:

1. **Available time** — the owner's `available_minutes` acts as a hard budget. No task is added once the budget is exhausted.
2. **Priority** — tasks are ranked `high > medium > low`. Within the same priority level, shorter tasks are scheduled first so that more tasks fit in the window.

Priority was treated as the primary constraint because missing a high-priority task (medication, feeding) has a direct impact on the pet's wellbeing, whereas running out of time simply means lower-priority items are deferred.

**b. Tradeoffs**

The scheduler is greedy: it processes tasks in sorted order and skips any task that does not fit in the remaining time, even if a different ordering might squeeze in more total tasks. For example, two medium-priority 15-minute tasks will both be skipped if 25 minutes remain and a single high-priority 30-minute task is processed first.

This tradeoff is reasonable here because correctness of priority order matters more than maximizing the number of tasks completed. A pet owner would rather finish every high-priority item and skip a low-priority one than reorder tasks to fit in one extra low-priority activity at the expense of a high-priority one.

**Conflict detection tradeoff**

The conflict detector uses a lightweight O(n²) pairwise check: it compares every pair of scheduled tasks and flags any two whose time windows overlap (`a.start_time < b.end_time and b.start_time < a.end_time`). This approach checks only exact time-window overlap and does not account for soft constraints like "Mochi needs a 10-minute rest between high-energy tasks." The advantage is simplicity — it returns plain warning strings without crashing the program, so the UI can surface conflicts gracefully. The disadvantage is that it does not prevent conflicts; it only reports them after the fact. A future improvement could integrate conflict checking directly into `build_plan()` to reject conflicting slots before they are assigned.

---

## 3. AI Collaboration

**a. How you used AI**

AI was used as a collaborative tool — not a code generator — at every phase:

- **Design phase** — described the scenario to the AI and asked for a class breakdown. The AI suggested separating `Owner`, `Pet`, `Task`, and `Scheduler`. The suggestion was reviewed against the scenario requirements before any code was written. One suggestion (keeping tasks on a global list rather than on each Pet) was rejected because it would have made multi-pet queries awkward.
- **Skeleton generation** — used AI to produce class stubs with empty method bodies, then filled in the logic manually. This kept the design in the driver's seat: the stubs matched the UML, not the other way around.
- **Algorithmic implementation** — used concrete, scenario-specific prompts like "given `Owner.available_minutes` and a sorted task list, write a greedy scheduler that stops when the budget runs out." Vague prompts like "write a scheduler" returned generic code that didn't fit the data model.
- **Testing** — asked AI to generate test cases for each invariant, then read every test before saving it. Several tests were modified or rejected (see 3b).
- **UI wiring** — used AI to translate domain objects into Streamlit widgets, reviewing each component to confirm it called the right method rather than rebuilding objects from dicts.

**Which AI features were most effective**

The most effective pattern was *providing the existing class signatures as context* before asking for new code. When the AI could see `Pet.add_task()` and `Owner.get_pending_tasks()`, the generated `Scheduler.build_plan()` called those methods correctly instead of inventing new ones. Without that context, suggestions often introduced redundant state.

Asking the AI to *explain* generated code before accepting it ("what does this lambda do?", "why is `id(task)` used as the dict key here?") caught several cases where the implementation was technically correct but fragile or hard to test.

**b. Judgment and verification**

Two examples of AI suggestions that were modified:

1. **Test assertion gap** — the AI's first version of `test_tasks_exceeding_time_are_skipped` only checked `len(plan.skipped) == 1` without verifying *which* task was skipped. That test would pass even if the wrong task was dropped. The explicit assertion on `plan.skipped[0][0].title` was added after reading the test and noticing the gap.

2. **Recurring task design** — the AI initially suggested that `mark_complete()` should automatically append a new Task to the pet's list as a side effect. This was rejected because it would make `mark_complete()` do two things (set a flag *and* mutate a list it doesn't own), breaking single-responsibility. Instead, `next_occurrence()` was made a pure function that returns a new Task, and `advance_recurring_tasks()` on the Scheduler handles the list mutation separately. This made both methods easier to test independently.

**How separate chat sessions helped**

Keeping algorithmic planning in its own session (separate from core implementation) prevented context drift. When asking "what edge cases exist for conflict detection?", the AI's answers stayed focused on the scheduling domain rather than mixing in UI or test concerns from earlier in the conversation. Each session started with a clean description of the current problem, which consistently produced more targeted suggestions.

**Lead architect role**

The key insight from working with AI on this project is that the human's job is to hold the *design invariants* that the AI cannot infer: which class should own which data, what the naming conventions are, what counts as "done" for a test. The AI is fast at generating code that compiles; the human is responsible for ensuring it fits the architecture. Every time AI suggestions were accepted without reading them, a test was weaker or a method did more than it should. Every time the class diagram was consulted before accepting a suggestion, the result was cleaner.

---

## 4. Testing and Verification

**a. What you tested**

39 automated tests in `tests/test_pawpal.py` across 9 categories:

1. **Task lifecycle** — `mark_complete()` changes status; completed tasks excluded from plan; `reset()` restores pending state.
2. **Pet task management** — `add_task()` increases count; all tasks stored correctly; `remove_task()` shrinks list; `pending_tasks()` excludes completed.
3. **Owner aggregation** — `add_pet()` registers pets; `get_all_tasks()` merges across all pets; `get_pending_tasks()` skips completed; `find_pet()` is case-insensitive.
4. **Core scheduling** — plan built from owner's pets automatically; time budget enforced; high priority scheduled first; completed tasks skipped.
5. **Sorting** — tasks sorted ascending by `duration_minutes`; empty list returns empty without error.
6. **Filtering** — by pet name; by completion status; combined filters; non-existent pet returns empty; case-insensitive pet name matching.
7. **Recurring tasks** — daily advances +1 day; weekly advances +7 days; as-needed returns None; next occurrence resets `completed`; `advance_recurring_tasks()` swaps tasks in place; as-needed tasks are not replaced.
8. **Conflict detection** — exact overlap flagged; sequential (touching) slots pass; partial overlap flagged; empty plan returns no warnings.
9. **Edge cases** — scheduled tasks are in chronological `start_time` order; no pets produces empty plan; pet with no tasks doesn't break scheduling; `available_minutes=0` skips all tasks; exact budget boundary is scheduled not skipped; equal-priority tasks ordered shortest-first.

**b. Confidence**

★★★★☆ (4/5) — The scheduler's core invariants are all covered with both happy-path and edge-case tests, including several boundary conditions. The main gaps are:

- Integration-level testing of the Streamlit UI layer (widget interactions are not tested)
- Concurrent modification scenarios (adding a task while a plan is being displayed)
- Performance tests for owners with very large task lists (the O(n²) conflict detector would slow down above ~100 tasks)

---

## 5. Reflection

**a. What went well**

The clean separation between the domain model (`pawpal_system.py`) and the UI (`app.py`) was the most valuable structural decision. Because `Scheduler.build_plan()` returns a plain `DailyPlan` dataclass with no Streamlit dependency, all 39 tests run in milliseconds with no browser, no server, and no mocking. The UI layer stayed thin — it only iterates and renders, never computes — which made the smart features (sort view, conflict warnings, recurring rollover) easy to add in the final phase without touching the logic at all.

**b. What you would improve**

Two improvements would make the biggest difference:

1. **Task dependency ordering** — the scheduler currently has no concept of "feeding must happen before medication." Adding an optional `depends_on: str` field to `Task` and a topological sort pass before the greedy selection would handle most real-world sequencing requirements without a full constraint solver.
2. **Smarter time-fitting** — the greedy algorithm skips a task as soon as it doesn't fit, even if a shorter lower-priority task could have used that time. A knapsack-style optimization for the remaining budget would increase utilization, at the cost of no longer guaranteeing strict priority order for the last few minutes of the day.

**c. Key takeaway**

The most important lesson was that *design work cannot be delegated to AI*. The AI was fast and helpful at generating code that fit a well-specified design, but every time the design itself was left vague, the suggestions introduced inconsistencies that had to be untangled later. The value of sketching the UML first — even roughly — was not the diagram itself but the thinking it forced: what does each class *own*, what does it *know*, and what does it *do*? Once those questions were answered, the AI could fill in the implementation details quickly and accurately. Without them, it generated plausible-looking code that solved a slightly different problem.
