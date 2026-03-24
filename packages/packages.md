# 📦 UWB Localization Packages

Core packages for UWB-based indoor localization using pose graph optimization.

## Package Overview

### datatypes
Core data structures used across the system:
- `Measurement`: Raw UWB measurements with timestamps
- `BinnedData`: Time-windowed measurement aggregation
- `AnchorConfig`: Ground truth and jittered anchor positions

### localization_algos
Core localization algorithms split into three main components:

#### edge_creation/
- Transform local measurements to global frame
- Create anchor-anchor edges from ground truth
- Support for jittered anchor positions

#### binning/
- Sliding window implementation (1s default)
- Late data handling with metrics
- Thread-safe per-phone binning

#### pgo/
- Pose Graph Optimization solver
- Proper anchoring to global frame
- Support for jittered edges

### uwb_mqtt_client (RPi)
Client-side MQTT handling:
- Measurement publishing
- Reconnection with backoff
- Keep-alive handling

### uwb_mqtt_server (Laptop)
Server-side MQTT handling:
- Subscribe to all RPi measurements
- Pure message handling
- Thread-safe callbacks

## Usage Example

```python
# Server side
from uwb_mqtt_server import UWBMQTTServer, MQTTConfig
from localization_algos.binning import SlidingWindowBinner
from localization_algos.pgo import PGOSolver

# Configure MQTT
mqtt_config = MQTTConfig(broker="localhost", port=1884)

# Create server components
server = UWBMQTTServer(config=mqtt_config)
binner = SlidingWindowBinner(window_size_seconds=1.0)
solver = PGOSolver()

# Start processing
server.start()

# Client side
from uwb_mqtt_client import UWBMqttClient, MQTTConfig

# Configure client
mqtt_config = MQTTConfig(broker="server_ip", port=1884)
client = UWBMqttClient(config=mqtt_config, phone_node_id=0)

# Connect and publish
client.connect()
client.publish_measurement(anchor_id=0, local_vector=[x, y, z])
```

## Key Features
- No side effects on import
- Thread-safe data handling
- Pure functions where possible
- Proper error handling
- Comprehensive metrics
- Support for jittered testing

## Dependencies
- numpy
- paho-mqtt
- scipy (for PGO)

## Development
- All packages have unit tests
- Use type hints throughout
- Follow PEP 8 style guide
- Keep functions pure where possible

## Reference application (Unified Demo)

**Localization libraries above are the core.** The [**Unified Demo**](../Demos/UnifiedDemo/README.md) is a **developer reference**: it composes `pgo_data_widget`, `adaptive_audio_widget`, `zone_dj_widget`, `viz_floorplan`, etc., and **imports** `ServerBringUpProMax` in-process to show how an application can sit on top of the UWB stack. Use it as a pattern for your own integration, not as the only way to ship the system.