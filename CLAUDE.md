# Claude Code Context for Mushroom Lighting Controller

## Project Overview

This is a Python asyncio-based DMX lighting controller for an art installation featuring giant mushrooms. Each mushroom has multiple RGB PAR fixtures controlled via Art-Net. The system supports multiple input sources (PS4 controller, OSC audio/bio sensors) and a web UI for configuration.

## Key Architecture Decisions

### Per-Mushroom Scenes
Each mushroom runs its own scene instance independently. The scene manager maintains a dict of `{mushroom_id: Scene}`. This allows different mushrooms to show different effects simultaneously.

### Event-Driven Architecture
All inputs publish to an async `EventBus`. The scene manager subscribes to events and routes them to appropriate mushrooms/scenes. This decouples input handling from scene logic.

### Flash Override System
The `LightingController` has a `_flash_queue` that temporarily overrides DMX output for fixture identification. Flashes are time-based and automatically expire.

### Config Hot-Reload
`ConfigManager` supports live config updates via the web API. Changes to scene parameters take effect immediately. Network changes require restart.

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point, `LightingController` class, asyncio task orchestration |
| `config.py` | Dataclasses with `to_dict()`/`from_dict()` for JSON serialization |
| `scene_manager.py` | Routes events to per-mushroom scenes, handles PS4 button mapping |
| `scenes/base.py` | Abstract `Scene` class - implement `update()` and `handle_event()` |
| `fixtures/rgb_par.py` | `Color` class with HSV conversion, `RGBFixture` with smoothing |
| `web/api.py` | FastAPI REST endpoints, all the `/api/*` routes |

## Common Tasks

### Adding a New Scene
1. Create `scenes/my_scene.py` extending `Scene`
2. Implement `update(mushroom, dt)` and optionally `handle_event(event, mushroom)`
3. Add to `scenes/__init__.py`
4. Add to `scene_manager.py` `SCENE_BUTTONS` dict
5. Add to `web/api.py` scene list and `scene_classes` dict
6. Add params to `config.py` `SceneParams` if needed

### Adding a New Input Source
1. Create handler in `inputs/` following the pattern of `ps4.py` or `osc_server.py`
2. Publish events to `EventBus` using appropriate `EventType`
3. Add to `main.py` as an asyncio task
4. Subscribe in `scene_manager.py` if scenes need to react

### Adding API Endpoints
1. Add Pydantic model if needed in `web/api.py`
2. Add route function with `@router.get/post/put/delete`
3. Access controller via `get_controller(request)`

## DMX Addressing
- Fixtures use 1-indexed DMX addresses (1-512)
- RGB = 3 channels (R, G, B)
- RGBW = 4 channels (R, G, B, W)
- Default config has 4 mushrooms starting at addresses 1, 10, 19, 28

## Web UI
Single HTML file using CDN-loaded Tailwind CSS and Alpine.js. No build step required. State managed in Alpine.js `app()` function with API calls via fetch.

## Testing Notes
- Graceful fallback if dependencies missing (pygame, python-osc, stupidArtnet)
- Art-Net runs in "simulation mode" without stupidArtnet
- Web server graceful degradation without fastapi/uvicorn

## OSC Message Format
Audio software should send:
- `/audio/beat` with float 0-1 intensity on beat
- `/audio/level` with floats for overall, low, mid, high (0-1)

Plant sensors should send:
- `/bio/plantN` where N matches mushroom number (1-indexed)
- Single float arg for resistance value (0-1, normalized)

## Dependencies
```
pygame>=2.5.0
python-osc>=1.8.0
stupidArtnet>=1.4.0
fastapi>=0.109.0
uvicorn>=0.27.0
```

## Running
```bash
source venv/bin/activate
python main.py
```

Web UI at http://localhost:8085 (port configurable in config.json)
