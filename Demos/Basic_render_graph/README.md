# Basic UWB Position Visualization

> **Deprecated:** This matplotlib-only viewer is superseded by **`Demos/UnifiedDemo/`** (`main_demo.py`), which includes live PGO plotting, floorplan, and audio tabs. This folder is retained only for minimal debugging or historical reference.

A clean, simple visualization for the UWB positioning system. This demo provides:
- Real-time grid display
- Smooth position updates
- Clear trajectory tracking
- Minimal, focused UI

## Features

- **Clean Grid Display**: Shows room layout with grid lines every 110cm
- **Anchor Visualization**: Clear markers for all 4 UWB anchors
- **Position Tracking**: Real-time position updates with trajectory history
- **Status Display**: Current position and tracking statistics
- **Smooth Animation**: 10 FPS update rate for fluid visualization

## Room Layout

The visualization uses the standard room configuration:

```
A1 (0,600,0) +-----------------+ A0 (480,600,0)
             |                 |
             |                 |
             |      Room      |
             |                 |
             |                 |
A3 (0,0,0)   +-----------------+ A2 (480,0,0)
```

## How to run

This script imports `Server_bring_up` from the **repository root** and `packages.*` for MQTT. Run it from the **root of `uwb-localization-mesh`**, not from inside `Demos/Basic_render_graph/`, unless you set `PYTHONPATH` to the repo root (see below).

### 1. Environment

Install project dependencies (see root `pyproject.toml`).

**Option A — `uv` (recommended):** from the repo root, sync and run with `uv run` so the project root is on the import path:

```bash
cd /path/to/uwb-localization-mesh
uv sync
```

**Option B — `venv` + `pip`:** install the package and its dependencies, then pass `PYTHONPATH=.` when launching the script so `Server_bring_up.py` at the repo root can be imported:

```bash
cd /path/to/uwb-localization-mesh
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

The built wheel only includes the `packages/` tree; `Server_bring_up` lives at the repo root, so use `PYTHONPATH=.` with the `python` command in step 3 if you are not using `uv run`.

### 2. Broker and anchors

1. Start your MQTT broker (same broker the anchors use), e.g.:

   ```bash
   mosquitto -c /path/to/mosquitto.conf
   ```

2. Start the UWB anchors and point them at that broker (see `Anchor_bring_up.md` at the repo root).

### 3. Start the visualizer

From the **repository root**:

```bash
uv run python Demos/Basic_render_graph/basic_visualizer.py
```

If you use a venv with `pip install -e .`, set the repo root on `PYTHONPATH`:

```bash
PYTHONPATH=. python Demos/Basic_render_graph/basic_visualizer.py
```

**CLI options** (defaults match `Server_bring_up.py`):

| Option | Default | Description |
|--------|---------|-------------|
| `--broker` | `localhost` | MQTT broker host |
| `--port` | `1884` | MQTT broker port |
| `--history` | `100` | Max trajectory points kept |

Example:

```bash
uv run python Demos/Basic_render_graph/basic_visualizer.py --broker 192.168.1.10 --port 1884 --history 50
```

### If imports still fail

From the repo root:

```bash
PYTHONPATH=. python Demos/Basic_render_graph/basic_visualizer.py
```

### Do not run two pipelines

`basic_visualizer.py` **already starts** the full MQTT + binning + PGO stack via `ServerBringUp`. Do not run `python Server_bring_up.py` in another terminal at the same time unless you intend to duplicate processing.

## Configuration

**Room and grid** — edit constants at the top of `basic_visualizer.py`:

```python
ROOM_WIDTH_CM = 480
ROOM_HEIGHT_CM = 600
GRID_SIZE_CM = 110
```

**Trajectory length** — use `--history` on the command line, or change the default in the `BasicVisualizer(..., history_length=...)` call in the `if __name__ == "__main__"` block.

**PGO sliding window** — `window_size_seconds` is passed into `BasicVisualizer` in that same block (default `1.0`); adjust there if needed.

## Controls

- Close the window to exit
- The visualization will automatically update as new positions are calculated
- Position history shows the last 100 points by default (override with `--history`)

## Requirements

- Python 3.8+ (see root `pyproject.toml` for `requires-python`)
- Dependencies: `matplotlib`, `numpy`, `paho-mqtt`, and the rest of the stack used by `Server_bring_up.py` (install via `uv sync` or `pip install -e .` from the repo root)

## Notes

- The visualization subclasses `ServerBringUp`; MQTT ingestion, binning, and PGO run **inside this process**.
- For the full PyQt demo (floorplan, PGO plot, audio), use `Demos/UnifiedDemo/main_demo.py`.
