from pathlib import Path

SKILLS_ROOT = Path(__file__).parents[2] / "agent-skills"


def test_memento_skill_package_contains_coordinator_and_specialists() -> None:
    expected = {
        "library-development-workflow",
        "library-find-context",
        "library-record",
        "library-checkpoint",
        "library-resume",
    }

    assert {
        path.parent.name for path in SKILLS_ROOT.glob("*/SKILL.md")
    } == expected


def test_coordinator_routes_every_specialist_workflow() -> None:
    content = (
        SKILLS_ROOT / "library-development-workflow" / "SKILL.md"
    ).read_text(encoding="utf-8")

    for specialist in (
        "library-find-context",
        "library-record",
        "library-checkpoint",
        "library-resume",
    ):
        assert f"../{specialist}/SKILL.md" in content

    assert "../references/memento-contract.md" in content
    assert "implementation_snapshot" in content
    assert "test_evidence" in content
    assert "task switch" in content.lower()
