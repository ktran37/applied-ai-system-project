# PawPal+ Project Reflection

## 1. System Design

**Core user actions**

Three things a user needs to be able to do with PawPal+:

1. **Enter owner and pet information** — provide a name, species, and the amount of time available for pet care today. This sets the constraints the scheduler works within.
2. **Add and manage care tasks** — create tasks with a title, duration, and priority level (high / medium / low), and remove tasks that are no longer needed.
3. **Generate and view a daily care plan** — ask the system to schedule the tasks, then see which tasks were chosen, in what order, with what time slots, and why — as well as which tasks were skipped and the reason.

---

**a. Initial design**

The initial UML included four core classes:

- **Owner** — holds the pet owner's name and the total minutes available for pet care that day. It acts as the source of the time constraint fed into the scheduler.
- **Pet** — holds the animal's name, species, age, and a reference to its Owner. It exists mainly as context for the plan (e.g., labeling output) and can be extended with species-specific rules later.
- **Task** — a single care activity with a title, duration in minutes, and a priority level (`low`, `medium`, or `high`). Tasks are passive data objects with no logic.
- **Scheduler** — the only class with real behavior. It receives an Owner, a Pet, and a list of Tasks, then produces a **DailyPlan** containing ordered **ScheduledTask** objects (each with a start time and a human-readable reason) plus a list of skipped tasks with explanations.

**b. Design changes**

The original sketch treated `DailyPlan` as just a list. During implementation it became clear that the plan needed to carry the skipped tasks too, so `DailyPlan` became a proper dataclass with both a `scheduled` list and a `skipped` list. This made the UI much easier to write — the Streamlit layer just iterates both lists without any extra filtering logic.

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

AI was used throughout the project:

- **Design phase** — asked AI to suggest a clean class breakdown given the scenario, then reviewed whether the responsibilities felt right before writing any code.
- **Implementation** — used AI to generate the initial class stubs and scheduling algorithm, then read through the logic to confirm it matched the intended behavior.
- **Testing** — asked AI to write pytest cases covering the key invariants (priority order, time budget, sequential time slots, empty input), then manually checked each test to make sure it was actually asserting the right thing and not just passing trivially.
- **UI wiring** — used AI to translate the domain objects into Streamlit widgets, reviewing the layout to ensure it matched the workflow described in the README.

The most helpful prompts were concrete and scenario-specific: "given an Owner with available_minutes and a list of Tasks with priorities, write a scheduler that picks tasks greedily by priority" produced much more usable output than open-ended requests.

**b. Judgment and verification**

The AI's first version of the test `test_tasks_exceeding_time_are_skipped` only checked `len(plan.skipped) == 1` without verifying *which* task was skipped. That test would pass even if the wrong task was dropped. The assertion `plan.skipped[0][0].title == "Another long task"` was added manually after reading the test and noticing the gap. This is a good example of why generated tests need the same code-review discipline as generated implementation code.

---

## 4. Testing and Verification

**a. What you tested**

Eight behaviors were tested in [test_pawpal.py](test_pawpal.py) against `pawpal_system.py`:

1. High-priority tasks appear before medium, medium before low.
2. Tasks that exceed remaining time are skipped.
3. Total scheduled time never exceeds available time.
4. An empty task list produces an empty plan with no errors.
5. A single task that exactly fills the budget is scheduled (not skipped).
6. Consecutive scheduled tasks have contiguous time slots (no gaps or overlaps).
7. Skipped-task reasons contain a human-readable explanation.
8. The plan's `owner` and `pet` references point to the correct objects.

These tests matter because they cover the core scheduling invariants — correctness of ordering, budget enforcement, and output integrity — rather than just exercising happy-path inputs.

**b. Confidence**

Confidence in the current logic is high for the scenarios covered. Edge cases to test next:

- Two tasks with identical priority and identical duration (tie-breaking stability).
- A task whose duration exactly equals the remaining budget (boundary condition).
- An owner with `available_minutes = 0` (should produce an all-skipped plan immediately).
- Tasks with very large durations that exceed the full daily budget on their own.
- Duplicate task titles (ensure the scheduler does not conflate them).

---

## 5. Reflection

**a. What went well**

The clean separation between the domain model (`pawpal_system.py`) and the UI (`app.py`) worked well. Because `Scheduler.build_plan()` returns a plain `DailyPlan` dataclass with no Streamlit dependency, the logic could be tested in isolation with fast unit tests, and the UI layer stayed thin — it only iterates and renders, never computes.

**b. What you would improve**

The scheduler currently has no concept of task ordering constraints (e.g., "feeding must happen before medication"). A next iteration would add optional `depends_on` relationships between tasks so the scheduler respects sequencing, not just priority. The `Pet` class also has an unused `notes` field that could drive species-specific rule variations (e.g., cats need less walking time than dogs).

**c. Key takeaway**

Designing the data model before writing any logic — even just sketching the classes on paper — makes implementation significantly faster and the resulting code more testable. When the classes have clear, single responsibilities, the scheduler logic almost writes itself. Working with AI reinforced this: vague prompts produced vague code, but prompts that already specified the classes and their relationships produced code that needed only minor adjustments.
