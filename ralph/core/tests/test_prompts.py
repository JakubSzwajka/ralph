"""Tests for prompt building and constants."""
from pathlib import Path

from ralph.core import COMPLETION_SIGNAL, SYSTEM_PROMPT, RalphConfig, build_prompt


def test_completion_signal_is_xml_tag() -> None:
    assert "<promise>" in COMPLETION_SIGNAL
    assert "COMPLETE" in COMPLETION_SIGNAL


def test_system_prompt_contains_rules() -> None:
    assert "ONLY WORK ON A SINGLE TASK" in SYSTEM_PROMPT
    assert COMPLETION_SIGNAL in SYSTEM_PROMPT


def test_build_prompt_includes_prd_reference() -> None:
    config = RalphConfig(prd=Path("docs/prds/feature"))
    prompt = build_prompt(config)
    assert "@docs/prds/feature" in prompt


def test_build_prompt_includes_tasks_reference() -> None:
    config = RalphConfig(prd=Path("PRD.md"), tasks=Path("tasks.md"))
    prompt = build_prompt(config)
    assert "@tasks.md" in prompt


def test_build_prompt_no_tasks() -> None:
    config = RalphConfig(prd=Path("PRD.md"), tasks=None)
    prompt = build_prompt(config)
    assert COMPLETION_SIGNAL in prompt
