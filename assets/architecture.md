# PawPal+ AI — System Architecture Diagram

```mermaid
flowchart TD
    U(["👤 User\n(natural language)"])
    UI["🖥️ Streamlit UI\nchat history · confidence score\ntool call log · suggested prompts"]

    subgraph Agent["🤖 PawPal AI Agent  —  claude-sonnet-4-6"]
        direction TB
        L1["1 · Receive message"]
        L2["2 · Plan tool calls"]
        L3["3 · Execute tools"]
        L4["4 · Verify with get_schedule"]
        L5["5 · Return response + confidence score"]
        L1 --> L2 --> L3 --> L4 --> L5
    end

    subgraph ToolLayer["⚙️ Tool Layer"]
        direction LR
        RAG["retrieve_care_tips\n🔍 RAG retrieval"]
        CT["create_task\ncomplete_task\nremove_task"]
        GP["get_pets\nadd_pet"]
        GS["get_schedule\n✅ verification"]
    end

    KB[("📚 Species Knowledge Base\ndog · cat · rabbit · bird · other\nessential tasks · health notes · tips")]

    subgraph Domain["📦 Domain Model"]
        OWN["Owner"]
        PET["Pet"]
        TSK["Task"]
        SCH["Scheduler\n(priority / weighted)"]
        OWN --> PET --> TSK
        SCH -.-> OWN
    end

    DB[("💾 data.json\nJSON persistence\nauto-save on every action")]

    U -->|"message"| UI
    UI -->|"user_message"| Agent
    Agent -->|"tool calls"| ToolLayer
    RAG -->|"retrieves"| KB
    CT --> Domain
    GP --> Domain
    GS --> Domain
    Domain -->|"save_to_json"| DB
    DB -->|"load_from_json"| Domain
    Agent -->|"text + confidence"| UI
    UI -->|"response"| U
```

## Component Summary

| Component | Role |
|---|---|
| **Streamlit UI** | Tab-based interface (Pets & Tasks / Schedule / AI Assistant). Displays chat history, confidence scores, and collapsible tool call logs. |
| **PawPal AI Agent** | Claude-powered agentic loop. Calls tools repeatedly until `stop_reason == "end_turn"`, then returns the final response. System prompt is cached for efficiency. |
| **retrieve_care_tips** | RAG tool. Retrieves curated species-specific care knowledge from the built-in knowledge base before the agent generates recommendations. |
| **create/complete/remove_task** | Mutation tools. Directly modify the in-memory `Owner` object. |
| **get_schedule** | Verification tool. Called after mutations to confirm the updated plan fits the time budget and has no conflicts. |
| **Species Knowledge Base** | Static curated store: essential tasks, health notes, and tips for 5 species. Acts as the retrieval corpus for the RAG pattern. |
| **Domain Model** | `Owner → Pet → Task` hierarchy + `Scheduler`. Pure Python dataclasses with no UI dependencies. |
| **data.json** | Persistent store. Auto-saved after every agent action and every Streamlit rerun. |

## Human Checkpoints

- Confidence score displayed on every AI response (🟢 ≥ 80% · 🟡 50–79% · 🔴 < 50%)
- Tool call log expandable in the UI — user can see exactly what the agent changed
- All changes immediately visible in the Pets & Tasks and Schedule tabs
- Conversation can be reset at any time with the "Clear" button
