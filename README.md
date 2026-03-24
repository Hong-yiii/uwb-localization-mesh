# 🚀 Project Hub — Overview & High‑Level Architecture

This repository contains **reusable packages** (e.g., `PGO`, `localization‑algos`, MQTT clients/servers, audio control) plus **bring‑up scripts** and **demos** that run across **RPi clients** and a **Laptop server**.

**Scope:** The **core** of this repository is **UWB indoor localization** (measurements → binning → edges → PGO → position). Everything else—**audio MQTT, PyQt UIs, floorplan/zone demos**—is built **on top of** that base: separate packages and bring-ups (`packages/audio_mqtt_*`, [`Demos/UnifiedDemo/server_bring_up_with_audio.py`](Demos/UnifiedDemo/server_bring_up_with_audio.py), `Demos/*`) so you can run **localization-only** with no demo or audio. Step-by-step hardware setup: **[`dummies_setup_guide.md`](dummies_setup_guide.md)**.

**Unified Demo** ([`Demos/UnifiedDemo/`](Demos/UnifiedDemo/README.md)) is a **reference application** for developers: it shows one way to **import the laptop bring-up** (`ServerBringUpProMax`), run it in-process, and attach a multi-tab PyQt front-end (`AppBus`, widgets under `packages/`). It is not the definition of the product—the **product** is the localization pipeline and reusable libraries.

- **Packages**: import‑safe libraries with no side effects on import (pure modules).
- **Bring‑ups**: scripts that instantiate device roles (RPi client / Laptop server) and wire MQTT + state.
- **Demos**: examples that compose packages and servers; the Unified Demo in particular illustrates **application-layer** integration on top of the UWB core.
- **Data_collection**: follows the same pattern as a demo for capturing data for evaluation.

---

## 🏗️ System Architecture & Data Flow

### Overview
This UWB localization system processes real-time measurements from 4 fixed anchors to estimate the 3D position of a mobile phone. The system uses MQTT for distributed communication, sliding window binning for temporal aggregation, and Pose Graph Optimization (PGO) for position estimation.

### Hardware Layer
- **4 UWB Anchors**: Raspberry Pi devices with UWB modules mounted at room corners
- **Mobile Phone**: Target device with UWB capability being localized
- **MQTT Broker**: Central message hub (Mosquitto) running on laptop/server

### Core Data Flow Pipeline

```mermaid
flowchart TD
    %% Hardware Input Layer
    subgraph "Hardware Layer"
        A0[UWB Anchor 0<br/>RPi + UWB Module]
        A1[UWB Anchor 1<br/>RPi + UWB Module]
        A2[UWB Anchor 2<br/>RPi + UWB Module]
        A3[UWB Anchor 3<br/>RPi + UWB Module]
        PHONE[UWB Phone<br/>Target Device]
    end

    %% Communication Layer
    subgraph "Communication Layer"
        MQTT[(MQTT Broker<br/>Mosquitto)]
    end

    %% Processing Layer - Server Bring-up
    subgraph "Processing Layer (Server_bring_up.py)"
        INGEST[MQTT Ingestion<br/>UWBMQTTServer]
        BIN[Sliding Window Binning<br/>1s windows per phone]
        EDGES[Edge Creation<br/>anchor↔anchor + anchor→phone]
        PGO[PGO Optimization<br/>Nonlinear least squares]
        STATE[Global State<br/>user_position, data dict]
    end

    %% Application Layer
    subgraph "Application Layer (examples on top of UWB core)"
        VIZ[Unified Demo — ref PyQt app<br/>embeds server + widgets]
        AUDIO_FOLLOW[Audio MQTT + widgets<br/>Follow / adaptive / zone DJ]
        AUDIO_ADAPTIVE[packages/audio_*<br/>Server & client]
        DATA_COLLECTION[Data_collection<br/>Logging & evaluation]
    end

    %% Data Flow
    A0 -->|uwb/anchor/0/vector| MQTT
    A1 -->|uwb/anchor/1/vector| MQTT
    A2 -->|uwb/anchor/2/vector| MQTT
    A3 -->|uwb/anchor/3/vector| MQTT

    MQTT -->|subscribe| INGEST
    INGEST -->|Measurement list| BIN
    BIN -->|BinnedData dict| EDGES
    EDGES -->|Edge list| PGO
    PGO -->|PGOResult| STATE

    STATE --> VIZ
    STATE --> AUDIO_FOLLOW
    STATE --> AUDIO_ADAPTIVE
    STATE --> DATA_COLLECTION

    %% Styling
    classDef hardware fill:#e1f5fe,stroke:#01579b
    classDef comm fill:#f3e5f5,stroke:#4a148c
    classDef processing fill:#e8f5e8,stroke:#1b5e20
    classDef app fill:#fff3e0,stroke:#e65100

    class A0,A1,A2,A3,PHONE hardware
    class MQTT comm
    class INGEST,BIN,EDGES,PGO,STATE processing
    class VIZ,AUDIO_FOLLOW,AUDIO_ADAPTIVE,DATA_COLLECTION app
```

### Detailed Data Flow Through Server_bring_up.py

#### 1. **Measurement Ingestion** (`UWBMQTTServer`)
```
MQTT Message → Measurement dataclass
├── timestamp: float (NTP epoch seconds)
├── anchor_id: int (0-3)
├── phone_node_id: int (currently always 0)
└── local_vector: np.ndarray [x,y,z] in cm (anchor's local frame)
```

**MQTT Topic Structure:**
- `uwb/anchor/{anchor_id}/vector` (wildcard subscription)
- Payload: `{"t_unix_ns": int, "vector_local": {"x": float, "y": float, "z": float}}`

#### 2. **Sliding Window Binning** (`SlidingWindowBinner`)
```
Measurement[] → BinnedData dataclass (1-second windows)
├── bin_start_time: float
├── bin_end_time: float
├── phone_node_id: int
└── measurements: Dict[int, List[np.ndarray]]
    └── anchor_id → [vector1, vector2, ...] (averaged later)
```

**Key Features:**
- Maintains sliding window of recent measurements
- Drops measurements older than window size
- Groups measurements by anchor within each window
- Tracks binning metrics (late drops, per-anchor counts)

#### 3. **Edge Creation** (transforms.py + anchor_edges.py)
```
BinnedData → Edge[] tuples: (from_node, to_node, relative_vector)
```

**Two types of edges:**
- **Anchor-Anchor Edges** (static, pre-computed):
  - Based on ground truth anchor positions
  - Creates constraints between all anchor pairs
  - Transforms to global coordinate frame

- **Anchor-Phone Edges** (dynamic, per-bin):
  - Average vectors within each 1s bin per anchor
  - Transform from anchor's local frame to global frame
  - Uses coordinate transformations accounting for anchor orientations

#### 4. **Pose Graph Optimization** (`PGOSolver`)
```
Edge[] + anchor_positions → PGOResult
├── node_positions: Dict[str, np.ndarray] (optimized positions)
├── success: bool
├── iterations: int
├── error: float (optimization residual)
```

**Optimization Process:**
- **Nodes:** `anchor_0`, `anchor_1`, `anchor_2`, `anchor_3`, `phone_0`
- **Anchored Optimization:** Anchors start at ground truth positions, phone starts floating
- **Nonlinear Least Squares:** Minimizes error between predicted vs measured relative vectors
- **Anchoring Transformation:** Aligns solution to ground truth anchor positions

#### 5. **State Management & Output**
```
PGOResult → Global State
├── user_position: np.ndarray [x,y,z] (latest phone position)
├── data: Dict[int, BinnedData] (per-phone binned data)
└── JSON logging of position updates and metrics
```

### Key System Characteristics

- **Real-time Processing:** Continuous 1-second sliding windows
- **Distributed Architecture:** MQTT enables loose coupling between anchors and server
- **Robust Optimization:** Handles noisy UWB measurements through statistical aggregation
- **Coordinate Systems:** Transforms from multiple local anchor frames to global room coordinates
- **Extensible:** Clean separation allows easy addition of new processing stages or outputs

### Configuration & Ground Truth
- **Room Dimensions:**480cm × 600cm
- **Anchor Heights:** All at 239cm (2.39m) from floor
- **Anchor Positions:**
  - Anchor 0: [480, 600, 239] (top-right)
  - Anchor 1: [0, 600, 239] (top-left)
  - Anchor 2: [480, 0, 239] (bottom-right)
  - Anchor 3: [0, 0, 239] (bottom-left, origin)

---


## 📦 Packages (what each does)

**`packages/uwb-mqtt-client`**  
Client‑side publish of UWB measurements from RPi. Handles reconnect, keep‑alive, and simple backoff.  
_Main entry points:_ `UwbMqttClient.connect()`, `publish_measurement(measurement)`.

**`packages/uwb-mqtt-server`**  
Server‑side subscribe/ingestion of measurements from all RPis. Emits per‑phone **binned** data and invokes localization callbacks.  
_Main entry points:_ `UwbMqttServer.start()`, callback `on_measurement(measurement)` → binning pipeline.

**`packages/localization-algos`**  
Transforms binned local vectors into **relative edges** (anchor→phone), applies optional filters/weights, and prepares inputs for PGO.  
_Main entry points:_ `make_edges(binned_data)`, `apply_azimuth_correction(vec, yaw_deg)`.

**`packages/PGO` (being refactored into a pure package)**  
Pose Graph Optimization over anchors + phone nodes; outputs consistent **global positions** for rendering and audio routing.  
_Main entry points:_ `PGOSolver.add_edges(edges)`, `solve() -> GraphSolution`.

**`packages/audio-mqtt-server` / `packages/audio-mqtt-client`**  
Laptop: `AdaptiveAudioServer` + `ServerBringUpProMax` publish JSON commands. RPi: `synchronized_audio_player_rpi.py` subscribes and plays.  
_Details:_ [`packages/audio_mqtt_server/README.md`](packages/audio_mqtt_server/README.md), [`packages/audio_mqtt_client/README.md`](packages/audio_mqtt_client/README.md).

---

## 🧯 Bring‑ups (device roles)

**Client (RPi) — UWB: `Anchor_bring_up.py`**  
Each anchor Raspberry Pi runs this script to read the UWB module (USB serial) and publish measurements to MQTT (`uwb/anchor/{id}/vector`, broker port **1884**). See `Anchor_bring_up.md` / repository anchor docs for `ANCHOR_ID`, `--broker`, and `SERIAL_PORT`.

**Client (RPi) — Audio (optional, separate process)**  
There is no single combined “UWB + audio” bring-up script. For corner speakers, run **a second process** on each Pi:

- `packages/audio_mqtt_client/synchronized_audio_player_rpi.py --id <0-3> --wav <file> --broker <BROKER_IP>`
- Subscribes to `audio/commands/rpi_{id}` and `audio/commands/broadcast`; uses the same broker port (**1884**) and default credentials (**`laptop` / `laptop`**) as [`server_bring_up_with_audio.py`](Demos/UnifiedDemo/server_bring_up_with_audio.py) / Unified Demo unless you change Mosquitto.
- WAV paths default under `Demos/Audio_Library/`; channel mapping (left/right per RPi) is documented in [`packages/audio_mqtt_client/README.md`](packages/audio_mqtt_client/README.md).

**Server (Laptop) — `Server_bring_up.py`**  
Localization only: MQTT ingest → binning → edges → PGO → `user_position`. No audio MQTT publishing.

**Server (Laptop) — [`Demos/UnifiedDemo/server_bring_up_with_audio.py`](Demos/UnifiedDemo/server_bring_up_with_audio.py) (`ServerBringUpProMax`)**  
Same pipeline as above, plus **`AdaptiveAudioServer`** and MQTT publishing of audio commands for the RPis. Run this module **standalone** (`python Demos/UnifiedDemo/server_bring_up_with_audio.py`) for a headless server, or **embed** it via [`Demos/UnifiedDemo/main_demo.py`](Demos/UnifiedDemo/main_demo.py) (reference PyQt app).

---

## ▶️ Demos

Index: **[`Demos/README.md`](Demos/README.md)**.

**`Demos/UnifiedDemo`** — **reference PyQt app**: embeds `ServerBringUpProMax` and wires `AppBus` + tab widgets to the localization + optional audio stack—useful as a **template** for your own UI. **Do not** start a second laptop server process while it runs. Deploy/run: **[`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)**.

**`Demos/Basic_render_graph`** — **deprecated** matplotlib view; superseded by Unified Demo. See that folder’s README.  
**`Data_collection`** — logging and evaluation.

**Run order — Unified Demo (typical):**

```bash
# 1) Broker (example: port 1884)
echo "listener 1884
allow_anonymous true" > mosquitto.conf
mosquitto -c mosquitto.conf

# 2) Anchors on RPis (broker = laptop IP or hostname reachable from Pis)
python Anchor_bring_up.py --anchor-id 0 --broker <BROKER_IP>
# … repeat for anchors 1–3

# 2b) Optional — audio on each RPi (second terminal per Pi; see Unified Demo README)
# python packages/audio_mqtt_client/synchronized_audio_player_rpi.py --id 0 --wav "<file>.wav" --broker <BROKER_IP>

# 3) GUI + embedded ServerBringUpProMax (same machine as broker is common)
python Demos/UnifiedDemo/main_demo.py
```

For **how the Unified Demo wires localization to audio** (tabs, MQTT topics, RPi clients), see **[`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)** — **section 3 (Anchors — audio players)** and **How audio works in the Unified Demo**.

**Run order — other demos** that expect a **standalone** server: broker → `Server_bring_up.py` (localization-only) or `python Demos/UnifiedDemo/server_bring_up_with_audio.py` (with audio MQTT) → anchors → demo script.

Always start the **broker** first, then any **standalone** server, then **anchors**.

If you use **`uv`**, use `uv run …` where appropriate.


## 📚 Reference Repositories
| **UWB Phone App** | iPhone app for UWB module control & tests | https://github.com/Hong-yiii/Bang_and_olufsen_UWB_Testing |

