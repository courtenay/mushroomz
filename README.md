# Mushroom Lighting Controller

A Python-based reactive lighting system for giant mushrooms (or any DMX fixtures). Controls RGB PAR lights via Art-Net, with inputs from PS4 controller, audio-reactive OSC, and plant bio-resistance sensors.

Tip: you can run the audio-to-OSC app separately anywhere on your network. 
  % source venv/bin/activate
  % python audio_to_osc.py --osc-port 8000


## Features

- **Per-mushroom scene control** - Each mushroom can run a different lighting scene
- **Multiple input sources:**
  - PS4 controller (USB/Bluetooth via pygame)
  - OSC server for audio reactivity and bio sensors
  - Idle timeout with automatic pastel fade
- **Web UI** for live configuration at `http://localhost:8085`
- **Fixture discovery** - Flash any DMX address to identify physical lights
- **JSON config persistence** - Save and reload configurations

## Scenes

| Scene | Description |
|-------|-------------|
| **Pastel Fade** | Gentle cycling through soft colors (default/idle) |
| **Audio Pulse** | Beat-reactive with intensity from audio levels |
| **Bio Glow** | Maps plant resistance to color (green→yellow) |
| **Manual** | Direct control via PS4 analog sticks |

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
./venv/bin/python main.py
```

Opens:
- **Web UI**: http://localhost:8085
- **Art-Net**: Sends to configured IP (default: 169.254.219.50)
- **OSC**: Listens on port 8000

## PS4 Controller Mapping

| Input | Action |
|-------|--------|
| D-pad Up | Select all mushrooms |
| D-pad Left/Down/Right | Select mushroom 1/2/3 |
| Triangle | Pastel Fade scene |
| Circle | Audio Pulse scene |
| Square | Bio Glow scene |
| X | Manual control scene |
| Options | Blackout toggle |
| Left stick | Hue / Saturation (manual mode) |
| Right stick | Brightness / Speed |

## Configuration

Edit `config.json` or use the web UI:

```json
{
  "artnet_ip": "169.254.219.50",
  "artnet_universe": 0,
  "dmx_fps": 40,
  "osc_port": 8000,
  "idle_timeout": 30.0,
  "web_port": 8085,
  "mushrooms": [
    {
      "name": "Mushroom 1",
      "fixtures": [
        {"name": "Cap", "address": 1, "channels": 3},
        {"name": "Stem", "address": 4, "channels": 3}
      ]
    }
  ],
  "scene_params": {
    "pastel_fade": {"cycle_duration": 30.0, "phase_offset": 0.25},
    "audio_pulse": {"base_hue": 280.0, "decay_rate": 3.0},
    "bio_glow": {
      "low_color": [120, 0.6, 0.4],
      "high_color": [60, 0.8, 0.9]
    }
  }
}
```

## OSC Messages

The system listens for these OSC messages:

| Address | Args | Description |
|---------|------|-------------|
| `/audio/beat` | float intensity | Beat detection trigger |
| `/audio/level` | float level, low, mid, high | Audio levels (0-1) |
| `/bio/plant1` | float resistance | Plant 1 resistance → Mushroom 1 |
| `/bio/plant2` | float resistance | Plant 2 resistance → Mushroom 2 |
| `/bio/plant3` | float resistance | Plant 3 resistance → Mushroom 3 |
| `/bio/plant4` | float resistance | Plant 4 resistance → Mushroom 4 |

## Web API

### Config
- `GET /api/config` - Full configuration
- `POST /api/config/save` - Save to JSON file
- `POST /api/config/reload` - Reload from file

### Mushrooms
- `GET /api/mushrooms` - List all mushrooms
- `POST /api/mushrooms` - Add mushroom
- `PUT /api/mushrooms/{id}` - Update mushroom
- `DELETE /api/mushrooms/{id}` - Delete mushroom
- `PUT /api/mushrooms/{id}/scene` - Set scene

### Fixtures
- `POST /api/fixtures/flash` - Flash any DMX address
- `POST /api/mushrooms/{id}/flash` - Flash all fixtures
- `POST /api/mushrooms/{id}/fixtures/{idx}/flash` - Flash single fixture

### System
- `GET /api/status` - Current state
- `POST /api/blackout` - Toggle blackout

## Architecture

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  PS4 Controller │  │   OSC Server    │  │   Web Server    │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │    Event Bus      │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Scene Manager   │
                    │  (per-mushroom)   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Art-Net Output  │
                    └───────────────────┘
```

## Project Structure

```
artnet/
├── main.py              # Entry point, asyncio event loop
├── config.py            # Dataclasses with serialization
├── config_manager.py    # JSON load/save
├── events.py            # Event bus and types
├── scene_manager.py     # Per-mushroom scene state machine
├── requirements.txt
├── config.json          # Persisted configuration
├── inputs/
│   ├── ps4.py           # PS4 controller (pygame)
│   ├── osc_server.py    # OSC listener
│   └── idle.py          # Idle timeout
├── scenes/
│   ├── base.py          # Abstract scene class
│   ├── pastel_fade.py   # Gentle color cycling
│   ├── audio_pulse.py   # Beat reactive
│   ├── bio_glow.py      # Plant resistance
│   └── manual.py        # Direct control
├── fixtures/
│   ├── rgb_par.py       # RGB fixture + Color class
│   └── mushroom.py      # Mushroom fixture group
├── output/
│   └── artnet.py        # Art-Net DMX output
└── web/
    ├── server.py        # FastAPI app
    ├── api.py           # REST endpoints
    └── static/
        └── index.html   # Tailwind + Alpine.js UI
```

## Dependencies

- `pygame` - PS4 controller input
- `python-osc` - OSC server
- `stupidArtnet` - Art-Net protocol
- `fastapi` - Web API
- `uvicorn` - ASGI server

## License

MIT
