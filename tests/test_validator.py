from rpg_assistant.ingestion.semantic.schemas import CHUNK_TYPES, ENTITY_TYPES
from rpg_assistant.ingestion.semantic.validator import ValidationResult, _contains_gm_only_leak


def test_chunk_types_include_core_labels():
    assert "npc" in CHUNK_TYPES
    assert "secret" in CHUNK_TYPES
    assert "location" in ENTITY_TYPES


def test_player_safe_spoiler_detection():
    assert _contains_gm_only_leak("This is a hidden truth about the cult.") == "hidden truth"
    assert _contains_gm_only_leak("A tired innkeeper.") is None


def test_validation_result_serializable():
    result = ValidationResult(valid=False, errors=[])
    payload = result.to_dict()
    assert payload["valid"] is False
    assert payload["errors"] == []
