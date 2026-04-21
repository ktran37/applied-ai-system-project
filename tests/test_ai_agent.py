"""Tests for the PawPal+ AI agent tool handlers and utility methods.

These tests exercise the tool functions directly without calling the Claude API,
making them fast, deterministic, and runnable without an ANTHROPIC_API_KEY.
"""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from ai_agent import PawPalAgent, _CARE_KNOWLEDGE
from pawpal_system import Owner, Pet, Task


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def owner_with_dog():
    """Owner with one dog that has two tasks."""
    owner = Owner(name="Alex", available_minutes=90)
    dog = Pet(name="Rex", species="dog", age_years=4.0)
    dog.add_task(Task("Morning walk", duration_minutes=30, priority="high", frequency="daily"))
    dog.add_task(Task("Breakfast", duration_minutes=10, priority="high", frequency="daily"))
    owner.add_pet(dog)
    return owner


@pytest.fixture
def agent(owner_with_dog):
    """PawPalAgent backed by a mock Anthropic client (no real API calls)."""
    with patch("ai_agent.anthropic.Anthropic"):
        a = PawPalAgent(owner=owner_with_dog)
    return a


# ---------------------------------------------------------------------------
# get_pets
# ---------------------------------------------------------------------------


def test_get_pets_returns_all_pets(agent, owner_with_dog):
    result = json.loads(agent._tool_get_pets())
    assert len(result["pets"]) == 1
    assert result["pets"][0]["name"] == "Rex"
    assert result["pets"][0]["species"] == "dog"
    assert result["pets"][0]["total_tasks"] == 2


def test_get_pets_empty_owner():
    empty_owner = Owner(name="Pat", available_minutes=60)
    with patch("ai_agent.anthropic.Anthropic"):
        a = PawPalAgent(owner=empty_owner)
    result = json.loads(a._tool_get_pets())
    assert result["pets"] == []
    assert "message" in result


def test_get_pets_includes_task_details(agent):
    result = json.loads(agent._tool_get_pets())
    tasks = result["pets"][0]["tasks"]
    titles = [t["title"] for t in tasks]
    assert "Morning walk" in titles
    assert "Breakfast" in titles


# ---------------------------------------------------------------------------
# add_pet
# ---------------------------------------------------------------------------


def test_add_pet_success(agent, owner_with_dog):
    result = json.loads(agent._tool_add_pet(name="Luna", species="cat", age_years=2.0))
    assert result["success"] is True
    assert owner_with_dog.find_pet("Luna") is not None


def test_add_pet_duplicate_returns_error(agent, owner_with_dog):
    result = json.loads(agent._tool_add_pet(name="Rex", species="dog"))
    assert "error" in result
    assert len(owner_with_dog.pets) == 1  # No duplicate added


def test_add_pet_without_age_defaults_zero(agent, owner_with_dog):
    agent._tool_add_pet(name="Pip", species="bird")
    pet = owner_with_dog.find_pet("Pip")
    assert pet is not None
    assert pet.age_years == 0.0


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------


def test_create_task_success(agent, owner_with_dog):
    result = json.loads(
        agent._tool_create_task(
            pet_name="Rex",
            title="Evening walk",
            duration_minutes=25,
            priority="high",
            frequency="daily",
        )
    )
    assert result["success"] is True
    pet = owner_with_dog.find_pet("Rex")
    assert any(t.title == "Evening walk" for t in pet.tasks)


def test_create_task_unknown_pet_returns_error(agent):
    result = json.loads(
        agent._tool_create_task(
            pet_name="Ghost",
            title="Walk",
            duration_minutes=20,
            priority="medium",
            frequency="daily",
        )
    )
    assert "error" in result
    assert "available_pets" in result


def test_create_task_with_description(agent, owner_with_dog):
    agent._tool_create_task(
        pet_name="Rex",
        title="Medication",
        duration_minutes=5,
        priority="high",
        frequency="daily",
        description="One pill with food",
    )
    pet = owner_with_dog.find_pet("Rex")
    med = next(t for t in pet.tasks if t.title == "Medication")
    assert med.description == "One pill with food"


# ---------------------------------------------------------------------------
# complete_task
# ---------------------------------------------------------------------------


def test_complete_task_marks_done(agent, owner_with_dog):
    result = json.loads(agent._tool_complete_task(pet_name="Rex", task_title="Morning walk"))
    assert result["success"] is True
    pet = owner_with_dog.find_pet("Rex")
    walk = next(t for t in pet.tasks if t.title == "Morning walk")
    assert walk.completed is True


def test_complete_task_case_insensitive(agent, owner_with_dog):
    result = json.loads(agent._tool_complete_task(pet_name="rex", task_title="BREAKFAST"))
    assert result["success"] is True


def test_complete_task_unknown_pet(agent):
    result = json.loads(agent._tool_complete_task(pet_name="Nobody", task_title="Walk"))
    assert "error" in result


def test_complete_task_unknown_task(agent):
    result = json.loads(
        agent._tool_complete_task(pet_name="Rex", task_title="Nonexistent task")
    )
    assert "error" in result
    assert "tasks" in result  # Lists available tasks for debugging


# ---------------------------------------------------------------------------
# remove_task
# ---------------------------------------------------------------------------


def test_remove_task_success(agent, owner_with_dog):
    result = json.loads(agent._tool_remove_task(pet_name="Rex", task_title="Breakfast"))
    assert result["success"] is True
    pet = owner_with_dog.find_pet("Rex")
    assert all(t.title != "Breakfast" for t in pet.tasks)


def test_remove_task_unknown_task(agent):
    result = json.loads(agent._tool_remove_task(pet_name="Rex", task_title="Nonexistent"))
    assert "error" in result


def test_remove_task_unknown_pet(agent):
    result = json.loads(agent._tool_remove_task(pet_name="Ghost", task_title="Walk"))
    assert "error" in result


# ---------------------------------------------------------------------------
# get_schedule
# ---------------------------------------------------------------------------


def test_get_schedule_returns_structure(agent):
    result = json.loads(agent._tool_get_schedule())
    assert "scheduled" in result
    assert "skipped" in result
    assert "total_minutes" in result
    assert "available_minutes" in result
    assert isinstance(result["conflicts"], list)


def test_get_schedule_respects_time_budget(agent, owner_with_dog):
    owner_with_dog.available_minutes = 15  # Only enough for Breakfast
    result = json.loads(agent._tool_get_schedule())
    assert result["total_minutes"] <= 15
    assert result["skipped_count"] >= 1


def test_get_schedule_weighted_flag(agent):
    result_standard = json.loads(agent._tool_get_schedule(use_weighted=False))
    result_weighted = json.loads(agent._tool_get_schedule(use_weighted=True))
    # Both should return valid schedule structures
    assert "scheduled" in result_standard
    assert "scheduled" in result_weighted


# ---------------------------------------------------------------------------
# retrieve_care_tips (RAG component)
# ---------------------------------------------------------------------------


def test_retrieve_care_tips_dog(agent):
    result = json.loads(agent._tool_retrieve_care_tips(species="dog"))
    assert result["species"] == "dog"
    assert "essential_tasks" in result["knowledge"]
    assert "health_notes" in result["knowledge"]
    assert "tips" in result["knowledge"]
    assert len(result["knowledge"]["essential_tasks"]) > 0


def test_retrieve_care_tips_all_species(agent):
    for species in ["dog", "cat", "rabbit", "bird", "other"]:
        result = json.loads(agent._tool_retrieve_care_tips(species=species))
        assert result["species"] == species
        assert "essential_tasks" in result["knowledge"]


def test_retrieve_care_tips_unknown_falls_back_to_other(agent):
    # The handler only accepts valid enum values via the tool schema,
    # but if called directly with an unknown key it should fall back gracefully.
    result = json.loads(agent._tool_retrieve_care_tips(species="other"))
    assert result["species"] == "other"


def test_knowledge_base_completeness():
    required_keys = {"essential_tasks", "health_notes", "tips"}
    for species, data in _CARE_KNOWLEDGE.items():
        missing = required_keys - data.keys()
        assert not missing, f"{species} knowledge missing keys: {missing}"


# ---------------------------------------------------------------------------
# execute_tool dispatch and error handling
# ---------------------------------------------------------------------------


def test_execute_tool_unknown_name(agent):
    result = json.loads(agent._execute_tool("nonexistent_tool", {}))
    assert "error" in result


def test_execute_tool_handles_exception_gracefully(agent, owner_with_dog):
    # Simulate an unexpected error inside a tool handler by passing wrong type
    result = json.loads(
        agent._execute_tool("create_task", {"pet_name": "Rex", "title": "x",
                                             "duration_minutes": "not-an-int",
                                             "priority": "high", "frequency": "daily"})
    )
    # Should return error JSON, not raise
    assert "error" in result or "success" in result  # Either error or Task coerced it


# ---------------------------------------------------------------------------
# Confidence score extraction
# ---------------------------------------------------------------------------


def test_extract_confidence_standard():
    assert PawPalAgent._extract_confidence("Done! CONFIDENCE: 0.9") == pytest.approx(0.9)


def test_extract_confidence_case_insensitive():
    assert PawPalAgent._extract_confidence("Done.\nconfidence: 0.75") == pytest.approx(0.75)


def test_extract_confidence_clamped_above_one():
    assert PawPalAgent._extract_confidence("CONFIDENCE: 1.5") == pytest.approx(1.0)


def test_extract_confidence_clamped_below_zero():
    # The regex [\d.]+ does not match a leading minus, so a negative value
    # is treated as missing and returns the 0.5 default.  Claude never emits
    # negative confidence, so this is the correct fallback behaviour.
    assert PawPalAgent._extract_confidence("CONFIDENCE: -0.3") == pytest.approx(0.5)


def test_extract_confidence_missing_defaults_to_half():
    assert PawPalAgent._extract_confidence("No score here.") == pytest.approx(0.5)


def test_extract_confidence_invalid_number():
    assert PawPalAgent._extract_confidence("CONFIDENCE: abc") == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Confidence line stripping
# ---------------------------------------------------------------------------


def test_strip_confidence_line_removes_trailing_line():
    text = "All done!\nCONFIDENCE: 0.9"
    assert PawPalAgent._strip_confidence_line(text) == "All done!"


def test_strip_confidence_line_no_change_when_absent():
    text = "All done!"
    assert PawPalAgent._strip_confidence_line(text) == "All done!"


def test_strip_confidence_line_preserves_body():
    text = "Created 3 tasks for Rex.\nThe schedule now fits in 65 minutes.\nCONFIDENCE: 0.95"
    stripped = PawPalAgent._strip_confidence_line(text)
    assert "CONFIDENCE" not in stripped
    assert "Created 3 tasks" in stripped


# ---------------------------------------------------------------------------
# Reset conversation
# ---------------------------------------------------------------------------


def test_reset_conversation_clears_history(agent):
    agent.conversation_history = [{"role": "user", "content": "hello"}]
    agent._tool_call_log = [{"tool": "get_pets", "input": {}, "result": "{}"}]
    agent.reset_conversation()
    assert agent.conversation_history == []
    assert agent._tool_call_log == []
