"""PawPal+ AI Agent — agentic workflow powered by Claude with tool use and RAG."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic

from pawpal_system import Owner, Pet, Scheduler, Task

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pawpal.agent")

# ---------------------------------------------------------------------------
# Species knowledge base (RAG source)
# The agent retrieves from this store before recommending tasks or routines,
# grounding its suggestions in curated care facts rather than hallucinating.
# ---------------------------------------------------------------------------

_CARE_KNOWLEDGE: dict[str, dict] = {
    "dog": {
        "essential_tasks": [
            "Morning walk (25 min, daily, high priority)",
            "Evening walk (25 min, daily, high priority)",
            "Breakfast feeding (10 min, daily, high priority)",
            "Dinner feeding (10 min, daily, high priority)",
            "Fresh water change (5 min, daily, high priority)",
            "Playtime / fetch (20 min, daily, medium priority)",
            "Brushing (15 min, weekly, low priority)",
            "Nail trim (15 min, as-needed, low priority)",
            "Dental chew / teeth brushing (10 min, daily, low priority)",
        ],
        "health_notes": [
            "Dogs need at least 30–60 minutes of exercise daily",
            "Puppies under 6 months need 3–4 meals per day",
            "Regular dental care prevents periodontal disease",
            "Watch for heat exhaustion during summer walks",
            "Annual vet visits and heartworm prevention are essential",
        ],
        "tips": [
            "Consistent feeding times regulate digestion and behaviour",
            "Mental stimulation (puzzle toys, training sessions) is as important as physical exercise",
            "Senior dogs (7+) may need shorter, more frequent walks",
            "Socialisation with other dogs reduces anxiety",
        ],
    },
    "cat": {
        "essential_tasks": [
            "Morning feeding (10 min, daily, high priority)",
            "Evening feeding (10 min, daily, high priority)",
            "Fresh water change (5 min, daily, high priority)",
            "Litter box scooping (10 min, daily, high priority)",
            "Interactive play session (15 min, daily, medium priority)",
            "Full litter box clean (20 min, weekly, medium priority)",
            "Brushing (10 min, weekly, low priority)",
        ],
        "health_notes": [
            "Cats need fresh water daily; a cat fountain encourages drinking",
            "Indoor cats need environmental enrichment to prevent boredom",
            "Urinary tract issues are common in male cats — monitor water intake",
            "Dental disease affects most cats over age 3; brush teeth or use dental treats",
        ],
        "tips": [
            "Cats are crepuscular — most active at dawn and dusk",
            "Provide vertical space (cat trees, shelves) for mental wellbeing",
            "One litter box per cat plus one extra is the recommended ratio",
            "Rotate toys weekly to maintain novelty and engagement",
        ],
    },
    "rabbit": {
        "essential_tasks": [
            "Unlimited hay replenishment (10 min, daily, high priority)",
            "Fresh water change (5 min, daily, high priority)",
            "Pellet feeding — limited amount (5 min, daily, high priority)",
            "Fresh leafy greens serving (10 min, daily, medium priority)",
            "Free-roam supervised playtime (30 min, daily, medium priority)",
            "Litter box / cage spot-clean (15 min, daily, medium priority)",
            "Full habitat deep clean (25 min, weekly, high priority)",
            "Grooming / fur check (10 min, weekly, low priority)",
        ],
        "health_notes": [
            "Hay should make up 80% of a rabbit's diet — it prevents GI stasis",
            "Signs of GI stasis (not eating, no droppings) require immediate vet care",
            "Rabbits are sensitive to heat — keep environment under 75°F (24°C)",
            "Never lift a rabbit by its ears or scruff; support the hindquarters",
            "Rabbits are fragile; handle gently and supervise children closely",
        ],
        "tips": [
            "Rabbits are social and thrive in bonded pairs",
            "Cardboard boxes and tunnels provide inexpensive enrichment",
            "Pellets should be limited; they are primarily for young/growing rabbits",
            "Rabbits can be litter-trained, making cleaning easier",
        ],
    },
    "bird": {
        "essential_tasks": [
            "Fresh food serving (10 min, daily, high priority)",
            "Fresh water change (5 min, daily, high priority)",
            "Cage spot-cleaning (10 min, daily, medium priority)",
            "Out-of-cage interaction time (20 min, daily, medium priority)",
            "Cage deep clean (30 min, weekly, high priority)",
            "Toy rotation (10 min, weekly, low priority)",
            "Beak and nail check (15 min, as-needed, low priority)",
        ],
        "health_notes": [
            "Birds hide illness — changes in droppings, feathers, or behaviour need vet attention",
            "Avocado, chocolate, caffeine, onion, and xylitol are toxic to birds",
            "Birds need 10–12 hours of sleep in a quiet, dark environment",
            "Non-stick (PTFE/Teflon) cookware fumes can be fatal to birds",
        ],
        "tips": [
            "Rotate toys weekly to prevent boredom",
            "Speak and sing to your bird daily for socialisation and bonding",
            "Foraging toys encourage natural behaviour and mental stimulation",
            "Misting with warm water encourages preening and feather health",
        ],
    },
    "other": {
        "essential_tasks": [
            "Daily feeding (10–15 min, daily, high priority)",
            "Fresh water change (5 min, daily, high priority)",
            "Habitat cleaning (20–30 min, weekly, high priority)",
            "Health observation (5 min, daily, medium priority)",
            "Socialisation / handling (15 min, daily, medium priority)",
        ],
        "health_notes": [
            "Research your specific species' husbandry needs carefully",
            "Regular vet check-ups are important for all pets",
            "Monitor for changes in eating, behaviour, and appearance",
        ],
        "tips": [
            "Create a consistent routine for feeding and interaction",
            "Environmental enrichment supports mental wellbeing for all animals",
        ],
    },
}

# ---------------------------------------------------------------------------
# Tool schema definitions passed to Claude
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "get_pets",
        "description": (
            "List all registered pets and their pending tasks. "
            "Call this first to understand the current state before making changes."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_pet",
        "description": "Add a new pet to the owner's roster.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Pet's name"},
                "species": {
                    "type": "string",
                    "enum": ["dog", "cat", "rabbit", "bird", "other"],
                },
                "age_years": {
                    "type": "number",
                    "description": "Age in years (e.g. 2.5)",
                },
            },
            "required": ["name", "species"],
        },
    },
    {
        "name": "create_task",
        "description": (
            "Create a new care task and add it to a specific pet. "
            "Call retrieve_care_tips first when you need species-specific guidance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pet_name": {"type": "string"},
                "title": {"type": "string", "description": "Short task title"},
                "duration_minutes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 240,
                },
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "frequency": {
                    "type": "string",
                    "enum": ["daily", "weekly", "as-needed"],
                },
                "description": {"type": "string", "description": "Optional detail"},
            },
            "required": ["pet_name", "title", "duration_minutes", "priority", "frequency"],
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a specific task as completed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pet_name": {"type": "string"},
                "task_title": {"type": "string"},
            },
            "required": ["pet_name", "task_title"],
        },
    },
    {
        "name": "remove_task",
        "description": "Remove a task from a pet's task list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pet_name": {"type": "string"},
                "task_title": {"type": "string"},
            },
            "required": ["pet_name", "task_title"],
        },
    },
    {
        "name": "get_schedule",
        "description": (
            "Generate and return today's care schedule. "
            "Call after making changes to verify the plan and confirm there are no issues."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "use_weighted": {
                    "type": "boolean",
                    "description": "True = urgency-weighted scoring; False = standard priority order",
                }
            },
            "required": [],
        },
    },
    {
        "name": "retrieve_care_tips",
        "description": (
            "Retrieve curated expert pet-care knowledge for a species from the knowledge base. "
            "Always call this before recommending tasks or routines so suggestions are "
            "grounded in accurate care information rather than guesses."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "species": {
                    "type": "string",
                    "enum": ["dog", "cat", "rabbit", "bird", "other"],
                }
            },
            "required": ["species"],
        },
    },
]

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class PawPalAgent:
    """Claude-powered agentic assistant for managing a PawPal+ owner's pets and schedule.

    Architecture:
      User message → Claude (with tools) → tool calls → results back to Claude
      → (repeat until stop_reason == "end_turn") → final text response with confidence score

    The retrieve_care_tips tool implements a lightweight RAG pattern: the agent
    retrieves species-specific care facts before generating recommendations, so
    its suggestions are grounded in the knowledge base rather than training data alone.
    """

    MODEL = "claude-sonnet-4-6"
    MAX_TOKENS = 1024
    MAX_TOOL_LOOPS = 10

    SYSTEM_PROMPT = (
        "You are PawPal AI, an expert pet care scheduling assistant. "
        "You help pet owners manage daily care routines for their pets.\n\n"
        "Behaviour rules:\n"
        "1. Before recommending tasks for a species, call retrieve_care_tips to ground "
        "   your response in the knowledge base.\n"
        "2. After creating, completing, or removing tasks, call get_schedule to verify "
        "   the updated plan and confirm there are no conflicts.\n"
        "3. Be concise and action-oriented. Confirm what you *did*, not just what you planned.\n"
        "4. If a pet is not found, tell the user and suggest adding the pet first.\n"
        "5. If a request is ambiguous, state your assumption and proceed.\n\n"
        "Confidence scoring (mandatory):\n"
        "End EVERY response with exactly one line in this format:\n"
        "CONFIDENCE: 0.X\n"
        "Rate 0.0–1.0 based on how completely and correctly you fulfilled the request. "
        "Use 0.9+ only when you verified the result with get_schedule or get_pets."
    )

    def __init__(self, owner: Owner) -> None:
        self.owner = owner
        self.client = anthropic.Anthropic()
        self.conversation_history: list[dict] = []
        self._tool_call_log: list[dict] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_message(self, user_message: str) -> tuple[str, float, list[dict]]:
        """Process a natural-language message through the agentic loop.

        Returns:
            (response_text, confidence_score, tool_calls_made)
        """
        logger.info("User: %s", user_message)
        self.conversation_history.append({"role": "user", "content": user_message})
        self._tool_call_log.clear()

        for _ in range(self.MAX_TOOL_LOOPS):
            response = self._call_claude()

            if response.stop_reason == "tool_use":
                tool_results = self._execute_tool_blocks(response.content)
                self.conversation_history.append(
                    {"role": "assistant", "content": response.content}
                )
                self.conversation_history.append(
                    {"role": "user", "content": tool_results}
                )
                continue

            text = self._extract_text(response.content)
            self.conversation_history.append({"role": "assistant", "content": text})
            confidence = self._extract_confidence(text)
            clean = self._strip_confidence_line(text)
            logger.info(
                "Agent (confidence=%.2f): %s",
                confidence,
                clean[:100] + ("…" if len(clean) > 100 else ""),
            )
            return clean, confidence, list(self._tool_call_log)

        logger.warning("Exceeded MAX_TOOL_LOOPS (%d)", self.MAX_TOOL_LOOPS)
        return "I ran into a problem — please try rephrasing your request.", 0.0, list(self._tool_call_log)

    def reset_conversation(self) -> None:
        """Clear conversation history for a fresh session."""
        self.conversation_history.clear()
        self._tool_call_log.clear()
        logger.info("Conversation reset.")

    # ------------------------------------------------------------------
    # Claude API call with prompt caching
    # ------------------------------------------------------------------

    def _call_claude(self) -> anthropic.types.Message:
        return self.client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": self.SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=TOOLS,
            messages=self.conversation_history,
        )

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool_blocks(self, content: list) -> list[dict]:
        results = []
        for block in content:
            if block.type != "tool_use":
                continue
            result = self._execute_tool(block.name, block.input)
            self._tool_call_log.append(
                {"tool": block.name, "input": block.input, "result": result}
            )
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            )
        return results

    def _execute_tool(self, name: str, inputs: dict[str, Any]) -> str:
        logger.info("Tool: %s(%s)", name, json.dumps(inputs, default=str))
        try:
            dispatch = {
                "get_pets": self._tool_get_pets,
                "add_pet": self._tool_add_pet,
                "create_task": self._tool_create_task,
                "complete_task": self._tool_complete_task,
                "remove_task": self._tool_remove_task,
                "get_schedule": self._tool_get_schedule,
                "retrieve_care_tips": self._tool_retrieve_care_tips,
            }
            handler = dispatch.get(name)
            if handler is None:
                return json.dumps({"error": f"Unknown tool: {name}"})
            return handler(**inputs)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool %s raised: %s", name, exc)
            return json.dumps({"error": str(exc)})

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------

    def _tool_get_pets(self) -> str:
        if not self.owner.pets:
            return json.dumps({"pets": [], "message": "No pets registered yet."})
        return json.dumps(
            {
                "pets": [
                    {
                        "name": p.name,
                        "species": p.species,
                        "age_years": p.age_years,
                        "total_tasks": len(p.tasks),
                        "pending_tasks": len(p.pending_tasks()),
                        "tasks": [
                            {
                                "title": t.title,
                                "duration_minutes": t.duration_minutes,
                                "priority": t.priority,
                                "frequency": t.frequency,
                                "completed": t.completed,
                                "due_date": t.due_date.isoformat(),
                            }
                            for t in p.tasks
                        ],
                    }
                    for p in self.owner.pets
                ]
            }
        )

    def _tool_add_pet(self, name: str, species: str, age_years: float = 0.0) -> str:
        if self.owner.find_pet(name):
            return json.dumps({"error": f"A pet named '{name}' already exists."})
        self.owner.add_pet(Pet(name=name, species=species, age_years=age_years))
        return json.dumps({"success": True, "message": f"Added {name} the {species}."})

    def _tool_create_task(
        self,
        pet_name: str,
        title: str,
        duration_minutes: int,
        priority: str,
        frequency: str,
        description: str = "",
    ) -> str:
        pet = self.owner.find_pet(pet_name)
        if pet is None:
            return json.dumps(
                {
                    "error": f"No pet named '{pet_name}' found.",
                    "available_pets": [p.name for p in self.owner.pets],
                }
            )
        task = Task(
            title=title,
            duration_minutes=duration_minutes,
            priority=priority,  # type: ignore[arg-type]
            description=description,
            frequency=frequency,  # type: ignore[arg-type]
        )
        pet.add_task(task)
        return json.dumps(
            {"success": True, "message": f"Added '{title}' to {pet_name}.", "task": task.to_dict()}
        )

    def _tool_complete_task(self, pet_name: str, task_title: str) -> str:
        pet = self.owner.find_pet(pet_name)
        if pet is None:
            return json.dumps({"error": f"No pet named '{pet_name}' found."})
        for task in pet.tasks:
            if task.title.lower() == task_title.lower():
                task.mark_complete()
                return json.dumps({"success": True, "message": f"Marked '{task_title}' complete."})
        return json.dumps(
            {"error": f"No task '{task_title}' found for {pet_name}.", "tasks": [t.title for t in pet.tasks]}
        )

    def _tool_remove_task(self, pet_name: str, task_title: str) -> str:
        pet = self.owner.find_pet(pet_name)
        if pet is None:
            return json.dumps({"error": f"No pet named '{pet_name}' found."})
        before = len(pet.tasks)
        pet.remove_task(task_title)
        if len(pet.tasks) < before:
            return json.dumps({"success": True, "message": f"Removed '{task_title}' from {pet_name}."})
        return json.dumps({"error": f"No task '{task_title}' found for {pet_name}."})

    def _tool_get_schedule(self, use_weighted: bool = False) -> str:
        sched = Scheduler(owner=self.owner)
        plan = sched.build_weighted_plan() if use_weighted else sched.build_plan()
        conflicts = sched.detect_conflicts(plan)
        return json.dumps(
            {
                "total_minutes": plan.total_minutes,
                "available_minutes": self.owner.available_minutes,
                "scheduled_count": len(plan.scheduled),
                "skipped_count": len(plan.skipped),
                "scheduled": [
                    {
                        "title": st.task.title,
                        "pet": st.pet.name,
                        "time": st.time_range(),
                        "priority": st.task.priority,
                        "duration_minutes": st.task.duration_minutes,
                    }
                    for st in plan.scheduled
                ],
                "skipped": [
                    {"title": t.title, "pet": p.name, "reason": r}
                    for t, p, r in plan.skipped
                ],
                "conflicts": conflicts,
            }
        )

    def _tool_retrieve_care_tips(self, species: str) -> str:
        """RAG retrieval: return curated care knowledge for the given species."""
        data = _CARE_KNOWLEDGE.get(species, _CARE_KNOWLEDGE["other"])
        return json.dumps({"species": species, "knowledge": data})

    # ------------------------------------------------------------------
    # Response parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(content: list) -> str:
        for block in content:
            if hasattr(block, "text"):
                return block.text
        return ""

    @staticmethod
    def _extract_confidence(text: str) -> float:
        match = re.search(r"CONFIDENCE:\s*([\d.]+)", text, re.IGNORECASE)
        if match:
            try:
                return min(1.0, max(0.0, float(match.group(1))))
            except ValueError:
                pass
        return 0.5

    @staticmethod
    def _strip_confidence_line(text: str) -> str:
        return re.sub(r"\n?CONFIDENCE:\s*[\d.]+\s*$", "", text, flags=re.IGNORECASE).strip()
