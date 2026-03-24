# Unified Demo

Primary PyQt5 visualization and audio UI for this repo. It supersedes the removed `Demos/PyQT_Visualisation/` demo and the deprecated `Demos/Basic_render_graph/` matplotlib viewer.

PyQt5 desktop app that runs the **full laptop server** and three tabs in one process:

| Tab | Package | Purpose |
|-----|---------|---------|
| **PGO Data** | `pgo_data_widget` | Live 2D path from estimated phone position |
| **Adaptive Audio** | `adaptive_audio_widget` | Floorplan, fixed two zones (split at 3.0 m), speaker levels |
| **Zone DJ** | `zone_dj_widget` | Floorplan, user-drawn circular zones, per-zone queues |

**Backend:** `ServerBringUpProMax` from [`Server_bring_up_with_Audio.py`](../../Server_bring_up_with_Audio.py) (MQTT ingest, binning, PGO, audio routing). There is no separate “simulation” server and no fallback to other bring-up scripts.

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

### 2. Anchors (one terminal or service per RPi)

Point each anchor at the **broker hostname or IP** (the machine running Mosquitto, often the same laptop as the demo):

```bash
python Anchor_bring_up.py --anchor-id 0 --broker <BROKER_IP>
# repeat for anchors 1–3
```

Anchors use **port 1884** (see `Anchor_bring_up.py`). Ensure firewall rules allow MQTT from the Pi subnet.

### 3. Unified Demo (laptop)

From the **repository root**:

```bash
python Demos/UnifiedDemo/main_demo.py
```

This starts **one** `ServerBringUpProMax` inside the GUI. Do **not** run `python Server_bring_up_with_Audio.py` in parallel unless you intend to run a second server (not supported for this UI).

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
Widgets emit play/pause/zones/... ---> MainWindow ---> server methods / MQTT audio topics
```

- **Position:** `MainWindow` timer reads `server.user_position`, converts to meters, emits `AppBus.pointerUpdated(..., source="server")`.
- **Commands:** widgets use `AppBus` signals; `MainWindow` routes to `ServerBringUpProMax` (playback, adaptive audio, zone DJ, volumes).
- **Full signal list:** [`packages/appbus.py`](../../packages/appbus.py).

UWB measurement topics and processing stages match the main repository README (sliding windows, edges, PGO).

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
| Server error on startup | Broker up; `mqtt/*` matches broker; `Server_bring_up_with_Audio` imports cleanly; console `[UnifiedDemo]` lines |
| Pointer frozen | Anchors publishing; PGO producing `user_position`; same broker as `mqtt/broker` |
| No floorplan grid | Mark corners or Auto Transform |
| Place Zones disabled | Switch to **Zone DJ** tab |
| No speaker icons | **Adaptive Audio** tab active; server implements speaker queries used by the widget |

---

## License

MIT (see package READMEs where applicable).
