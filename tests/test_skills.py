"""Contract tests for Product Forge skills created with skill-creator."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, f"missing frontmatter: {path}"
    value = yaml.safe_load(match.group(1))
    assert isinstance(value, dict), f"frontmatter must be a mapping: {path}"
    return value


def test_every_product_forge_skill_has_skill_creator_contract() -> None:
    skill_files = sorted(SKILLS.glob("pf-*/SKILL.md"))
    assert len(skill_files) == 16
    for skill_file in skill_files:
        skill_name = skill_file.parent.name
        frontmatter = _frontmatter(skill_file)
        assert frontmatter["name"] == skill_name
        assert isinstance(frontmatter["description"], str)
        assert frontmatter["description"].strip()
        assert len(skill_file.read_text(encoding="utf-8").splitlines()) <= 500

        interface_path = skill_file.parent / "agents" / "openai.yaml"
        interface = yaml.safe_load(interface_path.read_text(encoding="utf-8"))
        prompt = interface["interface"]["default_prompt"]
        assert f"${skill_name}" in prompt


def test_skill_index_matches_skill_directories() -> None:
    index = yaml.safe_load((SKILLS / "index.json").read_text(encoding="utf-8"))
    indexed = {item["name"] for item in index["skills"]}
    actual = {path.parent.name for path in SKILLS.glob("pf-*/SKILL.md")}
    assert indexed == actual
