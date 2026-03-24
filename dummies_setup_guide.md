# UWB Localization Setup Guide for Dummies

This guide will get your UWB localization system running from scratch. Copy and paste the commands in order.

**Note:** This project works well with **[uv](https://github.com/astral-sh/uv)** for dependencies. Commands below use `uv run` so the project environment is used; you can use plain `python` instead if you have installed the repo with `pip install -e .`.

---

## How this repo fits together (read once)

The **main codebase** is **UWB indoor localization**: anchors → MQTT → binning → edges → **PGO** → **`user_position`**.

**Audio, PyQt demos, and floorplan/zone UX** are **separate layers on top** of that base. They use MQTT and position where needed but are **not required** to run localization. They live in their own packages and scripts (`packages/audio_mqtt_*`, `Demos/UnifiedDemo/server_bring_up_with_audio.py`, `Demos/*`) so you can ignore them until you want them.

| Piece | Role |
|-------|------|
| **`Server_bring_up.py`** | Localization **only** (no audio command publishing). |
| **`Demos/UnifiedDemo/server_bring_up_with_audio.py`** (`ServerBringUpProMax`) | Same localization core **plus** audio MQTT orchestration (headless or embedded by the demo). |
| **`Demos/UnifiedDemo/main_demo.py`** | **Example / reference app:** PyQt UI with **embedded** `ServerBringUpProMax` (how a developer might import the base server and build a front-end). **Do not** also run `Server_bring_up.py` or a **second** `server_bring_up_with_audio` / demo server in another terminal. |

**Audio — what actually happens:** Sound does **not** come out of the Pis “for free.” `Anchor_bring_up.py` is **UWB only** (no speaker code). The laptop side (`ServerBringUpProMax` / Unified Demo) **publishes** MQTT messages on topics like `audio/commands/rpi_{id}`, but **nothing plays** unless each corner Pi also runs **`packages/audio_mqtt_client/synchronized_audio_player_rpi.py`** in a **second** terminal (or service), with `--id` matching that Pi’s anchor id. This repo has **no** single “unified” script that starts UWB + audio together on the Pi—you run **two processes** per speaker Pi. See **[`packages/audio_mqtt_client/README.md`](packages/audio_mqtt_client/README.md)** and **[`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)** (deploy §3).

More detail: **[`README.md`](README.md)** and **[`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)**.

---

## What you need

**Hardware:**

- 1 Laptop (Mac/Linux/Windows) — runs the MQTT broker and (depending on path) the localization server or Unified Demo
- 4 Raspberry Pis — each with a UWB anchor module connected via USB
- 1 Phone to track (iOS with UWB support, or your supported handset)

**Network:**

- All devices on the same Wi‑Fi (or LAN)
- Laptop must be reachable from every Raspberry Pi on **port 1884** (MQTT)

---

## Step 1: Install dependencies on the laptop

### First, install uv (Python package manager)

#### macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart your shell or run: source ~/.zshrc (or ~/.bashrc)
```

#### Linux/Ubuntu:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart your shell or run: source ~/.bashrc
```

#### Windows:

```powershell
# PowerShell
irm https://astral.sh/uv/install.ps1 | iex
```

Add `uv` to your PATH if the installer prints a path (check “uv was installed to …”).

### Then install Mosquitto and project dependencies

#### macOS:

```bash
brew install mosquitto

cd /path/to/uwb-localization-mesh
uv sync
```

#### Linux/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients

cd /path/to/uwb-localization-mesh
uv sync
```

#### Windows:

- Install Mosquitto from [https://mosquitto.org/download/](https://mosquitto.org/download/)
- Ensure `mosquitto` and `uv` are on your `PATH`
- In a terminal:

```bash
cd C:\path\to\uwb-localization-mesh
uv sync
```

---

## Step 2: Install dependencies on each Raspberry Pi

Run these on **each** of your **4** Raspberry Pis (clone or copy the repo onto each Pi first):

```bash
sudo apt-get update

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart shell or: source ~/.bashrc

# Serial + time sync (do time sync before serious logging)
sudo apt-get install -y python3-serial chrony
sudo chronyd -q 'server pool.ntp.org iburst'

cd /path/to/uwb-localization-mesh
uv sync
```

After `uv sync`, use `uv run …` from this directory (same as on the laptop).

---

## Step 3: Start MQTT broker (laptop — terminal 1)

On the laptop, in the project directory:

```bash
cd /path/to/uwb-localization-mesh

# Recommended: explicit port 1884 (matches anchors + server defaults)
echo "listener 1884
allow_anonymous true" > mosquitto.conf
mosquitto -c mosquitto.conf
```

**You should see** something like: `mosquitto version 2.x.x` and that it is running. When clients connect, you may see connection logs in that terminal.

**Alternative (debug):** `mosquitto -v` — if your default config listens on **1883**, anchors will not connect until you align ports; prefer the `mosquitto.conf` snippet above.

---

## Step 4: Choose what you are building / debugging

Choose **either** Track A **or** Track B—not both at the same time.

- **Same for both tracks:** Mosquitto on the laptop (**Step 3**) and **all four** `Anchor_bring_up.py` processes on the Pis (**Steps 6–9**). You do **not** change anchor commands when switching tracks.
- **Different on the laptop:** Track A runs **`Server_bring_up.py`** in its own terminal. Track B runs **`Demos/UnifiedDemo/main_demo.py`** instead and **must not** also run `Server_bring_up.py`.

### Track A — Core localization (headless)

**Goal:** See the **localization pipeline** end-to-end: MQTT ingest → binning → edges → PGO → `user_position`, without any PyQt demo.

- You run **`Server_bring_up.py`** (localization only, no audio orchestration).
- You confirm behavior via **server logs**, **`inspect_raw_data.py`**, and/or raw MQTT.
- **Do not** start `Demos/UnifiedDemo/main_demo.py` on the same laptop at the same time.

**Order after Step 3:** **Step 5** → **Steps 6–9** → **Step 10** → **Step 11 (Track A only)** → Step 12.

---

### Track B — Unified Demo (reference PyQt app)

**Goal:** Run the **reference application** that **embeds** `ServerBringUpProMax` (from `Demos/UnifiedDemo/server_bring_up_with_audio.py`) and shows how a UI can sit on top of the stack (PGO tab, floorplan, optional audio tabs).

- **Audio from speakers:** anchors alone are **not** enough. For playback on each corner Pi you still need a **second** process, **`synchronized_audio_player_rpi.py`** (see Quick reference → optional speakers, and **[`packages/audio_mqtt_client/README.md`](packages/audio_mqtt_client/README.md)**). Without it, Adaptive Audio / Zone DJ can run on the laptop but **nothing plays** on the RPis.
- You **skip** `Server_bring_up.py` entirely — the demo starts the server **inside** the GUI process.
- **Do not** run `Server_bring_up.py` or `python Demos/UnifiedDemo/server_bring_up_with_audio.py` in a separate terminal while the demo runs.
- If Mosquitto is **not** on `localhost` from the laptop’s point of view, set **`mqtt/broker`** (and related keys) via QSettings — **[`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)**.

**Order after Step 3:** **skip Step 5** → **Steps 6–9** → **Step 10** → **Step 11 (Track B only)** → Step 12.

---

### At a glance

| | **Track A — Core** | **Track B — Unified Demo** |
|---|-------------------|---------------------------|
| **Laptop server** | `Server_bring_up.py` | *(none separate; inside `main_demo.py`)* |
| **Best for** | Debugging PGO, MQTT, binning; minimal surface | Learning integration pattern; floorplan / audio UI |
| **Main script** | `Server_bring_up.py` | `Demos/UnifiedDemo/main_demo.py` |

---

## Step 5: Start the headless localization server (Track A only)

**If you chose Track B, skip this step completely.**

Open a **new** terminal on the laptop:

```bash
cd /path/to/uwb-localization-mesh
uv run python Server_bring_up.py --broker localhost
```

**You should see** JSON logs similar to:

```json
{"timestamp": "2025-10-08 10:30:00", "level": "INFO", "message": {"event": "server_config", "broker": "localhost", "port": 1884}}
```

As measurements arrive and PGO runs, watch for **position / state** lines in the same terminal (wording may vary slightly by version), e.g. updates reflecting the solved phone position.

---

## Steps 6–9: Start all four anchors (both tracks)

The next four steps are **the same** whether you chose **Track A** or **Track B**. Each command runs on **one** Raspberry Pi; use your laptop’s LAN IP as `YOUR_LAPTOP_IP` (the host running Mosquitto on port **1884**).

---

## Step 6: Start anchor 0 (RPi 0 terminal)

On your **first** Raspberry Pi:

```bash
cd /path/to/uwb-localization-mesh
# Replace YOUR_LAPTOP_IP with your laptop's LAN IP (the machine running Mosquitto)
uv run python Anchor_bring_up.py --anchor-id 0 --broker YOUR_LAPTOP_IP
```

Example:

```bash
uv run python Anchor_bring_up.py --anchor-id 0 --broker 192.168.68.63
```

**You should see** something like:

```
╔══════════════════════════════════════════════════════════════╗
║                     Anchor 0                                 ║
║               Top-right anchor                               ║
╚══════════════════════════════════════════════════════════════╝

Configuration:
  Anchor ID:     0
  MQTT Broker:   192.168.68.66:1884
  Serial Port:   /dev/ttyUSB0
  Baud Rate:     3000000
  Client ID:     uwb_anchor_0

Starting UWB measurement publishing...
✓ Connected to MQTT broker
✓ UWB hardware interface started
✓ Publishing measurements to MQTT
```

(Exact banner text may differ slightly; the important part is **connected** and **publishing**.)

---

## Step 7: Start anchor 1 (RPi 1 terminal)

On your **second** Raspberry Pi:

```bash
cd /path/to/uwb-localization-mesh
uv run python Anchor_bring_up.py --anchor-id 1 --broker YOUR_LAPTOP_IP
```

Example:

```bash
uv run python Anchor_bring_up.py --anchor-id 1 --broker 192.168.68.66
```

**You should see** the same style of banner for anchor **1** and MQTT connected / publishing.

---

## Step 8: Start anchor 2 (RPi 2 terminal)

On your **third** Raspberry Pi:

```bash
cd /path/to/uwb-localization-mesh
uv run python Anchor_bring_up.py --anchor-id 2 --broker YOUR_LAPTOP_IP
```

Example:

```bash
uv run python Anchor_bring_up.py --anchor-id 2 --broker 192.168.68.66
```

---

## Step 9: Start anchor 3 (RPi 3 terminal)

On your **fourth** Raspberry Pi:

```bash
cd /path/to/uwb-localization-mesh
uv run python Anchor_bring_up.py --anchor-id 3 --broker YOUR_LAPTOP_IP
```

Example:

```bash
uv run python Anchor_bring_up.py --anchor-id 3 --broker 192.168.68.66
```

---

## Step 10: Verify measurements (both tracks)

Use these checks for **either** track. They prove anchors → MQTT → broker; they do not replace your track-specific finish in **Step 11**.

### Check processed data (recommended debug tool)

```bash
cd /path/to/uwb-localization-mesh
uv run python Data_collection/inspect_raw_data.py
```

**You get:**

- Raw-style readings and **local** vectors  
- **Global** coordinate picture (anchor frames → room frame)  
- **Phone position** estimates per anchor view where applicable  
- **Sanity checks** (e.g. inside room bounds)  
- **Summary** when you stop with Ctrl+C  

**Example-style output** (numbers will differ):

```
======================================================================
Anchor 0 @ [0, 550, 0]
======================================================================
Local  [X, Y, Z]: [  123.45,   234.56,    78.90] cm
Global [X, Y, Z]: [  123.45,   234.56,    78.90] cm

Phone position (anchor + global vector):
  X = 0.00 + 123.45 = 123.45
  Y = 550.00 + 234.56 = 784.56
  Z = 0.00 + 78.90 = 78.90
✅ REASONABLE - within room bounds

Total messages: 42
```

### Alternative: raw MQTT

From a machine that can reach the broker (use laptop IP if not local):

```bash
mosquitto_sub -h localhost -p 1884 -t "uwb/#"
```

---

## Step 11: Finish the track you chose

Do **only** the subsection for your track.

### Track A — Core localization: confirm the solver in the server terminal

**Only if you started `Server_bring_up.py` in Step 5.**

In that **same laptop terminal**, keep it open and watch for ongoing activity as measurement bins fill and PGO runs. You want evidence of **position / state** updates (exact log wording can vary by version). If this terminal is quiet while `inspect_raw_data.py` (Step 10) shows traffic, check broker IP/port and that all four anchors are publishing.

---

### Track B — Unified Demo: launch the reference GUI

**Only if you skipped Step 5** (you are **not** running `Server_bring_up.py`).

On the **laptop**:

```bash
cd /path/to/uwb-localization-mesh
uv run python Demos/UnifiedDemo/main_demo.py
```

**You should see** a PyQt window. Open the **PGO Data** tab: the trace should move when the phone is in UWB range and sessions are active.

**If the app reports a server error:** Mosquitto is up; anchors point at the same broker; you are **not** also running `Server_bring_up.py` or a second copy of `server_bring_up_with_audio` in another terminal; if the broker is not `localhost`, set **`mqtt/*`** in QSettings per **[`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)**.

The Unified Demo is a **reference application** (how to embed `ServerBringUpProMax`, `AppBus`, and widgets—not the core library by itself). Deeper wiring: **[`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)**.

---

## Step 12: Next steps (phone, audio, docs)

1. **Phone:** Enable UWB / ranging in your test app; walk the room — **Track A:** watch the Step 5 terminal; **Track B:** watch the **PGO Data** tab.  
2. **Audio (optional, separate stack):** Adaptive / zone behavior in the **Unified Demo** (Track B) or via `packages/audio_mqtt_client` + laptop `Demos/UnifiedDemo/server_bring_up_with_audio.py`. UWB anchor processes and **audio player** processes on a Pi are **different** — **[`README.md`](README.md)** (*Client (RPi) — Audio*) and **[`packages/audio_mqtt_client/README.md`](packages/audio_mqtt_client/README.md)**.  
3. **Core vs demo:** UWB localization = packages + bring-ups in **[`README.md`](README.md)**; building your own UI = use Unified Demo as a **pattern** ([`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)).

---

## Troubleshooting

### "Connection refused" on Raspberry Pi

- Laptop IP is correct (`ipconfig` / `ip a` on laptop).  
- Mosquitto is running: `ps aux | grep mosquitto` (Linux/macOS).  
- Ping: `ping YOUR_LAPTOP_IP` from the Pi.

### "Failed to start UWB hardware interface"

- USB connected: `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`  
- User in dialout: `sudo usermod -a -G dialout $USER` then **reboot**  
- Wrong port, e.g. `SERIAL_PORT=/dev/ttyACM0 uv run python Anchor_bring_up.py --anchor-id 0 --broker YOUR_LAPTOP_IP`

### No position updates on server / flat PGO tab

- All **four** anchors running and connected.  
- MQTT traffic: `mosquitto_sub -h YOUR_LAPTOP_IP -p 1884 -t "uwb/#"`.  
- Phone in range and UWB session active.

### Raspberry Pi can't connect to MQTT

- Firewall: e.g. `sudo ufw allow 1884` on Ubuntu.  
- Same subnet / routing between Pi and laptop.

### USB re-enumerated (different tty after replug)

- `ls /dev/ttyUSB*` and set `SERIAL_PORT`, e.g.  
  `SERIAL_PORT=/dev/ttyUSB1 uv run python Anchor_bring_up.py --anchor-id 0 --broker 172.20.10.3`

### Unified Demo says server failed

- Broker running first.  
- Not running **two** laptop servers (no `Server_bring_up.py` + Unified Demo together).  
- If broker ≠ localhost, set `mqtt/broker` (and credentials) per **[`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)**.

---

## Quick reference — copy-paste (pick one track)

**Order matters:**

- **Track A:** MQTT → **`Server_bring_up.py`** on laptop → **four anchors** on Pis → verify (Step 10) → watch server logs (Step 11 A).  
- **Track B:** MQTT → **four anchors** on Pis → **`main_demo.py`** on laptop → verify (Step 10) as needed → GUI (Step 11 B).

Replace `YOUR_LAPTOP_IP` with the laptop’s IP on the network the Pis use.

---

### Shared — laptop terminal 1 (MQTT)

```bash
cd uwb-localization-mesh
echo "listener 1884
allow_anonymous true" > mosquitto.conf
mosquitto -c mosquitto.conf
```

### Shared — each Raspberry Pi (anchors 0–3)

```bash
cd uwb-localization-mesh
uv run python Anchor_bring_up.py --anchor-id 0 --broker YOUR_LAPTOP_IP
```

Repeat on the other three Pis with `--anchor-id` **1**, **2**, **3**.

---

### Track A — laptop terminal 2 (core localization only)

Matches **Step 5** in the main guide: start **right after** MQTT, **before** you bring up the four anchors (so the server is already subscribed when measurements start).

```bash
cd uwb-localization-mesh
uv run python Server_bring_up.py --broker localhost
```

Then start anchors (Steps 6–9), run **Step 10**, then **Step 11 → Track A**.

---

### Track B — laptop (Unified Demo, no `Server_bring_up.py`)

Matches **Step 11 → Track B**: start **after** MQTT **and** **after** all four anchors are publishing:

```bash
cd uwb-localization-mesh
uv run python Demos/UnifiedDemo/main_demo.py
```

---

### Optional — each Pi, second terminal (speakers only; either track)

`--id` must match that Pi’s anchor id. WAV under `Demos/Audio_Library/` unless you pass a full `Demos/Audio_Library/...` path.

```bash
cd uwb-localization-mesh
uv run python packages/audio_mqtt_client/synchronized_audio_player_rpi.py --id 0 --wav "your-track.wav" --broker YOUR_LAPTOP_IP
```

Repeat with `--id` 1, 2, 3 on the other Pis. Details: **[`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)** (anchors — audio players) and **How audio works in the Unified Demo**.
