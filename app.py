import os
import pathlib

import streamlit as st

from pawpal_system import Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")
st.caption("Pet care planning assistant")

DATA_FILE = "data.json"

# ---------------------------------------------------------------------------
# Session state initialisation — restore from data.json or seed defaults
# ---------------------------------------------------------------------------

if "owner" not in st.session_state:
    if pathlib.Path(DATA_FILE).exists():
        st.session_state.owner = Owner.load_from_json(DATA_FILE)
    else:
        default_owner = Owner(name="Jordan", available_minutes=90)
        mochi = Pet(name="Mochi", species="dog", age_years=3.0)
        mochi.add_task(Task("Morning walk", duration_minutes=30, priority="high", frequency="daily"))
        mochi.add_task(Task("Breakfast", duration_minutes=10, priority="high", frequency="daily"))
        mochi.add_task(Task("Playtime", duration_minutes=20, priority="medium", frequency="daily"))
        mochi.add_task(Task("Brushing", duration_minutes=15, priority="low", frequency="weekly"))
        default_owner.add_pet(mochi)
        st.session_state.owner = default_owner
    st.session_state.start_hour = 8
    st.session_state.use_weighted = False

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "agent" not in st.session_state:
    st.session_state.agent = None

owner: Owner = st.session_state.owner

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs(["🐾 Pets & Tasks", "📅 Schedule", "🤖 AI Assistant"])

# ===========================================================================
# TAB 1 — Pets & Tasks
# ===========================================================================

with tab1:
    # Owner settings
    st.subheader("Owner")
    col1, col2, col3 = st.columns(3)
    with col1:
        owner.name = st.text_input("Your name", value=owner.name)
    with col2:
        owner.available_minutes = int(
            st.number_input(
                "Time available today (min)",
                min_value=0,
                max_value=1440,
                value=owner.available_minutes,
                step=10,
            )
        )
    with col3:
        st.session_state.start_hour = st.slider(
            "Day starts at (hour)",
            min_value=5,
            max_value=12,
            value=st.session_state.start_hour,
        )

    st.divider()
    st.subheader("Pets & Tasks")

    with st.expander("Add a pet"):
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            new_pet_name = st.text_input("Pet name", key="new_pet_name")
        with pc2:
            new_pet_species = st.selectbox(
                "Species", ["dog", "cat", "rabbit", "bird", "other"], key="new_pet_species"
            )
        with pc3:
            new_pet_age = st.number_input(
                "Age (years)", min_value=0.0, max_value=30.0, value=1.0, step=0.5, key="new_pet_age"
            )
        if st.button("Add pet"):
            if new_pet_name.strip():
                owner.add_pet(
                    Pet(
                        name=new_pet_name.strip(),
                        species=new_pet_species,
                        age_years=float(new_pet_age),
                    )
                )
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
                t_dur = st.number_input(
                    "Duration (min)", min_value=1, max_value=240, value=15, key=f"t_dur_{pi}"
                )
            with ac3:
                t_pri = st.selectbox(
                    "Priority", ["low", "medium", "high"], index=1, key=f"t_pri_{pi}"
                )
            with ac4:
                t_freq = st.selectbox(
                    "Frequency", ["daily", "weekly", "as-needed"], key=f"t_freq_{pi}"
                )
            if st.button("Add task", key=f"add_task_{pi}"):
                pet.add_task(
                    Task(title=t_title, duration_minutes=int(t_dur), priority=t_pri, frequency=t_freq)
                )
                st.rerun()

    # Sorted task overview
    scheduler = Scheduler(owner=owner, start_hour=st.session_state.start_hour)
    all_tasks = owner.get_all_tasks()
    if all_tasks:
        st.divider()
        with st.expander("📋 All tasks sorted by duration (shortest first)"):
            sorted_tasks = scheduler.sort_by_time(all_tasks)
            st.table(
                [
                    {
                        "Task": t.title,
                        "Duration (min)": t.duration_minutes,
                        "Priority": t.priority,
                        "Frequency": t.frequency,
                        "Status": "✓ done" if t.completed else "○ pending",
                    }
                    for t in sorted_tasks
                ]
            )

# ===========================================================================
# TAB 2 — Schedule
# ===========================================================================

with tab2:
    scheduler2 = Scheduler(owner=owner, start_hour=st.session_state.start_hour)

    col_a, col_b = st.columns([3, 2])
    with col_b:
        st.session_state.use_weighted = st.toggle(
            "⚖️ Urgency weighting",
            value=st.session_state.use_weighted,
            help="Score = priority × (1 + 1/(days_until_due+1)). Overdue tasks jump ahead.",
        )

    if st.button("Build daily plan", type="primary"):
        if not owner.get_pending_tasks():
            st.warning("Add at least one pending task before generating a plan.")
        else:
            if st.session_state.use_weighted:
                plan = scheduler2.build_weighted_plan()
                st.info("⚖️ Using **urgency-weighted** scheduling.")
            else:
                plan = scheduler2.build_plan()

            conflicts = scheduler2.detect_conflicts(plan)
            if conflicts:
                st.error(f"⚠️ {len(conflicts)} scheduling conflict(s) detected:")
                for w in conflicts:
                    st.warning(w)

            st.success(
                f"Plan for **{owner.name}** — {plan.total_minutes} min scheduled "
                f"out of {owner.available_minutes} min available."
            )

            st.markdown("### Scheduled Tasks")
            for st_task in plan.scheduled:
                with st.container(border=True):
                    c1, c2 = st.columns([2, 3])
                    c1.markdown(f"**{st_task.task.title}**")
                    c1.caption(f"{st_task.pet.name} · {st_task.time_range()}")
                    badge = {"high": "🔴", "medium": "🟡", "low": "🟢"}[st_task.task.priority]
                    c2.caption(f"{badge} {st_task.reason}")

            if plan.skipped:
                st.markdown("### Skipped Tasks")
                for task, pet, reason in plan.skipped:
                    with st.container(border=True):
                        c1, c2 = st.columns([2, 3])
                        c1.markdown(f"~~{task.title}~~ ({pet.name})")
                        c2.caption(reason)

            st.session_state.last_plan = plan

    # Recurring task rollover
    all_tasks2 = owner.get_all_tasks()
    if all_tasks2:
        completed_recurring = [
            t for pet in owner.pets for t in pet.tasks if t.completed and t.frequency != "as-needed"
        ]
        if completed_recurring:
            st.divider()
            st.subheader("Recurring Task Rollover")
            st.caption(f"{len(completed_recurring)} completed recurring task(s) ready to roll over.")
            if st.button("Roll over recurring tasks to next occurrence"):
                new_tasks = scheduler2.advance_recurring_tasks()
                st.success(f"✅ {len(new_tasks)} task(s) rolled forward:")
                for t in new_tasks:
                    st.write(f"  • **{t.title}** → due {t.due_date}")
                st.rerun()

# ===========================================================================
# TAB 3 — AI Assistant
# ===========================================================================

with tab3:
    st.subheader("🤖 PawPal AI Assistant")
    st.caption(
        "Ask me to create routines, complete tasks, suggest care tips, or analyse your schedule. "
        "I use an agentic workflow — I plan, act, verify, and report back."
    )

    # Check for API key
    api_key_present = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    if not api_key_present:
        st.error(
            "⚠️ `ANTHROPIC_API_KEY` is not set. "
            "Add it to your environment or a `.env` file and restart the app."
        )
        st.code("export ANTHROPIC_API_KEY=your_key_here", language="bash")
        st.stop()

    # Lazy-initialise the agent (avoids creating Anthropic client when tab not visited)
    if st.session_state.agent is None:
        try:
            from ai_agent import PawPalAgent
            st.session_state.agent = PawPalAgent(owner=owner)
        except Exception as e:
            st.error(f"Failed to initialise AI agent: {e}")
            st.stop()

    agent = st.session_state.agent
    # Keep agent's owner reference in sync (owner may have been mutated in other tabs)
    agent.owner = owner

    # Chat history display
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                conf = msg.get("confidence", 0.5)
                bar_color = "green" if conf >= 0.8 else "orange" if conf >= 0.5 else "red"
                st.caption(f"Confidence: {conf:.0%}")
                if msg.get("tool_calls"):
                    with st.expander(f"🔧 {len(msg['tool_calls'])} tool call(s)"):
                        for tc in msg["tool_calls"]:
                            st.markdown(f"**`{tc['tool']}`**")
                            st.json(tc["input"], expanded=False)

    # Input
    col_input, col_reset = st.columns([5, 1])
    with col_reset:
        if st.button("Clear", help="Reset conversation"):
            st.session_state.chat_history = []
            agent.reset_conversation()
            st.rerun()

    user_input = st.chat_input("Ask PawPal AI something…")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("PawPal AI is thinking…"):
            try:
                response_text, confidence, tool_calls = agent.process_message(user_input)
            except Exception as e:
                response_text = f"Sorry, an error occurred: {e}"
                confidence = 0.0
                tool_calls = []

        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": response_text,
                "confidence": confidence,
                "tool_calls": tool_calls,
            }
        )
        # Auto-save after AI changes
        owner.save_to_json(DATA_FILE)
        st.rerun()

    # Suggested prompts for new users
    if not st.session_state.chat_history:
        st.markdown("**Try asking:**")
        examples = [
            "Set up a complete daily routine for my dog Mochi",
            "What tasks should I add for a new rabbit named Biscuit?",
            "Mark Mochi's morning walk as done and show me the updated schedule",
            "How many minutes of care does my daily plan require?",
        ]
        for ex in examples:
            if st.button(ex, key=f"ex_{ex[:20]}"):
                st.session_state.chat_history.append({"role": "user", "content": ex})
                with st.spinner("PawPal AI is thinking…"):
                    try:
                        response_text, confidence, tool_calls = agent.process_message(ex)
                    except Exception as e:
                        response_text = f"Sorry, an error occurred: {e}"
                        confidence = 0.0
                        tool_calls = []
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": response_text,
                        "confidence": confidence,
                        "tool_calls": tool_calls,
                    }
                )
                owner.save_to_json(DATA_FILE)
                st.rerun()

# ---------------------------------------------------------------------------
# Auto-save on every rerun
# ---------------------------------------------------------------------------
owner.save_to_json(DATA_FILE)
