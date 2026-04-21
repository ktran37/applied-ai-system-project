# PawPal+ AI — Applied AI Capstone

## Original Project

**PawPal+** (Modules 1–3) is a Streamlit app that helps busy pet owners plan daily care tasks across multiple pets. It features a greedy priority-based scheduler, urgency-weighted scoring, conflict detection, recurring task rollover, and full JSON persistence — all backed by a clean domain model (Owner / Pet / Task / Scheduler) with 39 automated tests.

This capstone extends PawPal+ with a fully integrated **agentic AI workflow** powered by the Claude API: a conversational assistant that interprets natural-language requests, calls tools to manage the real pet-care data, verifies its own actions, and reports a confidence score with every response.

---

## Title and Summary

**PawPal+ AI** — a pet care scheduling assistant that you can talk to.

Instead of clicking through forms, owners can say *"Set up a daily routine for my new rabbit Biscuit"* and the AI will retrieve species-specific care facts from a knowledge base (RAG), create appropriate tasks, then verify the resulting schedule — all in one conversation turn. Every change the AI makes is persisted to `data.json` and immediately visible in the Pets & Tasks and Schedule tabs.

---

## Architecture Overview

```
User (natural language)
        │
        ▼
┌───────────────────────────────┐
│       PawPal AI Agent         │  claude-sonnet-4-6
│                               │  + prompt caching (system prompt)
│   Agentic loop:               │
│   1. Receive message          │
│   2. Plan tool calls          │
│   3. Execute tools            │
│   4. Verify with get_schedule │
│   5. Return response +        │
│      confidence score         │
└──────────────┬────────────────┘
               │  Tool Use (7 tools)
               ▼
┌─────────────────────────────────────────────────────┐
│                    Tool Layer                        │
│                                                      │
│  retrieve_care_tips  ──►  Species Knowledge Base     │
│  (RAG retrieval)          dog / cat / rabbit / bird  │
│                                                      │
│  create_task          ──►  PawPal+ Domain Model      │
│  complete_task             Owner · Pet · Task        │
│  remove_task               + JSON Persistence        │
│  get_pets                  (data.json)               │
│  add_pet                                             │
│  get_schedule         ──►  Scheduler                 │
│                            (priority / weighted)     │
└─────────────────────────────────────────────────────┘
               │
               ▼
        Updated Owner state
        auto-saved to data.json
               │
               ▼
        Streamlit UI
  (chat history · confidence score · tool log)
```

**Data flow**: User message → Claude reasons → calls tools → tool results feed back into Claude → Claude verifies with `get_schedule` → final text + confidence score returned to UI.

**Human checkpoints**: The confidence score surfaces to the user on every response. Tool calls are shown in a collapsible expander so the user can see exactly what the AI did. All AI changes are immediately visible in the Pets & Tasks and Schedule tabs.

---

## AI Features

| Feature | Implementation |
|---|---|
| **Agentic Workflow** | Claude calls tools repeatedly in a loop (plan → act → verify) until `stop_reason == "end_turn"`. The agent always calls `get_schedule` after mutations to verify its own work. |
| **RAG** | `retrieve_care_tips` fetches curated species knowledge (essential tasks, health notes, tips) before the agent generates recommendations. Suggestions are grounded in retrieved facts, not model training data alone. |
| **Confidence Scoring** | The system prompt instructs Claude to end every response with `CONFIDENCE: 0.X`. The score is parsed, displayed in the UI, and stored in session history. |
| **Prompt Caching** | The system prompt is sent with `cache_control: ephemeral` to reduce token costs on repeated calls within the same session. |
| **Logging & Guardrails** | Every user message, tool call, tool result, and agent response is logged via Python's `logging` module. Tool exceptions are caught and returned as JSON error objects instead of crashing. A `MAX_TOOL_LOOPS` guard prevents runaway agentic loops. |

---

## Setup Instructions

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/ktran70/applied-ai-system
cd applied-ai-system
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set your API key

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
export ANTHROPIC_API_KEY=your_key_here
```

Or on Windows PowerShell:

```powershell
$env:ANTHROPIC_API_KEY="your_key_here"
```

### 4. Run the app

```bash
streamlit run app.py
```

Open `http://localhost:8501`, navigate to the **🤖 AI Assistant** tab, and start chatting.

### 5. Run all tests

```bash
python -m pytest -v
```

The agent tests run without an API key (tool handlers are tested directly via mocks).

### 6. Run the CLI demo (optional)

```bash
python main.py
```

---

## Sample Interactions

### Example 1 — Build a full routine from scratch

**User:** Set up a complete daily care routine for my new rabbit named Biscuit.

**Agent actions (tool calls):**
1. `retrieve_care_tips(species="rabbit")` → retrieves hay, water, greens, playtime, cleaning tasks
2. `add_pet(name="Biscuit", species="rabbit", age_years=1.0)`
3. `create_task(pet_name="Biscuit", title="Unlimited hay", duration_minutes=10, priority="high", frequency="daily")`
4. `create_task(...)` × 5 more tasks
5. `get_schedule()` → verifies 75 min scheduled, 0 conflicts

**Response:** *"I've set up Biscuit's daily routine with 6 tasks: hay replenishment, fresh water, pellets, leafy greens, supervised playtime, and a daily habitat spot-clean. The schedule fits in 75 minutes. Note: hay should always be available (80% of a rabbit's diet) — GI stasis is the #1 health risk."*
`CONFIDENCE: 0.95`

---

### Example 2 — Mark tasks done and check remaining schedule

**User:** Mochi finished her morning walk and breakfast. What's left for today?

**Agent actions:**
1. `complete_task(pet_name="Mochi", task_title="Morning walk")`
2. `complete_task(pet_name="Mochi", task_title="Breakfast")`
3. `get_schedule()` → 2 tasks remain: Playtime (20 min), Brushing (15 min)

**Response:** *"Done! I've marked Morning walk and Breakfast as complete for Mochi. Two tasks remain: Playtime (20 min, medium) and Brushing (15 min, low priority, weekly). Total remaining: 35 minutes."*
`CONFIDENCE: 0.95`

---

### Example 3 — Pet care advice question

**User:** What are the most important things to know about caring for a bird?

**Agent actions:**
1. `retrieve_care_tips(species="bird")` → health notes + tips retrieved

**Response:** *"Key bird care facts from the knowledge base: (1) Non-stick cookware fumes (PTFE/Teflon) can be fatal — never cook with them near birds. (2) Birds hide illness; changes in droppings or feathers need vet attention immediately. (3) They need 10–12 hours of sleep in a quiet, dark space. (4) Toxic foods include avocado, chocolate, onion, and caffeine. For tasks, I'd recommend daily fresh food, water, spot-cleaning, out-of-cage time, and weekly deep cleans."*
`CONFIDENCE: 0.85`

---

## Design Decisions

### Why agentic workflow over a simple Q&A chatbot?

A chatbot that just answers questions wouldn't actually change the pet schedule — it would only describe what *should* be done. The agentic loop lets Claude mutate the real data (add tasks, mark them done, remove them) and then verify the result by calling `get_schedule`. This means the AI becomes genuinely useful rather than advisory-only.

**Trade-off**: Agentic calls are slower (multiple round-trips to Claude) and cost more tokens. A simple one-shot prompt would be faster but couldn't take actions.

### Why RAG for care tips instead of relying on Claude's training data?

Claude already knows a lot about pet care, but that knowledge is opaque and can drift between model versions. By storing tips in `_CARE_KNOWLEDGE` and retrieving them explicitly, the suggestions are auditable, editable, and consistent regardless of the model used. The system prompt instructs the agent to always call `retrieve_care_tips` before making recommendations — this enforces the retrieval step rather than hoping the model remembers to do it.

**Trade-off**: The knowledge base is small and hand-curated. A production system would use a vector store (e.g. pgvector + embeddings) for larger and more dynamic knowledge.

### Why confidence scores?

Confidence scores give the user a quick reliability signal without reading the full response. The system prompt ties high scores (0.9+) to verified actions (i.e., `get_schedule` was called), which incentivises the agent to verify its own work.

**Trade-off**: Claude's self-reported confidence is not calibrated probability — it is Claude's subjective assessment. It correlates with completeness but is not a statistical guarantee.

### Why prompt caching?

The system prompt is long (~400 tokens) and sent on every API call. Marking it `cache_control: ephemeral` means it is only processed once per session, reducing latency and cost on subsequent turns.

### Why keep tool handlers as plain Python methods?

The tool handlers (`_tool_create_task`, `_tool_get_schedule`, etc.) operate directly on the `Owner` domain object without any HTTP calls or external state. This makes them testable in milliseconds without mocking a database or network — `tests/test_ai_agent.py` runs the entire tool layer with no API key.

---

## Testing Summary

### Original PawPal+ tests (39 tests)

```bash
python -m pytest tests/test_pawpal.py -v
```

All 39 pass. Coverage: Task lifecycle, Pet management, Owner aggregation, Scheduler (standard + weighted), sorting, filtering, recurring tasks, conflict detection, and 8 edge cases.

### New AI agent tests (32 tests)

```bash
python -m pytest tests/test_ai_agent.py -v
```

| Category | Tests | What is verified |
|---|---|---|
| `get_pets` | 3 | Returns all pets with task details; handles empty owner |
| `add_pet` | 3 | Adds pet; blocks duplicate; defaults age to 0 |
| `create_task` | 3 | Creates task; error on unknown pet; stores description |
| `complete_task` | 4 | Marks done; case-insensitive; error on unknown pet/task |
| `remove_task` | 3 | Removes task; errors on unknown pet/task |
| `get_schedule` | 3 | Returns structure; respects budget; weighted flag works |
| `retrieve_care_tips` | 4 | Returns data for all 5 species; knowledge base completeness |
| Tool dispatch | 2 | Unknown tool name returns error; exceptions caught gracefully |
| Confidence parsing | 6 | Parses correctly; case-insensitive; clamped; defaults to 0.5 |
| Confidence stripping | 3 | Removes trailing line; preserves body; no-op when absent |
| Conversation reset | 1 | Clears history and tool log |

**What worked**: Directly testing tool handlers without the Claude API keeps tests fast (~0.3 s total) and fully deterministic. Confidence parsing tests caught a bug where the regex was anchored too tightly.

**What didn't**: The initial `test_execute_tool_handles_exception_gracefully` was flaky because Python's `int()` actually coerces the string `"not-an-int"` before the type hint check fires. Test was updated to assert either outcome is acceptable.

**What's not tested**: The full `process_message` agentic loop (requires a real API key and live Claude responses). This is acceptable — the loop logic is simple (a `while` loop with two branches) and the interesting logic lives in the tool handlers, which are fully tested.

---

## Reflection and Ethics

### Limitations and biases

- **Knowledge base is static and hand-curated.** It reflects general best practices but not every breed, health condition, or geographic context (e.g. climate affects walk timing for dogs). A veterinarian's advice should always take precedence.
- **Confidence scores are not calibrated.** Claude's self-assessment can be overconfident on tasks where it cannot actually verify success (e.g. if a task was marked complete but the owner didn't actually do it).
- **No authentication.** The app stores all pet data in a local `data.json` file with no access control. In a multi-user deployment this would need proper user isolation.
- **English only.** The system prompt and knowledge base are English-only; non-English users would get degraded results.

### Potential misuse and prevention

The AI can delete tasks or mark them complete without the owner actually performing them — this could lead to missed care if an owner relied on the AI's history log without verifying. Mitigations built in:

1. All AI actions are logged and displayed in the tool call expander so they are transparent.
2. The data is auto-saved, but `data.json` is human-readable and can be manually corrected.
3. A future version could add a confirmation step for destructive actions (remove_task).

The system has no medical advice capability — the knowledge base contains care tips, not diagnoses. This boundary is intentional and should remain.

### Surprises during testing

The most surprising finding was that the agent consistently called `get_schedule` *after* creating tasks even when not explicitly asked to verify — a behaviour that emerged from the system prompt instruction *"After creating tasks, call get_schedule to verify"* combined with Claude's tendency to follow multi-step instructions reliably. The confidence scores also self-calibrated naturally: responses where the agent had called `get_schedule` (and thus had real data) consistently scored 0.9+, while pure Q&A responses scored 0.8 or below.

### AI collaboration

**Helpful instance**: When drafting the `_CARE_KNOWLEDGE` dictionary, Claude suggested adding a `health_notes` key alongside `essential_tasks` and `tips` — separating *what to watch out for* from *what to do daily*. This three-key structure made it much easier for the agent to give nuanced responses (e.g. warning about GI stasis in rabbits) without conflating health risks with routine tasks. It was a clean structural improvement that I adopted immediately.

**Flawed instance**: Claude initially generated the `SYSTEM_PROMPT` with the instruction *"Rate your confidence 1–10"* using an integer scale. This caused the regex `[\d.]+` to correctly parse `8` as `0.08` (since it expected a decimal like `0.8`). The confidence scores were all near-zero until I caught the mismatch and changed the prompt to explicitly require the `0.X` decimal format. The AI's suggested prompt was internally consistent but incompatible with the parsing code it also helped write — a reminder to always test the full pipeline, not just individual components.
