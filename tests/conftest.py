"""A real Home Assistant instance that loads the blueprints from this repository.

Nothing here touches a real house: zones and pump readings are plain states set by
the tests, and timings are shortened so each scenario runs in a few seconds.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry,
    category_registry,
    condition,
    device_registry,
    entity,
    entity_registry,
    floor_registry,
    frame,
    issue_registry,
    label_registry,
    restore_state,
    template,
    translation,
    trigger,
)

ROOT = Path(__file__).parents[1]
BLUEPRINTS = ROOT / "blueprints"
NAMESPACE = "endoftheline-ha"


@pytest.fixture
async def hass(tmp_path):
    for domain_dir in BLUEPRINTS.iterdir():
        target = tmp_path / "blueprints" / domain_dir.name / NAMESPACE
        shutil.copytree(domain_dir, target)
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    # The same core helpers Home Assistant's bootstrap sets up before integrations load.
    loader.async_setup(instance)
    entity.async_setup(instance)
    frame.async_setup(instance)
    template.async_setup(instance)
    translation.async_setup(instance)
    device_registry.async_setup(instance)
    for registry in (
        area_registry,
        category_registry,
        device_registry,
        entity_registry,
        floor_registry,
        issue_registry,
        label_registry,
        restore_state,
    ):
        await registry.async_load(instance, load_empty=True)
    await condition.async_setup(instance)
    await trigger.async_setup(instance)
    # No web server or frontend in these tests.
    instance.config.skip_pip = True
    instance.config.components.update({"http", "websocket_api", "frontend"})
    # Automations attach their triggers only once Home Assistant is running.
    await instance.async_start()
    yield instance
    await instance.async_stop(force=True)
