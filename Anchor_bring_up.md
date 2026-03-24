# UWB Anchor Bring-Up Guide

This guide explains how to set up and run the UWB anchor system on 4 Raspberry Pis for real-time localization.

## Overview

The UWB localization system consists of:
- **4 Raspberry Pis** (one per anchor)
- **4 UWB anchors** (numbered 0-3)
- **1 phone** being tracked
- **1 MQTT broker** for communication
- **1 server** running the localization algorithm

Each Raspberry Pi runs the same `Anchor_bring_up.py` script, which automatically detects which anchor it is and publishes UWB measurements to MQTT.

**Optional — corner speakers:** this script is **UWB only**. For adaptive / zone audio, run a **second** process on each Pi: `packages/audio_mqtt_client/synchronized_audio_player_rpi.py` (see **[`README.md`](README.md)** and **[`Demos/UnifiedDemo/README.md`](Demos/UnifiedDemo/README.md)**).


## Prerequisites

### 1. Hardware Setup
- 4 Raspberry Pis (one per anchor)
- 4 UWB anchor modules connected via USB serial
- Network connectivity to MQTT broker

- Time syncing to external server
```bash 
sudo apt-get install -y chrony
sudo chronyd -q 'server pool.ntp.org iburst'
```
- time syncing on mac
```bash
sudo sntp -sS pool.ntp.org
```

### 2. Software Dependencies
```bash
# On each Raspberry Pi
pip install paho-mqtt numpy
sudo apt-get install -y python3-serial
```

### 3. MQTT Broker Setup

#### On the Server (Laptop):
1. Install Mosquitto:
```bash
# macOS
brew install mosquitto

# Linux
sudo apt-get install mosquitto mosquitto-clients
```

2. Create a custom mosquitto.conf:
```bash
# Create mosquitto.conf in your project directory
echo "listener 1884
allow_anonymous true" > mosquitto.conf

# Start Mosquitto with this config
mosquitto -c mosquitto.conf
```

3. Verify MQTT broker is running:
```bash
# Subscribe on the same port as anchors (1884)
mosquitto_sub -h localhost -p 1884 -t "uwb/#"
```

## Quick Start

### Step 1: Configure Each RPi

1. First, ensure your laptop's IP address is accessible from all RPis:
```bash
# On each RPi, test connection to laptop
ping <laptop-ip>  # Example: ping 192.168.68.66
```

2. Configure each RPi:

**On RPi 0 (Anchor 0):**
```bash
# Either use command line argument
python Anchor_bring_up.py --anchor-id 0 --broker <laptop-ip>

# Or use environment variables
export ANCHOR_ID=0
export MQTT_BROKER="<laptop-ip>"  # Example: 192.168.68.66
python Anchor_bring_up.py
```

**On RPi 1 (Anchor 1):**
```bash
python Anchor_bring_up.py --anchor-id 1 --broker <laptop-ip>
```

**On RPi 2 (Anchor 2):**
```bash
python Anchor_bring_up.py --anchor-id 2 --broker <laptop-ip>
```

**On RPi 3 (Anchor 3):**
```bash
python Anchor_bring_up.py --anchor-id 3 --broker <laptop-ip>
```

### Step 2: Run on Each RPi

```bash
python Anchor_bring_up.py
```

You should see output like:
```
╔══════════════════════════════════════════════════════════════╗
║                     Anchor 0                               ║
║               Top-right anchor                             ║
╚══════════════════════════════════════════════════════════════╝

Configuration:
  Anchor ID:     0
  MQTT Broker:   192.168.1.100:1884
  Serial Port:   /dev/ttyUSB0
  Baud Rate:     3000000
  Client ID:     uwb_anchor_rpi0

Starting UWB measurement publishing...
✓ Connected to MQTT broker
✓ UWB hardware interface started
✓ Publishing measurements to MQTT
```

## Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ANCHOR_ID` | Anchor ID (0-3) | Auto-detected | Yes |
| `MQTT_BROKER` | MQTT broker IP | localhost | No |
| `SERIAL_PORT` | UWB serial device | /dev/ttyUSB0 | No |

### Command Line Arguments

```bash
python Anchor_bring_up.py [options]

Options:
  --anchor-id {0,1,2,3}    Anchor ID (overrides ANCHOR_ID env var)
  --broker BROKER_IP       MQTT broker IP (overrides MQTT_BROKER env var)
  --serial-port PORT       Serial device path (overrides SERIAL_PORT env var)
  --dry-run                Show configuration without starting
  --help                   Show help message
```

## Auto-Detection Features

The script automatically detects the anchor ID using the following priority order:

1. **Command line argument** `--anchor-id` (highest priority)
2. **Environment variable** `ANCHOR_ID`
3. **Hostname detection** (looks for "anchor0", "anchor1", "anchor2", "anchor3" or "rpi0", "rpi1", "rpi2", "rpi3" in hostname)

### Recommended: Hostname-Based Setup

Set hostnames on each RPi for automatic detection:

```bash
# On RPi 0
sudo hostnamectl set-hostname anchor0

# On RPi 1
sudo hostnamectl set-hostname anchor1

# On RPi 2
sudo hostnamectl set-hostname anchor2

# On RPi 3
sudo hostnamectl set-hostname anchor3
```

Then you only need to set `MQTT_BROKER` and the script will auto-detect the anchor ID.

## Troubleshooting

### Common Issues

**1. "Connection refused" to MQTT broker**
- Ensure Mosquitto is running on laptop with correct config
- Verify laptop's IP is accessible from RPi (`ping <laptop-ip>`)
- Check no firewall is blocking port 1884
- Verify mosquitto.conf has `listener 1884` and `allow_anonymous true`

**2. "Clock synchronization issues"**
- Ensure all devices are time-synced (see Prerequisites section)

**3. "Could not determine anchor ID"**
- Explicitly provide anchor ID via --anchor-id argument
- Or set ANCHOR_ID environment variable
- Or use hostname-based detection (see Hostname Setup section)

**4. "Failed to start UWB hardware interface"**
- Check USB serial device is connected: `ls /dev/ttyUSB*`
- Verify serial port in `SERIAL_PORT`
- Check device permissions: `sudo usermod -a -G dialout $USER`

**5. "MQTT disconnects frequently"**
- Check network stability between RPi and laptop
- Ensure laptop's IP hasn't changed
- Verify Mosquitto is still running on laptop

### Testing

**Dry Run (check configuration):**
```bash
export ANCHOR_ID=0
python Anchor_bring_up.py --dry-run
```

**Test MQTT Connection:**
```bash
mosquitto_sub -h <broker-ip> -p 1884 -t "uwb/#"
```

**Monitor one anchor’s vectors:**
```bash
mosquitto_sub -h <broker-ip> -p 1884 -t "uwb/anchor/0/vector"
```

## Anchor Positions

The system assumes standard anchor positions (can be modified in localization server):

- **Anchor 0**: Top-right (480, 600, 0) cm
- **Anchor 1**: Top-left (0, 600, 0) cm
- **Anchor 2**: Bottom-right (480, 0, 0) cm
- **Anchor 3**: Bottom-left (origin) (0, 0, 0) cm

## Next Steps

After anchors are running and publishing measurements:

1. **Start the laptop side:** **`Server_bring_up.py`** (localization only), **`Demos/UnifiedDemo/main_demo.py`** (GUI + embedded `ServerBringUpProMax`), or headless **`python Demos/UnifiedDemo/server_bring_up_with_audio.py`** (localization + audio MQTT) — **only one** of these at a time. See **[`dummies_setup_guide.md`](dummies_setup_guide.md)**.
2. **Verify measurements** are being received (`mosquitto_sub -h <broker> -p 1884 -t "uwb/#"`).
3. **Tune anchor positions** if needed (server / PGO config).
4. **Test phone tracking** with the localization pipeline.
5. **Optional audio:** second terminal per Pi — `synchronized_audio_player_rpi.py` per **[`packages/audio_mqtt_client/README.md`](packages/audio_mqtt_client/README.md)**.

## Files Overview

- `Anchor_bring_up.py` - Main script (this file)
- `Anchor_bring_up.md` - This documentation
- `packages/uwb_mqtt_client/` - MQTT client package
- `Server_bring_up.py` - Localization-only laptop server
- `Demos/UnifiedDemo/server_bring_up_with_audio.py` - Laptop server with audio MQTT (`ServerBringUpProMax`; also embedded by Unified Demo)

The UWB anchor system is now ready to provide real-time positioning data! 📍
