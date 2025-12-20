"""REST API endpoints for the lighting controller."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import Config, MushroomConfig, FixtureConfig

router = APIRouter()


# Pydantic models for request/response
class FixtureModel(BaseModel):
    name: str
    address: int
    channels: int = 3


class MushroomModel(BaseModel):
    name: str
    fixtures: list[FixtureModel] = []


class NetworkModel(BaseModel):
    artnet_ip: str
    artnet_universe: int
    osc_port: int
    dmx_fps: int


class SceneChangeModel(BaseModel):
    scene: str


class FlashModel(BaseModel):
    address: int
    channels: int = 3
    color: list[int] = [255, 255, 255]  # Default white
    duration: float = 1.0  # Seconds


class StatusResponse(BaseModel):
    blackout: bool
    selected_mushrooms: list[int]
    mushroom_scenes: dict[int, str]


def get_controller(request: Request):
    """Get the lighting controller from app state."""
    return request.app.state.controller


# === Config Endpoints ===

@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """Get the full configuration."""
    controller = get_controller(request)
    return controller.config_manager.config.to_dict()


@router.put("/config")
async def update_config(request: Request, data: dict[str, Any]) -> dict[str, str]:
    """Update the full configuration."""
    controller = get_controller(request)
    controller.config_manager.update_from_dict(data)
    return {"status": "ok"}


@router.post("/config/save")
async def save_config(request: Request) -> dict[str, str]:
    """Save configuration to JSON file."""
    controller = get_controller(request)
    controller.config_manager.save()
    return {"status": "saved"}


@router.post("/config/reload")
async def reload_config(request: Request) -> dict[str, Any]:
    """Reload configuration from JSON file."""
    controller = get_controller(request)
    config = controller.config_manager.reload()
    return config.to_dict()


# === Status Endpoints ===

@router.get("/status")
async def get_status(request: Request) -> dict[str, Any]:
    """Get current system status."""
    controller = get_controller(request)
    sm = controller.scene_manager

    mushroom_scenes = {}
    for mushroom in controller.mushrooms:
        scene = sm._scenes.get(mushroom.id)
        mushroom_scenes[mushroom.id] = scene.name if scene else "Unknown"

    return {
        "blackout": sm._blackout,
        "selected_mushrooms": list(sm._selected),
        "mushroom_scenes": mushroom_scenes,
    }


@router.post("/blackout")
async def toggle_blackout(request: Request) -> dict[str, bool]:
    """Toggle blackout mode."""
    controller = get_controller(request)
    controller.scene_manager._blackout = not controller.scene_manager._blackout
    return {"blackout": controller.scene_manager._blackout}


# === Mushroom Endpoints ===

@router.get("/mushrooms")
async def list_mushrooms(request: Request) -> list[dict[str, Any]]:
    """List all mushrooms with their current state."""
    controller = get_controller(request)
    result = []
    for i, mc in enumerate(controller.config_manager.config.mushrooms):
        scene = controller.scene_manager._scenes.get(i)
        result.append({
            "id": i,
            "name": mc.name,
            "fixtures": [f.to_dict() for f in mc.fixtures],
            "scene": scene.name if scene else "Unknown",
        })
    return result


@router.post("/mushrooms")
async def add_mushroom(request: Request, mushroom: MushroomModel) -> dict[str, Any]:
    """Add a new mushroom."""
    controller = get_controller(request)
    config = controller.config_manager.config

    new_mushroom = MushroomConfig(
        name=mushroom.name,
        fixtures=[
            FixtureConfig(f.name, f.address, f.channels)
            for f in mushroom.fixtures
        ],
    )
    config.mushrooms.append(new_mushroom)
    controller.config_manager._notify_change()

    return {"id": len(config.mushrooms) - 1, "name": mushroom.name}


@router.put("/mushrooms/{mushroom_id}")
async def update_mushroom(
    request: Request, mushroom_id: int, mushroom: MushroomModel
) -> dict[str, str]:
    """Update a mushroom's configuration."""
    controller = get_controller(request)
    config = controller.config_manager.config

    if mushroom_id < 0 or mushroom_id >= len(config.mushrooms):
        raise HTTPException(status_code=404, detail="Mushroom not found")

    config.mushrooms[mushroom_id] = MushroomConfig(
        name=mushroom.name,
        fixtures=[
            FixtureConfig(f.name, f.address, f.channels)
            for f in mushroom.fixtures
        ],
    )
    controller.config_manager._notify_change()

    return {"status": "ok"}


@router.delete("/mushrooms/{mushroom_id}")
async def delete_mushroom(request: Request, mushroom_id: int) -> dict[str, str]:
    """Delete a mushroom."""
    controller = get_controller(request)
    config = controller.config_manager.config

    if mushroom_id < 0 or mushroom_id >= len(config.mushrooms):
        raise HTTPException(status_code=404, detail="Mushroom not found")

    config.mushrooms.pop(mushroom_id)
    controller.config_manager._notify_change()

    return {"status": "deleted"}


# === Scene Endpoints ===

@router.get("/scenes")
async def list_scenes() -> list[dict[str, str]]:
    """List available scenes."""
    return [
        {"id": "pastel_fade", "name": "Pastel Fade", "description": "Gentle color cycling"},
        {"id": "audio_pulse", "name": "Audio Pulse", "description": "Beat-reactive lighting"},
        {"id": "bio_glow", "name": "Bio Glow", "description": "Plant resistance reactive"},
        {"id": "manual", "name": "Manual", "description": "Direct controller control"},
    ]


@router.get("/mushrooms/{mushroom_id}/scene")
async def get_mushroom_scene(request: Request, mushroom_id: int) -> dict[str, str]:
    """Get the current scene for a mushroom."""
    controller = get_controller(request)
    scene = controller.scene_manager._scenes.get(mushroom_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="Mushroom not found")
    return {"scene": scene.name}


@router.put("/mushrooms/{mushroom_id}/scene")
async def set_mushroom_scene(
    request: Request, mushroom_id: int, data: SceneChangeModel
) -> dict[str, str]:
    """Set the scene for a mushroom."""
    controller = get_controller(request)
    sm = controller.scene_manager

    if mushroom_id < 0 or mushroom_id >= len(controller.mushrooms):
        raise HTTPException(status_code=404, detail="Mushroom not found")

    # Map scene name to class
    scene_map = {
        "pastel_fade": "PastelFadeScene",
        "audio_pulse": "AudioPulseScene",
        "bio_glow": "BioGlowScene",
        "manual": "ManualScene",
    }

    scene_id = data.scene.lower().replace(" ", "_")
    if scene_id not in scene_map:
        raise HTTPException(status_code=400, detail=f"Unknown scene: {data.scene}")

    # Import and instantiate the scene
    from scenes import PastelFadeScene, AudioPulseScene, BioGlowScene, ManualScene
    scene_classes = {
        "pastel_fade": PastelFadeScene,
        "audio_pulse": AudioPulseScene,
        "bio_glow": BioGlowScene,
        "manual": ManualScene,
    }

    old_scene = sm._scenes.get(mushroom_id)
    if old_scene:
        old_scene.deactivate()

    new_scene = scene_classes[scene_id]()
    new_scene.activate()
    sm._scenes[mushroom_id] = new_scene

    return {"status": "ok", "scene": new_scene.name}


@router.get("/scenes/{scene_id}/params")
async def get_scene_params(request: Request, scene_id: str) -> dict[str, Any]:
    """Get parameters for a scene."""
    controller = get_controller(request)
    params = controller.config_manager.config.scene_params

    param_map = {
        "pastel_fade": params.pastel_fade,
        "audio_pulse": params.audio_pulse,
        "bio_glow": params.bio_glow,
        "manual": params.manual,
    }

    if scene_id not in param_map:
        raise HTTPException(status_code=404, detail="Scene not found")

    return param_map[scene_id]


@router.put("/scenes/{scene_id}/params")
async def update_scene_params(
    request: Request, scene_id: str, params: dict[str, Any]
) -> dict[str, str]:
    """Update parameters for a scene."""
    controller = get_controller(request)
    scene_params = controller.config_manager.config.scene_params

    param_map = {
        "pastel_fade": scene_params.pastel_fade,
        "audio_pulse": scene_params.audio_pulse,
        "bio_glow": scene_params.bio_glow,
        "manual": scene_params.manual,
    }

    if scene_id not in param_map:
        raise HTTPException(status_code=404, detail="Scene not found")

    param_map[scene_id].update(params)
    controller.config_manager._notify_change()

    return {"status": "ok"}


# === Network Endpoints ===

@router.get("/network")
async def get_network(request: Request) -> dict[str, Any]:
    """Get network configuration."""
    controller = get_controller(request)
    config = controller.config_manager.config
    return {
        "artnet_ip": config.artnet_ip,
        "artnet_universe": config.artnet_universe,
        "osc_port": config.osc_port,
        "dmx_fps": config.dmx_fps,
    }


@router.put("/network")
async def update_network(request: Request, network: NetworkModel) -> dict[str, str]:
    """Update network configuration."""
    controller = get_controller(request)
    config = controller.config_manager.config

    config.artnet_ip = network.artnet_ip
    config.artnet_universe = network.artnet_universe
    config.osc_port = network.osc_port
    config.dmx_fps = network.dmx_fps

    controller.config_manager._notify_change()

    return {"status": "ok", "note": "Restart required for network changes to take effect"}


# === Fixture Discovery Endpoints ===

@router.post("/fixtures/flash")
async def flash_fixture(request: Request, flash: FlashModel) -> dict[str, Any]:
    """Flash a fixture to identify it. Temporarily overrides DMX output."""
    controller = get_controller(request)

    # Store the flash request in controller
    controller.add_flash(flash.address, flash.channels, flash.color, flash.duration)

    return {"status": "flashing", "address": flash.address}


@router.post("/mushrooms/{mushroom_id}/fixtures/{fixture_idx}/flash")
async def flash_mushroom_fixture(
    request: Request, mushroom_id: int, fixture_idx: int
) -> dict[str, Any]:
    """Flash a specific fixture on a mushroom."""
    controller = get_controller(request)
    config = controller.config_manager.config

    if mushroom_id < 0 or mushroom_id >= len(config.mushrooms):
        raise HTTPException(status_code=404, detail="Mushroom not found")

    mushroom_config = config.mushrooms[mushroom_id]
    if fixture_idx < 0 or fixture_idx >= len(mushroom_config.fixtures):
        raise HTTPException(status_code=404, detail="Fixture not found")

    fixture = mushroom_config.fixtures[fixture_idx]
    controller.add_flash(fixture.address, fixture.channels, [255, 255, 255], 1.0)

    return {"status": "flashing", "fixture": fixture.name, "address": fixture.address}


@router.post("/mushrooms/{mushroom_id}/flash")
async def flash_all_mushroom_fixtures(request: Request, mushroom_id: int) -> dict[str, Any]:
    """Flash all fixtures on a mushroom."""
    controller = get_controller(request)
    config = controller.config_manager.config

    if mushroom_id < 0 or mushroom_id >= len(config.mushrooms):
        raise HTTPException(status_code=404, detail="Mushroom not found")

    mushroom_config = config.mushrooms[mushroom_id]
    for fixture in mushroom_config.fixtures:
        controller.add_flash(fixture.address, fixture.channels, [255, 255, 255], 1.0)

    return {"status": "flashing", "mushroom": mushroom_config.name, "fixtures": len(mushroom_config.fixtures)}
