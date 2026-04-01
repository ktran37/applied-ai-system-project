import streamlit as st

# Step 1: import the logic layer directly
from pawpal_system import Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")
st.caption("Pet care planning assistant")

# ---------------------------------------------------------------------------
# Application "memory" via st.session_state
# The Owner object lives here so it survives Streamlit reruns.
# ---------------------------------------------------------------------------

if "owner" not in st.session_state:
    default_owner = Owner(name="Jordan", available_minutes=90)
    mochi = Pet(name="Mochi", species="dog", age_years=3.0)
    mochi.add_task(Task("Morning walk", duration_minutes=30, priority="high",   frequency="daily"))
    mochi.add_task(Task("Breakfast",    duration_minutes=10, priority="high",   frequency="daily"))
    mochi.add_task(Task("Playtime",     duration_minutes=20, priority="medium", frequency="daily"))
    mochi.add_task(Task("Brushing",     duration_minutes=15, priority="low",    frequency="weekly"))
    default_owner.add_pet(mochi)
    st.session_state.owner = default_owner
    st.session_state.start_hour = 8

owner: Owner = st.session_state.owner

# ---------------------------------------------------------------------------
# Owner settings
# ---------------------------------------------------------------------------
st.subheader("Owner")
col1, col2, col3 = st.columns(3)
with col1:
    owner.name = st.text_input("Your name", value=owner.name)
with col2:
    owner.available_minutes = int(st.number_input(
        "Time available today (min)", min_value=0, max_value=1440, value=owner.available_minutes, step=10,
    ))
with col3:
    st.session_state.start_hour = st.slider(
        "Day starts at (hour)", min_value=5, max_value=12, value=st.session_state.start_hour,
    )

st.divider()

# ---------------------------------------------------------------------------
# Pet management
# ---------------------------------------------------------------------------
st.subheader("Pets & Tasks")

with st.expander("Add a pet"):
    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        new_pet_name = st.text_input("Pet name", key="new_pet_name")
    with pc2:
        new_pet_species = st.selectbox("Species", ["dog", "cat", "rabbit", "bird", "other"], key="new_pet_species")
    with pc3:
        new_pet_age = st.number_input("Age (years)", min_value=0.0, max_value=30.0, value=1.0, step=0.5, key="new_pet_age")
    if st.button("Add pet"):
        if new_pet_name.strip():
            owner.add_pet(Pet(name=new_pet_name.strip(), species=new_pet_species, age_years=float(new_pet_age)))
            st.rerun()
        else:
            st.warning("Please enter a pet name.")

for pi, pet in enumerate(owner.pets):
    with st.expander(f"🐾 {pet.name} the {pet.species}", expanded=True):
        if st.button(f"Remove {pet.name}", key=f"remove_pet_{pi}"):
            owner.pets.pop(pi)
            st.rerun()

        st.markdown("**Tasks:**")
        if pet.tasks:
            for ti, task in enumerate(pet.tasks):
                tc1, tc2, tc3, tc4, tc5 = st.columns([3, 2, 2, 2, 1])
                label = f"~~{task.title}~~" if task.completed else task.title
                tc1.markdown(label)
                tc2.write(f"{task.duration_minutes} min · {task.frequency}")
                tc3.write(task.priority)
                tc4.write(f"due {task.due_date}")
                if tc5.button("✕", key=f"rm_task_{pi}_{ti}"):
                    pet.tasks.pop(ti)
                    st.rerun()
        else:
            st.caption("No tasks yet.")

        st.markdown("**Add a task:**")
        ac1, ac2, ac3, ac4 = st.columns([3, 2, 2, 2])
        with ac1:
            t_title = st.text_input("Title", key=f"t_title_{pi}", value="New task")
        with ac2:
            t_dur = st.number_input("Duration (min)", min_value=1, max_value=240, value=15, key=f"t_dur_{pi}")
        with ac3:
            t_pri = st.selectbox("Priority", ["low", "medium", "high"], index=1, key=f"t_pri_{pi}")
        with ac4:
            t_freq = st.selectbox("Frequency", ["daily", "weekly", "as-needed"], key=f"t_freq_{pi}")

        if st.button("Add task", key=f"add_task_{pi}"):
            pet.add_task(Task(title=t_title, duration_minutes=int(t_dur), priority=t_pri, frequency=t_freq))
            st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Smart task overview — sorted by duration using Scheduler.sort_by_time()
# ---------------------------------------------------------------------------
scheduler = Scheduler(owner=owner, start_hour=st.session_state.start_hour)
all_tasks = owner.get_all_tasks()

if all_tasks:
    with st.expander("📋 All tasks sorted by duration (shortest first)"):
        sorted_tasks = scheduler.sort_by_time(all_tasks)
        task_rows = [
            {
                "Task": t.title,
                "Duration (min)": t.duration_minutes,
                "Priority": t.priority,
                "Frequency": t.frequency,
                "Status": "✓ done" if t.completed else "○ pending",
            }
            for t in sorted_tasks
        ]
        st.table(task_rows)

st.divider()

# ---------------------------------------------------------------------------
# Generate schedule
# ---------------------------------------------------------------------------
st.subheader("Generate Schedule")

if st.button("Build daily plan", type="primary"):
    if not owner.get_pending_tasks():
        st.warning("Add at least one pending task before generating a plan.")
    else:
        plan = scheduler.build_plan()

        # ── Conflict detection ────────────────────────────────────────────
        conflicts = scheduler.detect_conflicts(plan)
        if conflicts:
            st.error(f"⚠️ {len(conflicts)} scheduling conflict(s) detected:")
            for w in conflicts:
                st.warning(w)

        # ── Summary banner ────────────────────────────────────────────────
        st.success(
            f"Plan for **{owner.name}** — {plan.total_minutes} min scheduled "
            f"out of {owner.available_minutes} min available."
        )

        # ── Scheduled tasks ───────────────────────────────────────────────
        st.markdown("### Scheduled Tasks")
        for st_task in plan.scheduled:
            with st.container(border=True):
                c1, c2 = st.columns([2, 3])
                c1.markdown(f"**{st_task.task.title}**")
                c1.caption(f"{st_task.pet.name} · {st_task.time_range()}")
                badge = {"high": "🔴", "medium": "🟡", "low": "🟢"}[st_task.task.priority]
                c2.caption(f"{badge} {st_task.reason}")

        # ── Skipped tasks ─────────────────────────────────────────────────
        if plan.skipped:
            st.markdown("### Skipped Tasks")
            for task, pet, reason in plan.skipped:
                with st.container(border=True):
                    c1, c2 = st.columns([2, 3])
                    c1.markdown(f"~~{task.title}~~ ({pet.name})")
                    c2.caption(reason)

        st.session_state.last_plan = plan

# ---------------------------------------------------------------------------
# Recurring task rollover
# ---------------------------------------------------------------------------
if owner.get_all_tasks():
    completed_recurring = [
        t for pet in owner.pets
        for t in pet.tasks
        if t.completed and t.frequency != "as-needed"
    ]
    if completed_recurring:
        st.divider()
        st.subheader("Recurring Task Rollover")
        st.caption(
            f"{len(completed_recurring)} completed recurring task(s) can be rolled over to tomorrow."
        )
        if st.button("Roll over recurring tasks to next occurrence"):
            new_tasks = scheduler.advance_recurring_tasks()
            st.success(f"✅ {len(new_tasks)} task(s) rolled forward:")
            for t in new_tasks:
                st.write(f"  • **{t.title}** → now due {t.due_date}")
            st.rerun()
