"""Checks on the repository itself: every blueprint is valid, importable and documented."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

import pytest
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.util.yaml import load_yaml_dict

ROOT = Path(__file__).parents[1]
REPO = "https://github.com/EndOfTheLine-HA/ha-blueprints"
EM_DASH = chr(0x2014)
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv"}
BLUEPRINT_FILES = sorted((ROOT / "blueprints").glob("*/*.yaml"))
TEXT_FILES = [
    path
    for path in ROOT.rglob("*")
    if path.is_file()
    and not SKIP_DIRS.intersection(path.parts)
    and path.suffix in {".md", ".yaml", ".yml", ".py", ".toml", ".txt", ""}
]


def test_there_is_at_least_one_blueprint():
    assert BLUEPRINT_FILES


@pytest.mark.parametrize("path", BLUEPRINT_FILES, ids=lambda p: p.name)
def test_blueprint_is_valid_and_points_at_itself(path: Path):
    domain = path.parent.name
    blueprint = Blueprint(load_yaml_dict(str(path)), expected_domain=domain, schema=BLUEPRINT_SCHEMA)
    relative = path.relative_to(ROOT).as_posix()
    assert blueprint.metadata["source_url"] == f"{REPO}/blob/main/{relative}"
    assert blueprint.metadata["homeassistant"]["min_version"]


@pytest.mark.parametrize("path", BLUEPRINT_FILES, ids=lambda p: p.name)
def test_readme_has_an_import_link_for_each_blueprint(path: Path):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    source = f"{REPO}/blob/main/{path.relative_to(ROOT).as_posix()}"
    link = "https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=" + quote(source, safe="")
    assert link in readme


@pytest.mark.parametrize("path", TEXT_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_text_has_no_em_dashes_or_private_identifiers(path: Path):
    text = path.read_text(encoding="utf-8")
    assert EM_DASH not in text and "&" + "mdash;" not in text
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text), "looks like an IP address"
    assert not re.search(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b", text), "looks like a MAC address"
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    assert not emails, f"email address found: {emails}"
