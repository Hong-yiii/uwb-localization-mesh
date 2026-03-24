# Audio MQTT Client

Raspberry Pi audio player that receives and executes synchronized audio commands over MQTT.

## Components

### `synchronized_audio_player_rpi.py` (use this)

Main RPi entry point for the follow-me / adaptive audio stack. Subscribes to `audio/commands/rpi_{id}` and `audio/commands/broadcast`, plays the correct stereo channel per corner speaker, and honors `execute_time` in payloads for sync.

**Usage (from repo root on the Pi):**

```bash
python packages/audio_mqtt_client/synchronized_audio_player_rpi.py \
  --id 0 --wav your-track.wav --broker YOUR_BROKER_IP
```

Place `.wav` files under `Demos/Audio_Library/` at the repo root (create the folder; no sample audio is bundled), or pass a path the script resolves.

Run **in parallel** with `Anchor_bring_up.py` on the same Pi (`--id` must match `--anchor-id`). Same broker port (**1884**) and default credentials as [`server_bring_up_with_audio.py`](../../Demos/UnifiedDemo/server_bring_up_with_audio.py) / Unified Demo unless you change Mosquitto.

Deployment context: **[`README.md`](../../README.md)** (bring-ups), **[`Demos/UnifiedDemo/README.md`](../../Demos/UnifiedDemo/README.md)** (section 3 — optional audio per RPi).


## Speaker Configuration

- **RPi 0, 3:** RIGHT channel (play right channel of stereo audio)
- **RPi 1, 2:** LEFT channel (play left channel of stereo audio)

**Front/Back Pairing:**

- **Front:** RPi 2 (LEFT), RPi 3 (RIGHT)
- **Back:** RPi 1 (LEFT), RPi 0 (RIGHT)

## Audio Setup

Configured for Raspberry Pi 3.5mm headphone jack:

- Uses ALSA driver
- ALSA card 2 (3.5mm jack)
- Sample rate: 22050 Hz
- Stereo (2 channels)
- Buffer: 512

## Commands

- `start`: Start playing audio (loops forever)
- `pause`: Pause audio
- `volume`: Set volume (0-100)
- `load_track`: Load and switch to a new audio file

## MQTT Subscriptions

- `audio/commands/broadcast`: All speakers
- `audio/commands/rpi_{id}`: Specific speaker
