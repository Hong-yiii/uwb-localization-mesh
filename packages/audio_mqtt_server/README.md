# Audio MQTT Server

Server-side components for adaptive audio control based on user position.

## Components

### `follow_me_audio_server.py`
Contains `AdaptiveAudioServer` class that computes audio state based on position.

**Architecture:**
- **Does NOT handle MQTT publishing** - that's done by `ServerBringUpProMax`
- Computes audio commands and state (volumes, speaker pairs, execution times)
- Returns structured data to be published by the main server
- Pure computation logic with no MQTT dependencies

**Key Methods:**
- `compute_adaptive_audio_state(position, global_time)` - Returns commands for adaptive audio based on position
- `compute_zone_dj_state(global_time)` - Returns commands for Zone DJ mode (all speakers at 70%)
- `compute_pause_all_state(global_time)` - Returns pause commands for all speakers

**Audio Logic:**
- **Front/Back:** Y >= 300 → back speakers (RPi 1,0); Y < 300 → front speakers (RPi 2,3)
- **Left/Right Panning:** Volume varies around X=240 center
  - Moving right: increase LEFT speaker, decrease RIGHT speaker
  - Moving left: increase RIGHT speaker, decrease LEFT speaker

**Return Format:**
```python
{
    'commands': [
        {
            'command': 'start|pause|volume',
            'rpi_id': 0-3,  # Explicit RPi ID (not just pair name)
            'volume': 0-100 or None,
            'execute_time': float  # Global time for execution
        },
        ...
    ],
    'volumes': {0: vol, 1: vol, 2: vol, 3: vol},
    'current_pair': 'front' or 'back'  # For logging/status only
}
```

### `adaptive_audio_controller.py` (DEPRECATED)
Old standalone audio controller. Logic has been refactored into `AdaptiveAudioServer` in `follow_me_audio_server.py`.

## Audio Files

- `crazy-carls-brickhouse-tavern.wav`: Test audio file
- `funky-bossanova-guitar.wav`: Test audio file
- `guitar-on-loop.mp3`: Test audio file

## MQTT Topics

- `audio/commands/broadcast`: Commands for all speakers
- `audio/commands/rpi_{id}`: Commands for specific RPi (0-3)

## Message Format

MQTT messages published to RPi clients:

```json
{
  "command": "start|pause|volume",
  "execute_time": 1234567890.123,  // Absolute time (seconds since epoch)
  "rpi_id": 0,  // 0-3, or null for broadcast
  "command_id": "uuid",
  "target_volume": 70  // Only for "volume" command
}
```

**Note:** RPi clients only need `execute_time` to know when to execute. They calculate their own delay by comparing `execute_time` to their local `time.time()`.

## Architecture Flow

```
ServerBringUpProMax (Demos/UnifiedDemo/server_bring_up_with_audio.py)
    ├─ Tracks user position via UWB/PGO
    ├─ Runs _adaptive_audio_loop() or _zone_dj_loop() in background threads
    │
    ├─→ AdaptiveAudioServer (follow_me_audio_server.py)
    │   └─ Computes audio state based on position
    │   └─ Returns commands with explicit rpi_id values (0-3)
    │
    └─→ Publishes MQTT commands to topics:
        ├─ audio/commands/rpi_0
        ├─ audio/commands/rpi_1
        ├─ audio/commands/rpi_2
        ├─ audio/commands/rpi_3
        └─ audio/commands/broadcast (if rpi_id is null)
            ↓
        FollowMeAudioClient (on each RPi)
            └─ Receives commands and plays audio
```

## Usage

The audio server is used by `ServerBringUpProMax` (see [`Demos/UnifiedDemo/server_bring_up_with_audio.py`](../../Demos/UnifiedDemo/server_bring_up_with_audio.py)). Ensure the repo root is on `sys.path`, and either add `Demos/UnifiedDemo` to `sys.path` or run from that directory:

```python
from server_bring_up_with_audio import ServerBringUpProMax
from packages.uwb_mqtt_server.config import MQTTConfig

server = ServerBringUpProMax(mqtt_config=MQTTConfig(...))
server.start()

# Start adaptive audio (polls position every 100ms)
server.adaptive_audio_start()

# Or start zone DJ mode (all speakers at 70%)
server.zone_dj_start()

# Stop audio
server.adaptive_audio_stop()
# or
server.zone_dj_stop()
```

## Key Design Decisions

1. **Separation of Concerns:**
   - `AdaptiveAudioServer`: Pure computation, no MQTT
   - `ServerBringUpProMax`: Handles MQTT publishing and threading

2. **Explicit RPi IDs:**
   - Even though audio logic uses "front"/"back" pairs conceptually, commands contain explicit `rpi_id` values (0-3)
   - This ensures correct MQTT topic routing (`audio/commands/rpi_{id}`)

3. **Threading:**
   - `_adaptive_audio_loop()` runs in a background thread, polling `user_position` every 100ms
   - `_zone_dj_loop()` runs in a separate thread for Zone DJ mode
   - Both can be started/stopped independently
