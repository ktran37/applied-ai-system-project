# PawPal+ UML Class Diagram — Final

> Updated to match the final implementation in `pawpal_system.py`.

```mermaid
classDiagram
    class Task {
        +str title
        +int duration_minutes
        +Priority priority
        +str description
        +Frequency frequency
        +bool completed
        +date due_date
        +mark_complete() None
        +reset() None
        +next_occurrence() Task
        +__str__() str
    }

    class Pet {
        +str name
        +str species
        +float age_years
        +str notes
        +list~Task~ tasks
        +add_task(task: Task) None
        +remove_task(title: str) None
        +pending_tasks() list~Task~
        +__str__() str
    }

    class Owner {
        +str name
        +int available_minutes
        +list~Pet~ pets
        +add_pet(pet: Pet) None
        +get_all_tasks() list~Task~
        +get_pending_tasks() list~Task~
        +find_pet(name: str) Pet
        +__str__() str
    }

    class ScheduledTask {
        +Task task
        +Pet pet
        +datetime start_time
        +str reason
        +end_time() datetime
        +time_range() str
        +__str__() str
    }

    class DailyPlan {
        +Owner owner
        +list~ScheduledTask~ scheduled
        +list~tuple~ skipped
        +total_minutes() int
        +summary() str
    }

    class Scheduler {
        +Owner owner
        +int start_hour
        +build_plan() DailyPlan
        +sort_by_time(tasks: list~Task~) list~Task~
        +filter_tasks(pet_name, completed) list~tuple~
        +advance_recurring_tasks() list~Task~
        +detect_conflicts(plan: DailyPlan) list~str~
        -_explain(task: Task, remaining: int) str
    }

    Owner "1" *-- "0..*" Pet : owns
    Pet "1" *-- "0..*" Task : has
    Scheduler --> Owner : queries
    Scheduler ..> DailyPlan : creates
    DailyPlan --> Owner : references
    DailyPlan "1" *-- "0..*" ScheduledTask : contains
    ScheduledTask --> Task : wraps
    ScheduledTask --> Pet : belongs to
```

## Design changes from initial UML

| Area | Initial | Final |
|---|---|---|
| `Task` | title, duration, priority | + `frequency`, `completed`, `due_date`, `mark_complete()`, `reset()`, `next_occurrence()` |
| `Pet` | name, species, age | + `tasks` list, `add_task()`, `remove_task()`, `pending_tasks()` — Pet now *owns* its tasks |
| `Owner` | name, available_minutes | + `pets` list, `add_pet()`, `get_all_tasks()`, `get_pending_tasks()`, `find_pet()` |
| `Scheduler` | `build_plan(tasks)` takes a task list | `build_plan()` queries owner directly; + `sort_by_time()`, `filter_tasks()`, `advance_recurring_tasks()`, `detect_conflicts()` |
| `DailyPlan` | single list of tasks | + `skipped` list (Task, Pet, reason tuples); + `summary()` |
| `ScheduledTask` | task + start_time + reason | + `pet` field so the plan knows which pet each task belongs to |

## Relationships

| Relationship | Type | Description |
|---|---|---|
| `Owner` ◆ `Pet` | Composition | Pets are created and managed through the Owner |
| `Pet` ◆ `Task` | Composition | Tasks live on the Pet, not as free-floating objects |
| `Scheduler` → `Owner` | Dependency | Scheduler calls `owner.get_pending_tasks()` to build the plan |
| `Scheduler` ‥▷ `DailyPlan` | Creation | `build_plan()` instantiates and returns a DailyPlan |
| `DailyPlan` ◆ `ScheduledTask` | Composition | ScheduledTasks only exist within a DailyPlan |
| `ScheduledTask` → `Task` / `Pet` | Association | Wraps a Task and records which Pet it belongs to |
