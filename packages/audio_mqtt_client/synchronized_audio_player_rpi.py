#!/usr/bin/env python3
"""
RPi Audio Player - MQTT Subscriber
Receives synchronized audio commands and executes them at specified global times
"""

import json
import time
import threading
import os
import sys
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
import pygame
import pathlib
from typing import Dict, Any

# Add packages to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
from uwb_mqtt_client.config import MQTTConfig

# ====== NETWORK CONFIGURATION ======
# DEFAULT_BROKER_IP = "192.168.1.100"  # Your laptop's IP address
DEFAULT_BROKER_IP = "172.20.10.3"  # MSI's ip addr on iphone hotspot
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"
# ====================================


class RPiAudioPlayer:
    def __init__(self, rpi_id: int, wav_file: str, broker_ip: str = DEFAULT_BROKER_IP):
        self.rpi_id = rpi_id
        # Auto-prepend directory path if not already included
        if not wav_file.startswith("Demos/Audio_Library/"):
            self.wav_file = f"Demos/Audio_Library/{wav_file}"
        else:
            self.wav_file = wav_file
        self.broker_ip = broker_ip
        self.current_volume = 70  # Start at 70%
        self.is_playing = False
        self.audio_ready = False
        
        # MQTT setup
        self.config = MQTTConfig(
            broker=broker_ip,
            port=DEFAULT_BROKER_PORT,
            client_id=f"audio_player_rpi_{rpi_id}"
        )
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.config.client_id)
        self.client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)
        
        # Topics to subscribe to
        self.broadcast_topic = "audio/commands/broadcast"
        self.rpi_topic = f"audio/commands/rpi_{rpi_id}"
        
        # Command queue for synchronized execution
        self.command_queue = []
        self.queue_lock = threading.Lock()
        
        # Initialize audio
        self.init_audio()
        
        # Connect to MQTT
        self.connect_mqtt()
        
        # Start command execution thread
        self.execution_thread = threading.Thread(target=self.command_executor, daemon=True)
        self.execution_thread.start()
        
        print(f"🎵 RPi {rpi_id} Audio Player Ready")
        print(f"   WAV file: {wav_file}")
        print(f"   Position: {'LEFT' if rpi_id in [1, 2] else 'RIGHT'}")
        print(f"   Initial volume: {self.current_volume}%")
    
    def init_audio(self):
        """Initialize pygame audio system."""
        try:
            # Configure for RPi 3.5mm jack
            os.environ["SDL_AUDIODRIVER"] = "alsa"
            os.environ["ALSA_CARD"] = "2"  # Use 3.5mm headphones jack
            
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
            pygame.mixer.init()
            
            # Check if WAV file exists
            wav_path = pathlib.Path(self.wav_file)
            if not wav_path.exists():
                raise FileNotFoundError(f"WAV file not found: {wav_path}")
            
            # Load the audio file with stereo channel separation
            self.load_stereo_channel(str(wav_path))
            self.audio_ready = True
            
            channel_name = "LEFT" if self.rpi_id in [1, 2] else "RIGHT"
            print(f"✅ Audio initialized successfully - Playing {channel_name} channel only")
            
        except Exception as e:
            print(f"❌ Audio initialization failed: {e}")
            self.audio_ready = False
    
    def load_stereo_channel(self, wav_path: str):
        """Load only the left or right channel of the stereo audio file."""
        import numpy as np
        import wave
        
        # Read the WAV file
        with wave.open(wav_path, 'rb') as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
        
        if channels != 2:
            # If not stereo, just load normally
            pygame.mixer.music.load(wav_path)
            return
        
        # Convert bytes to numpy array
        if sample_width == 2:  # 16-bit
            audio_data = np.frombuffer(frames, dtype=np.int16)
        elif sample_width == 4:  # 32-bit
            audio_data = np.frombuffer(frames, dtype=np.int32)
        else:
            # Fallback to normal loading
            pygame.mixer.music.load(wav_path)
            return
        
        # Reshape to separate left and right channels
        audio_data = audio_data.reshape(-1, 2)
        
        # Select the appropriate channel
        if self.rpi_id in [1, 2]:  # Left speakers - play left channel
            channel_data = audio_data[:, 0]
        else:  # Right speakers (0, 3) - play right channel
            channel_data = audio_data[:, 1]
        
        # Convert back to mono by duplicating the channel
        mono_data = np.column_stack((channel_data, channel_data))
        
        # Convert back to bytes
        if sample_width == 2:  # 16-bit
            mono_bytes = mono_data.astype(np.int16).tobytes()
        elif sample_width == 4:  # 32-bit
            mono_bytes = mono_data.astype(np.int32).tobytes()
        
        # Create a temporary WAV file with the selected channel
        temp_wav_path = f"temp_channel_{self.rpi_id}.wav"
        with wave.open(temp_wav_path, 'wb') as temp_wav:
            temp_wav.setnchannels(2)  # Keep as stereo for pygame compatibility
            temp_wav.setsampwidth(sample_width)
            temp_wav.setframerate(sample_rate)
            temp_wav.writeframes(mono_bytes)
        
        # Load the processed audio
        pygame.mixer.music.load(temp_wav_path)
        
        # Clean up temporary file after loading
        import os
        try:
            os.remove(temp_wav_path)
        except:
            pass
    
    def connect_mqtt(self):
        """Connect to MQTT broker and set up callbacks."""
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        try:
            self.client.connect(self.config.broker, self.config.port, self.config.keepalive)
            print(f"✅ Connected to MQTT broker at {self.config.broker}:{self.config.port}")
        except Exception as e:
            print(f"❌ Failed to connect to MQTT broker: {e}")
            sys.exit(1)
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        """MQTT connection callback."""
        if rc == 0:
            print("✅ MQTT Connected successfully")
            # Subscribe to relevant topics
            client.subscribe(self.broadcast_topic, qos=1)
            client.subscribe(self.rpi_topic, qos=1)
            print(f"📡 Subscribed to: {self.broadcast_topic}")
            print(f"📡 Subscribed to: {self.rpi_topic}")
        else:
            print(f"❌ MQTT Connection failed with code {rc}")
    
    def on_message(self, client, userdata, msg):
        """MQTT message callback."""
        try:
            print(f"📨 Received MQTT message on topic: {msg.topic}")
            print(f"📨 Payload: {msg.payload.decode()}")
            
            message = json.loads(msg.payload.decode())
            command = message.get("command")
            execute_time = message.get("execute_time")
            rpi_id = message.get("rpi_id")
            
            print(f"📨 Parsed - command: {command}, rpi_id: {rpi_id}, execute_time: {execute_time}")
            print(f"📨 My RPi ID: {self.rpi_id}")
            
            # Only process commands intended for this RPi or broadcast commands
            if rpi_id is None or rpi_id == self.rpi_id:
                print(f"📨 Processing command for this RPi")
                self.queue_command(command, execute_time, message)
            else:
                print(f"📨 Ignoring command for RPi {rpi_id}")
                
        except Exception as e:
            print(f"❌ Error processing MQTT message: {e}")
    
    def queue_command(self, command: str, execute_time: float, message: Dict[str, Any]):
        """Add command to execution queue."""
        with self.queue_lock:
            self.command_queue.append({
                "command": command,
                "execute_time": execute_time,
                "message": message,
                "queued_at": time.time()
            })
            
            # Sort queue by execute time
            self.command_queue.sort(key=lambda x: x["execute_time"])
            
            current_time = time.time()
            delay = execute_time - current_time
            
            print(f"📥 Queued: {command.upper()} (execute in {delay:.3f}s)")
    
    def execute_command(self, command: str, message: Dict[str, Any]):
        """Execute an audio command."""
        if not self.audio_ready:
            print(f"⚠️  Audio not ready, skipping command: {command}")
            return
        
        try:
            if command == "start":
                if not self.is_playing:
                    pygame.mixer.music.play(-1)  # Loop forever
                    self.is_playing = True
                    print(f"🎵 STARTED playing at {self.current_volume}%")
                else:
                    print(f"🎵 Already playing at {self.current_volume}%")
            
            elif command == "pause":
                if self.is_playing:
                    pygame.mixer.music.pause()
                    self.is_playing = False
                    print(f"⏸️  PAUSED at {self.current_volume}%")
                else:
                    print(f"⏸️  Already paused at {self.current_volume}%")
            
            elif command == "volume": # volume is set by the controller, but can be muted here (overridden with vol=0)
                # Handle volume command from controller
                target_volume = message.get("target_volume")
                if target_volume is not None:
                    old_volume = self.current_volume
                    self.current_volume = max(0, min(100, int(target_volume)))
                    pygame.mixer.music.set_volume(self.current_volume / 100.0)
                    print(f"🔊 VOLUME: {old_volume}% → {self.current_volume}%")
            
            elif command == "load_track":
                # Handle track loading command
                track_file = message.get("track_file")
                if track_file:
                    try:
                        # Stop current playback
                        was_playing = self.is_playing
                        if self.is_playing:
                            pygame.mixer.music.stop()
                            self.is_playing = False
                        
                        # Auto-prepend directory path if not already included
                        if not track_file.startswith("Demos/Audio_Library/"):
                            full_track_path = f"Demos/Audio_Library/{track_file}"
                        else:
                            full_track_path = track_file
                        
                        # Load new track
                        pygame.mixer.music.load(full_track_path)
                        print(f"🎵 LOADED: {track_file}")
                        
                        # Resume playback if it was playing before
                        if was_playing:
                            pygame.mixer.music.play(-1)  # Loop forever
                            self.is_playing = True
                            print(f"🎵 RESUMED playing: {track_file}")
                            
                    except pygame.error as e:
                        print(f"❌ Failed to load track {track_file}: {e}")
                else:
                    print(f"⚠️  load_track command missing track_file parameter")
            
            elif command in ["left", "right"]:
                old_volume = self.current_volume
                
                if command == "left":
                    if self.rpi_id in [1, 2]:  # Left speakers get louder
                        self.current_volume = min(100, self.current_volume + 10)
                    else:  # Right speakers get quieter
                        self.current_volume = max(0, self.current_volume - 10)
                else:  # command == "right"
                    if self.rpi_id in [1, 2]:  # Left speakers get quieter
                        self.current_volume = max(0, self.current_volume - 15)
                    else:  # Right speakers get louder
                        self.current_volume = min(100, self.current_volume + 15)
                
                # Apply volume change
                pygame.mixer.music.set_volume(self.current_volume / 100.0)
                
                print(f"🔊 {command.upper()}: {old_volume}% → {self.current_volume}%")
                
        except Exception as e:
            print(f"❌ Error executing command {command}: {e}")
    
    def command_executor(self):
        """Background thread that executes queued commands at the right time."""
        while True:
            current_time = time.time()
            
            with self.queue_lock:
                # Execute commands that are due
                commands_to_execute = []
                remaining_commands = []
                
                for cmd in self.command_queue:
                    if cmd["execute_time"] <= current_time:
                        commands_to_execute.append(cmd)
                    else:
                        remaining_commands.append(cmd)
                
                self.command_queue = remaining_commands
            
            # Execute commands outside the lock
            for cmd in commands_to_execute:
                actual_delay = current_time - cmd["execute_time"]
                print(f"⚡ EXECUTING: {cmd['command'].upper()} (delay: {actual_delay:+.3f}s)")
                self.execute_command(cmd["command"], cmd["message"])
            
            time.sleep(0.01)  # Small delay to prevent busy waiting
    
    def run(self):
        """Run the audio player."""
        try:
            print(f"🎧 RPi {self.rpi_id} Audio Player running...")
            print("Press Ctrl+C to stop")
            
            # Start MQTT loop
            self.client.loop_start()
            
            # Keep main thread alive
            while True:
                time.sleep(1)
                
                # Print status every 10 seconds
                if int(time.time()) % 10 == 0:
                    with self.queue_lock:
                        queue_size = len(self.command_queue)
                    status = "PLAYING" if self.is_playing else "STOPPED"
                    print(f"📊 Status: {status}, Volume: {self.current_volume}%, Queue: {queue_size}")
                    time.sleep(1)  # Prevent duplicate prints
                    
        except KeyboardInterrupt:
            print(f"\n👋 Shutting down RPi {self.rpi_id} Audio Player...")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            if self.audio_ready:
                pygame.mixer.music.stop()
                pygame.mixer.quit()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="RPi Audio Player")
    parser.add_argument("--id", type=int, required=True, help="RPi ID (1,2=left; 0,3=right)")
    parser.add_argument("--wav", default="P1 - Minor Mush - John Deley.wav", help="WAV file to play")
    parser.add_argument("--broker", default=DEFAULT_BROKER_IP, help="MQTT broker IP")
    
    args = parser.parse_args()
    
    # Validate RPi ID
    if args.id not in [0, 1, 2, 3]:
        print("❌ RPi ID must be 0, 1, 2, or 3")
        print("   RPi 1,2 = Left channel")
        print("   RPi 0,3 = Right channel")
        sys.exit(1)
    
    player = RPiAudioPlayer(args.id, args.wav, args.broker)
    player.run()


if __name__ == "__main__":
    main()
