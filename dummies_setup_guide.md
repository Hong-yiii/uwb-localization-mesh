# UWB Localization Setup Guide for Dummies

This guide will get your UWB localization system running from scratch. Just copy and paste the commands in order.

**Note:** This project uses UV for dependency management. All Python commands in this guide use `uv run` to ensure the correct virtual environment is used.

## What You Need

**Hardware:**
- 1 Laptop (Mac/Linux/Windows) - runs the server and MQTT broker
- 4 Raspberry Pis - each with a UWB anchor module connected via USB
- 1 Phone to track (iOS with UWB support)

**Network:**
- All devices on the same WiFi network
- Laptop must be accessible from Raspberry Pis

---

## Step 1: Install Dependencies on Laptop

### First, Install UV (Python Package Manager)

#### macOS:
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart your shell or run: source ~/.bashrc (or ~/.zshrc)
```

#### Linux/Ubuntu:
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Restart your shell or run: source ~/.bashrc
```

#### Windows:
```bash
# Install UV using PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or using cmd:
curl -LsSf https://astral.sh/uv/install.cmd | cmd
```

### Then Install Mosquitto and Project Dependencies

#### macOS:
```bash
# Install Mosquitto MQTT broker
brew install mosquitto

# Install Python dependencies using UV (this uses uv.lock for exact versions)
uv sync
```

#### Linux/Ubuntu:
```bash
# Install Mosquitto MQTT broker
sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients

# Install Python dependencies using UV (this uses uv.lock for exact versions)
uv sync
```

#### Windows:
```bash
# Install Mosquitto MQTT broker from: https://mosquitto.org/download/

# Add to PATH environment variable
$env:PATH += ";C:\Users\limji\.local\bin" #or whatever default path u installed uv in
$env:PATH += ";C:\Program Files\mosquitto" #or whatever default path u installed mosquitto in 
.venv\Scripts\activate

# Install Python dependencies using UV (this uses uv.lock for exact versions)
uv sync
```

---

## Step 2: Install Dependencies on Each Raspberry Pi

Run these commands on **each of your 4 Raspberry Pis** :

```bash
# Update system
sudo apt-get update

# Install UV (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install serial port support
sudo apt-get install -y python3-serial

# Time sync (Do this before any sorta data collection / critical logging!)
sudo apt-get install -y chrony
sudo chronyd -q 'server pool.ntp.org iburst'

# Activate the venv. for Python interpreter and packages to be available in your current shell session
source .venv/bin/activate

# Install Python dependencies using UV (this uses uv.lock for exact versions)
uv sync
```

---

## Step 3: Start MQTT Broker (Laptop Terminal 1)

On your laptop, in the project directory:

```bash

# Start MQTT broker
mosquitto -c mosquitto.conf
# or
mosquitto -v 
```

You should see: `mosquitto version 2.x.x running`
When devices connect via MQTT u should see some sort of logging here

---

## Step 6: Start Localization Server (Laptop Terminal 2)

Open a **new terminal** on your laptop, navigate to the project directory, and run:

```bash
# Server connects to MQTT broker on the same laptop
uv run python Server_bring_up.py --broker localhost
```

You should see logs like:
```json
{"timestamp": "2025-10-08 10:30:00", "level": "INFO", "message": {"event": "server_config", "broker": "localhost", "port": 1884}}
```

---

## Step 7: Start Anchor 0 (RPi 0 Terminal)

On your **first Raspberry Pi**, navigate to the project directory and run:

```bash
# Replace YOUR_LAPTOP_IP with your laptop's IP
uv run python Anchor_bring_up.py --anchor-id 0 --broker YOUR_LAPTOP_IP
```

Example:
```bash
uv run python Anchor_bring_up.py --anchor-id 0 --broker 192.168.68.63 
```

You should see:
```
╔══════════════════════════════════════════════════════════════╗
║                     Anchor 0                               ║
║               Top-right anchor                             ║
╚══════════════════════════════════════════════════════════════╝

Configuration:
  Anchor ID:     0
  MQTT Broker:   192.168.68.66:1884
  Serial Port:   /dev/ttyUSB0
  Baud Rate:     3000000
  Client ID:     uwb_anchor_rpi0

Starting UWB measurement publishing...
✓ Connected to MQTT broker
✓ UWB hardware interface started
✓ Publishing measurements to MQTT
```

---

## Step 8: Start Anchor 1 (RPi 1 Terminal)

On your **second Raspberry Pi**:

```bash
# Replace YOUR_LAPTOP_IP with your laptop's IP
uv run python Anchor_bring_up.py --anchor-id 1 --broker YOUR_LAPTOP_IP
```

Example:
```bash
uv run python Anchor_bring_up.py --anchor-id 1 --broker 192.168.68.66
```

---

## Step 9: Start Anchor 2 (RPi 2 Terminal)

On your **third Raspberry Pi**:

```bash
# Replace YOUR_LAPTOP_IP with your laptop's IP
uv run python Anchor_bring_up.py --anchor-id 2 --broker YOUR_LAPTOP_IP
```

Example:
```bash
uv run python Anchor_bring_up.py --anchor-id 2 --broker 192.168.68.66
```

---

## Step 10: Start Anchor 3 (RPi 3 Terminal)

On your **fourth Raspberry Pi**:

```bash
# Replace YOUR_LAPTOP_IP with your laptop's IP
uv run python Anchor_bring_up.py --anchor-id 3 --broker YOUR_LAPTOP_IP
```

Example:
```bash
uv run python Anchor_bring_up.py --anchor-id 3 --broker 192.168.68.66
```

---

## Step 11: Verify Everything is Working

### Check Processed Vector Data (Recommended Debug Method)

Use the included data inspector for detailed debugging:

```bash
uv run python Data_collection/inspect_raw_data.py
```

This will show you:
- **Raw sensor readings** converted to local vectors
- **Global coordinate transformations** (accounting for anchor orientations)
- **Calculated phone positions** for each anchor
- **Validation** - checks if positions are within reasonable room bounds
- **Summary statistics** when you stop with Ctrl+C

**Example output:**
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

### Alternative: Raw MQTT Messages

If you prefer to see raw MQTT messages directly:

```bash
# Subscribe to all anchor messages
mosquitto_sub -h localhost -t "uwb/#"
```

### Check Server Position Updates

In your server terminal (Step 6), you should see position updates like:
```
Current position: [123.45 234.56  50.00]
```

---

## Troubleshooting

### "Connection refused" on Raspberry Pi
- Check your laptop's IP address is correct
- Verify Mosquitto is running on laptop: `ps aux | grep mosquitto`
- Test connectivity: `ping YOUR_LAPTOP_IP`

### "Failed to start UWB hardware interface"
- Check USB device is connected: `ls /dev/ttyUSB*`
- Check permissions: `sudo usermod -a -G dialout $USER` (then reboot)
- Try different serial port: `--serial-port /dev/ttyACM0`

### No position updates on server
- Verify all 4 anchors are running and connected
- Check MQTT messages are being published
- Ensure phone is in range and UWB is enabled

### Raspberry Pi can't connect to MQTT
- Ensure firewall allows port 1884: `sudo ufw allow 1884`
- Check network connectivity between RPi and laptop

### UWB board changed port (when say, upon manual reconnection)
- Check port using `lsusb` or `ls /dev/ttyUSB*`
- Use the new Usb port (eg if usb0 changed to usb1): `SERIAL_PORT=/dev/ttyUSB1 uv run python Anchor_bring_up.py --anchor-id 0 --broker 172.20.10.3`

---

## Next Steps

Once everything is running, you can:

1. **Run the unified visualization / audio UI:**
   ```bash
   # On laptop, in new terminal (embeds ServerBringUpProMax; broker + anchors must be up)
   uv run python Demos/UnifiedDemo/main_demo.py
   ```

2. **Test with your phone:**
   - Enable UWB in phone settings
   - Move around the tracked area
   - Watch position updates in server terminal

3. **Audio:** Use the **Adaptive Audio** and **Zone DJ** tabs inside the Unified Demo, or integrate via `packages/audio_mqtt_client` / `packages/audio_mqtt_server` (there is no separate `Demos/Follow_me_audio/` tree in this repo).

---

## Quick Reference Commands

### Start Everything (Copy-Paste Ready)

**On Laptop Terminal 1 (MQTT):**
```bash
cd uwb-localization-mesh
echo "listener 1884
allow_anonymous true" > mosquitto.conf
mosquitto -c mosquitto.conf
```

**On Laptop Terminal 2 (Server):**
```bash
cd uwb-localization-mesh
uv run python Server_bring_up.py --broker localhost
```

**On RPi 0:**
```bash
cd uwb-localization-mesh
uv run python Anchor_bring_up.py --anchor-id 0 --broker YOUR_LAPTOP_IP
```

**On RPi 1:**
```bash
cd uwb-localization-mesh
uv run python Anchor_bring_up.py --anchor-id 1 --broker YOUR_LAPTOP_IP
```

**On RPi 2:**
```bash
cd uwb-localization-mesh
uv run python Anchor_bring_up.py --anchor-id 2 --broker YOUR_LAPTOP_IP
```

**On RPi 3:**
```bash
cd uwb-localization-mesh
uv run python Anchor_bring_up.py --anchor-id 3 --broker YOUR_LAPTOP_IP
```

Replace `YOUR_LAPTOP_IP` with your actual laptop IP address (only needed for Raspberry Pi anchors)!
