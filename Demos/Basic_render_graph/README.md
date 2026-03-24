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

## Usage

1. Start the MQTT broker:
```bash
mosquitto -c /path/to/mosquitto.conf
```

2. Start the UWB anchors (see Anchor_bring_up.md)

3. Run the visualizer:
```bash
python basic_visualizer.py
```

## Configuration

You can adjust these parameters in `basic_visualizer.py`:

```python
# Room dimensions
ROOM_WIDTH_CM = 480   # Width in cm
ROOM_HEIGHT_CM = 600  # Height in cm
GRID_SIZE_CM = 110    # Grid square size in cm

# Visualization settings
history_length = 100  # Number of past positions to show
window_size_seconds = 1.0  # Data window size
```

## Controls

- Close the window to exit
- The visualization will automatically update as new positions are calculated
- Position history shows the last 100 points by default

## Requirements

- Python 3.7+
- matplotlib
- numpy
- paho-mqtt

## Notes

- The visualization inherits from `ServerBringUp` to maintain consistency
- All UWB and PGO processing happens in the base class
- This visualization focuses purely on clean, clear display of the results
