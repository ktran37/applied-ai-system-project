# Model Card — PawPal+ AI

## Overview

| Field | Value |
|---|---|
| **Project** | PawPal+ AI (Applied AI Capstone) |
| **Base model** | `claude-sonnet-4-6` (Anthropic) |
| **Primary AI feature** | Agentic workflow with tool use |
| **Secondary AI feature** | Retrieval-Augmented Generation (RAG) for species care tips |
| **Interface** | Streamlit chat tab + confidence scoring |
| **Persistence** | JSON file (`data.json`) |
| **Test coverage** | 81 automated tests (35 agent + 46 domain) |

---

## What the Model Does

PawPal+ AI wraps `claude-sonnet-4-6` in an agentic loop that manages a pet owner's care schedule through natural language. The model can:

- Create, complete, and remove pet care tasks
- Add new pets to the owner's roster
- Retrieve expert care tips for a species before making recommendations (RAG)
- Generate and verify the daily schedule after any change
- Rate its own confidence on every response

The model does **not** give veterinary or medical advice. All care information comes from a curated static knowledge base, not model training data.

---

## AI Feature Details

### Agentic Workflow

The agent runs in a `while` loop:
1. Send the current conversation + tools to Claude
2. If `stop_reason == "tool_use"` → execute each requested tool, append results, repeat
3. If `stop_reason == "end_turn"` → parse confidence score and return final text

A `MAX_TOOL_LOOPS = 10` guard prevents runaway loops. All tool calls and results are logged.

### RAG (Retrieval-Augmented Generation)

The `retrieve_care_tips` tool fetches structured care data from `_CARE_KNOWLEDGE` — a Python dictionary with entries for `dog`, `cat`, `rabbit`, `bird`, and `other`. The system prompt instructs the agent to always call this tool before recommending routines, ensuring suggestions are grounded in retrieved facts rather than opaque training data.

The knowledge base contains three categories per species:
- **essential_tasks** — common daily/weekly care activities with suggested duration and priority
- **health_notes** — critical warnings (e.g. Teflon fumes and birds, GI stasis in rabbits)
- **tips** — best-practice advice for enrichment and routine-building

### Confidence Scoring

The system prompt requires every response to end with `CONFIDENCE: 0.X` on a 0–1 scale. The score is parsed with a regex, clamped to [0, 1], and displayed in the UI. High scores (0.9+) are reserved for responses where the agent verified its result via `get_schedule`.

### Prompt Caching

The system prompt (~400 tokens) is sent with `cache_control: ephemeral`, which caches it for 5 minutes. This reduces latency and cost on subsequent turns within the same session.

---

## Training Data and Knowledge Sources

The base model (`claude-sonnet-4-6`) was trained by Anthropic on a broad corpus of internet text. PawPal+ AI does **not** fine-tune the model.

The species knowledge base (`_CARE_KNOWLEDGE` in `ai_agent.py`) was hand-curated from general pet care best practices. It is not sourced from a veterinary database and should not be used as a substitute for professional veterinary advice.

---

## Limitations and Biases

| Limitation | Detail |
|---|---|
| **Static knowledge base** | Care tips are hard-coded and do not update. They reflect general best practices, not individual animal needs, breed differences, or regional climate factors. |
| **No medical capability** | The system cannot diagnose illness, assess symptoms, or recommend medications. It explicitly avoids this scope. |
| **Self-reported confidence is uncalibrated** | Claude's confidence scores reflect its own assessment of completeness, not a statistical probability. The agent can be overconfident on tasks it believes it fulfilled but cannot externally verify. |
| **English only** | The system prompt, knowledge base, and all responses are English-only. Non-English queries receive degraded results. |
| **Single-user, local storage** | `data.json` has no access control or multi-user isolation. Unsuitable for shared or production deployments without auth. |
| **Species coverage** | Only `dog`, `cat`, `rabbit`, `bird`, and `other`. Exotic pets (reptiles, fish, guinea pigs) fall through to a generic `other` entry. |

---

## Potential Misuse and Mitigations

| Misuse scenario | Mitigation |
|---|---|
| Owner marks tasks complete without doing them | Tool calls are logged and visible in the UI expander. `data.json` is human-readable and can be audited. |
| Agent removes tasks the user didn't intend to delete | Tool call log is always shown; future versions could add a confirmation step for destructive actions. |
| User treats care tips as veterinary advice | Knowledge base entries explicitly state health risks (e.g. "requires immediate vet care"); the model card and README state the system is not a veterinary tool. |
| API key exposure | `.env` is in `.gitignore`; `.env.example` is committed instead. `ANTHROPIC_API_KEY` is never logged or displayed in the UI. |

---

## Testing Summary

### Automated tests

```
python -m pytest -v        # 81 tests, all passing
```

| Suite | Tests | Pass |
|---|---|---|
| `tests/test_ai_agent.py` | 35 | 35 ✅ |
| `tests/test_pawpal.py` | 46 | 46 ✅ |

Agent tests cover all 7 tool handlers, confidence extraction/clamping/stripping, tool dispatch error handling, and conversation reset. They run in ~0.3 s without an API key (tool handlers are tested directly via mocks).

### What worked

- Tool handlers are pure Python methods on the `PawPalAgent` class, so they can be tested in isolation without any HTTP calls.
- The confidence regex correctly handles case variations (`CONFIDENCE:`, `confidence:`) and malformed values (non-numeric, out-of-range).
- Directly exercising `_tool_get_schedule` confirmed that `use_weighted=True` and `use_weighted=False` both return valid schedule structures with the same keys.

### What didn't / surprises

- **Initial confidence regex was anchored too tightly.** The first version used `\bCONFIDENCE:` which failed when the line had leading whitespace. Updated to `re.search` (not `re.match`) to handle any position in the string.
- **`test_execute_tool_handles_exception_gracefully` was initially flaky** because Python's `int()` coerces a string like `"not-an-int"` before the tool handler fires, and the `Task` dataclass doesn't validate types at construction time. The test was updated to accept either an error or a successful result.
- **The agent verified its own work without being told to** on specific tasks. The system prompt says "call get_schedule after mutations" and Claude followed it consistently — even when the user didn't ask for a schedule summary. This emergent adherence to multi-step instructions was a positive surprise.

---

## AI Collaboration

### Helpful suggestion

When drafting the `_CARE_KNOWLEDGE` dictionary, Claude suggested splitting entries into three separate keys — `essential_tasks`, `health_notes`, and `tips` — rather than a single flat list. This structural separation meant the agent could distinguish between *what to do daily* (actionable tasks) and *what to watch out for* (health risks), producing responses that were more nuanced and practically useful. For example, when asked about rabbit care, the agent could lead with the GI stasis warning from `health_notes` before listing routine tasks, rather than burying it in a flat list. I adopted this structure immediately.

### Flawed suggestion

Claude initially drafted the `SYSTEM_PROMPT` with the instruction *"Rate your confidence on a scale of 1 to 10"* using an integer scale. The confidence parsing regex I had written expected a decimal like `0.9` and used the pattern `[\d.]+`. When Claude emitted `CONFIDENCE: 8`, the regex correctly matched `8`, but `float("8")` is `8.0` — which the `min(1.0, ...)` clamp then reduced to `1.0`. Every response appeared 100% confident regardless of actual quality. The fix was to change the system prompt to explicitly require the `0.X` format (`CONFIDENCE: 0.9`). The lesson: always test the full pipeline end-to-end, not just individual components in isolation — the AI's prompt suggestion was internally consistent but incompatible with the parsing code it had also helped write.

---

## Ethical Considerations

- **Transparency**: Every AI action is logged and surfaced to the user. The system does not make silent changes.
- **Human oversight**: The confidence score and tool call log give users the information they need to spot mistakes.
- **Scope boundaries**: The system is explicitly a scheduling assistant, not a diagnostic tool. This scope is stated in the system prompt, the README, and this model card.
- **Data privacy**: All data is stored locally in `data.json`. No pet or owner data is sent to Anthropic beyond the tool results and schedule summaries included in Claude's context window.
