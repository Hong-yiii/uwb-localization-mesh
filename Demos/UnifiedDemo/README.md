# Unified Demo

**Role in this repository:** **UWB localization** (MQTT → binning → edges → PGO → `user_position`) is the **core**—see the root [`README.md`](../../README.md) and [`packages/`](../../packages/). The Unified Demo is a **reference application** for developers: it shows **one way** to import the laptop bring-up class, run it **in the same process** as a GUI, and build tabs that consume **`user_position`** and optional audio APIs. Use it as a **blueprint** for your own app; you can instead run [`server_bring_up_with_audio.py`](server_bring_up_with_audio.py) headlessly (or use root [`Server_bring_up.py`](../../Server_bring_up.py) for localization-only) and link your UI however you prefer.

**What this app does:** PyQt5 desktop shell with **embedded** [`ServerBringUpProMax`](server_bring_up_with_audio.py) (localization + audio orchestration) and three tabs:

| Tab | Package | Illustrates |
|-----|---------|-------------|
| **PGO Data** | `pgo_data_widget` | Plotting live position from the solver |
| **Adaptive Audio** | `adaptive_audio_widget` | Floorplan + fixed zones + speaker UI on top of position |
| **Zone DJ** | `zone_dj_widget` | User zones, queues, and MQTT-backed audio commands |

There is no in-repo “simulation” server and no fallback to other bring-up scripts in `main_demo.py`—only this embedded server path.

**Will audio “just work” on the Pis?** **No.** Localization works with **only** `Anchor_bring_up.py` on each Pi. The demo’s **Adaptive Audio** / **Zone DJ** tabs drive **`ServerBringUpProMax`**, which **publishes** commands over MQTT—but **physical playback** requires a **separate** process on each speaker Pi: [`synchronized_audio_player_rpi.py`](../../packages/audio_mqtt_client/synchronized_audio_player_rpi.py). There is **no** merged anchor+audio bring-up script in this repo (two MQTT clients per Pi: UWB + player).

---

## Requirements

- Python 3.8+ and dependencies from the repo root [`pyproject.toml`](../../pyproject.toml) (e.g. `pip install -e .`).
- **Mosquitto** (or compatible broker) reachable from the laptop and from each anchor Raspberry Pi.
- **Four anchors** publishing UWB measurements (see repository [`README.md`](../../README.md) for topic and payload format).

---

## Deploy (recommended order)

### 1. Broker

Run MQTT on the port and credentials you will use everywhere (defaults below use **1884** and user **`laptop`** / password **`laptop`** — create matching users in Mosquitto or use `allow_anonymous true` for lab use only).

Example minimal listener (adapt paths and security for production):

```bash
printf '%s\n' "listener 1884" "allow_anonymous true" > mosquitto.conf
mosquitto -c mosquitto.conf
```

### 2. Anchors — UWB (one terminal or service per RPi)

Point each anchor at the **broker hostname or IP** (the machine running Mosquitto, often the same laptop as the demo):

```bash
python Anchor_bring_up.py --anchor-id 0 --broker <BROKER_IP>
# repeat for anchors 1–3
```

Anchors use **port 1884** (see `Anchor_bring_up.py`). Ensure firewall rules allow MQTT from the Pi subnet.

### 3. Anchors — audio players (optional, second process per RPi)

Localization only needs step 2. For **real speakers** at the four corners, run an **additional** process on each Pi in parallel with `Anchor_bring_up.py`:

```bash
# From repo root on each RPi; use matching --id and same --broker as UWB
python packages/audio_mqtt_client/synchronized_audio_player_rpi.py \
  --id 0 --wav "your-track.wav" --broker <BROKER_IP>
```

- **`--id`:** must be **0–3** and match that Pi’s anchor id. The player subscribes to `audio/commands/rpi_{id}` and to `audio/commands/broadcast`.
- **`--wav`:** filename under `Demos/Audio_Library/` (create that folder at repo root and add `.wav` files—they are not bundled) or another path the player resolves (see `synchronized_audio_player_rpi.py`).
- **Broker auth:** defaults match the laptop server (**user / password `laptop` / `laptop`**, port **1884**). If your broker differs, align Mosquitto users or use anonymous mode consistently.
- **Hardware:** pygame + ALSA, RPi 3.5 mm jack (see [`packages/audio_mqtt_client/README.md`](../../packages/audio_mqtt_client/README.md) for sample rate, stereo channel per RPi).

There is **no** merged “UWB + audio” script in this repo; UWB and audio are two MQTT clients on the same Pi.

### 4. Unified Demo (laptop)

From the **repository root**:

```bash
python Demos/UnifiedDemo/main_demo.py
```

This starts **one** `ServerBringUpProMax` inside the GUI. Do **not** run `python Demos/UnifiedDemo/server_bring_up_with_audio.py` in parallel unless you intend to run a second server (not supported for this UI).

**Floorplan images:** place PNG/JPG under `Demos/UnifiedDemo/assets/floorplans/` or use **Open Image…** after launch. Use **Mark Corners** or **Auto Transform** before zones and coordinates behave correctly.

---

## Configuration

### QSettings namespace

Stored under organization **UWB-Localization**, application **UnifiedDemo** (standard Qt `QSettings`).

| Key | Default | Role |
|-----|---------|------|
| `mqtt/broker` | `localhost` | Broker hostname or IP for **embedded** `ServerBringUpProMax` |
| `mqtt/port` | `1884` | Broker port |
| `mqtt/username` | `laptop` | MQTT user (or empty for anonymous) |
| `mqtt/password` | `laptop` | MQTT password |
| `world/width_m` | `4.80` | Room width (m) for floorplan grid |
| `world/height_m` | `6.00` | Room height (m) |
| `grid/cols`, `grid/rows` | `8`, `10` | Grid layout |
| `adaptive/split_y_m` | `3.00` | Adaptive Audio zone split (m) |
| `zonedj/default_zone_radius_m` | `0.25` | Default Zone DJ radius (m) |
| `floorplan/default_path` | *(empty)* | Optional default image for toolbar load |

Defaults are primed in [`packages/services/settings.py`](../../packages/services/settings.py). The **Settings (⚙)** dialog edits zone radius and default floorplan path only; change **`mqtt/*`** with a Qt settings editor, your own small script, or the platform store (e.g. macOS `defaults` for the app id).

**LAN deployment:** set `mqtt/broker` to the laptop’s IP on the Wi‑Fi/Ethernet used by the Pis. Anchor `--broker` must target the **same** broker host.

---

## Architecture (concise)

```
Anchors --MQTT (uwb/anchor/+/vector)--> ServerBringUpProMax  <---+
       (same process)                                            |
                                                                 |
MainWindow polls server.user_position --------------------------+
       |
       v
    AppBus.pointerUpdated  --->  PGO / Adaptive / Zone DJ widgets
       ^
Widgets emit play/pause/zones/... ---> MainWindow ---> server methods
                                          |
                                          +--MQTT (audio/commands/rpi_*)--> RPi audio players (optional)
```

- **Position:** `MainWindow` timer reads `server.user_position`, converts to meters, emits `AppBus.pointerUpdated(..., source="server")`.
- **Commands:** widgets use `AppBus` signals; `MainWindow` routes to `ServerBringUpProMax` (playback, adaptive audio, zone DJ, volumes).
- **Full signal list:** [`packages/appbus.py`](../../packages/appbus.py).

UWB measurement topics and processing stages match the main repository README (sliding windows, edges, PGO).

---

## How audio works in the Unified Demo

The GUI does **not** run a separate audio service. It constructs **one** [`ServerBringUpProMax`](server_bring_up_with_audio.py) instance with the MQTT settings from **Settings / QSettings** (`mqtt/*`), in the same process as the Qt event loop.

**Position → UI (downstream)**  
A short timer in `MainWindow` reads `server.user_position` (updated by the PGO pipeline from UWB measurements). Positions are converted to meters and emitted on **`AppBus.pointerUpdated`**. The **PGO Data**, **Adaptive Audio**, and **Zone DJ** tabs subscribe to that bus so the dot, zones, and floorplan stay aligned with the solve.

**UI → server → MQTT → RPis (upstream)**  
Tab widgets emit **`AppBus`** signals (play/pause, enable adaptive audio, enable zone DJ, volumes, zone geometry, etc.). **`MainWindow`** connects those signals to `ServerBringUpProMax` methods (`enable_adaptive_audio`, `enable_zone_dj`, demo entry points, and related helpers — see `main_demo.py` around the “AppBus Signal Connections” section).

**Inside `ServerBringUpProMax`**  
- **`AdaptiveAudioServer`** ([`packages/audio_mqtt_server/follow_me_audio_server.py`](../../packages/audio_mqtt_server/follow_me_audio_server.py)) computes `start` / `pause` / `volume` commands from the **current** `user_position` (adaptive follow-me) or from time/zone logic (zone DJ). It does not publish MQTT itself.  
- Background threads (`_adaptive_audio_loop`, zone DJ loop) poll state and call **`_publish_commands`**, which publishes JSON to per-speaker topics **`audio/commands/rpi_0` … `rpi_3`** (and broadcast when applicable). Payloads include `execute_time` so RPis can schedule synchronized playback.  
- Full topic and JSON shape: [`packages/audio_mqtt_server/README.md`](../../packages/audio_mqtt_server/README.md).

**Tab roles**  
- **Adaptive Audio:** floorplan + front/back speaker logic driven by position (Y split, X panning); starting adaptive mode turns on the server loop that maps position to volumes and MQTT commands.  
- **Zone DJ:** user-drawn zones and queues; server runs the zone-DJ loop and publishes commands so multiple speakers can follow zone rules.  
- **PGO Data:** visualization only; no extra audio path.

**Developers copying this pattern**  
- Import path: `main_demo.py` adds `packages/`, this directory, and repo root to `sys.path`, then `from server_bring_up_with_audio import ServerBringUpProMax`, plus `AppBus` and `services["server"]` for widgets—mirror that layout or adapt to your packaging.  
- Position path: poll `server.user_position` on a timer → meters → `AppBus.pointerUpdated` (see `main_demo.py`).  
- Command path: widgets emit `AppBus` signals → `MainWindow` slots → `ServerBringUpProMax` methods (playback, adaptive, zone DJ).

---

## Using the UI

**Toolbar**

- **Open Image…** — floorplan for the active tab  
- **Mark Corners** / **Auto Transform** — world (meters) ↔ image (pixels) homography  
- **Place Zones** — Zone DJ only (disabled on Adaptive Audio)  
- **Clear Zones** / **Clear Mapping**  
- **Load Default Floorplan** — uses `floorplan/default_path` or asset folder  
- **Settings** — zone radius + default floorplan path  

**Tabs**

- **PGO Data:** path plot; grid matches `world/*` and `grid/*` settings.  
- **Adaptive Audio:** rectangular zones A/B; speaker icons when the server exposes positions/volumes.  
- **Zone DJ:** circular zones, registration timers, per-zone demo queues.  

**Status bar:** server line plus pixel/meter readouts when homography is set.

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Server error on startup | Broker up; `mqtt/*` matches broker; `server_bring_up_with_audio` imports cleanly; console `[UnifiedDemo]` lines |
| Pointer frozen | Anchors publishing; PGO producing `user_position`; same broker as `mqtt/broker` |
| No floorplan grid | Mark corners or Auto Transform |
| Place Zones disabled | Switch to **Zone DJ** tab |
| No speaker icons | **Adaptive Audio** tab active; server implements speaker queries used by the widget |
| No sound from speakers | Each RPi runs `synchronized_audio_player_rpi.py` with `--id` matching anchor; broker IP/credentials match demo; WAV exists under `Demos/Audio_Library/`; adaptive or zone DJ mode enabled and phone/anchors producing position |

---

## License

MIT (see package READMEs where applicable).
