#!/usr/bin/env python3
"""
Follow-Me Methods for audio control

Coordinates UWB positioning (via ServerBringUp) and adaptive audio control.
ServerBringUp tracks user position and adapts audio accordingly.

Architecture:
- ServerBringUp: Handles UWB measurements, PGO, position tracking
- FollowMeAudioServer: Controls RPi speakers based on position
- FollowMeAudioClient: Receives and plays audio on RPi

Logic:
- If y >= 300 → play on speakers 1 and 0 (back pair)
- If y < 300  → play on speakers 2 and 3 (front pair)
- For x-axis panning around x == 240:
  - At x == 240 → both speakers volume = 70
  - Move left  → increase RIGHT speaker volume, decrease LEFT speaker volume
  - Move right → increase LEFT speaker volume, decrease RIGHT speaker volume

Usage:
    uv run follow-me_audio_server.py --broker localhost --port 1884

"""


import json
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
import numpy as np

import paho.mqtt.client as mqtt
import uuid

# Import the playlist controller
from .playlist_controller.playlist_controller import PlaylistController

# Suppress MQTT and position logs logs after imports (to override basicConfig) - only show WARNING and above
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("Server_bring_up").setLevel(logging.WARNING)
logging.getLogger("packages.uwb_mqtt_server").setLevel(logging.WARNING)


# Defaults
DEFAULT_BROKER_IP = "localhost"
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"


def clamp(value: float, lo: int = 0, hi: int = 100) -> int:
    v = int(round(value))
    return max(lo, min(hi, v))


class AdaptiveAudioServer:
    """
    Audio controller that computes audio state based on position.
    
    Returns commands and state information to be published by ServerBringUp.
    Does not handle MQTT publishing bc it's done by the main server.
    """
    
    def __init__(self):
        """Initialize audio server state."""
        self.current_pair: Optional[str] = None  # "front" or "back"
        self.started_for_pair: Optional[str] = None
        self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}
        self._last_position: Optional[np.ndarray] = None
        
        # Initialize playlist controller for professional playlist management
        self.playlist_controller = PlaylistController()
        
        # Song queue management - now using PlaylistController
        self.song_queue = self.playlist_controller.get_playlist(1)  # Start with playlist 1
        self.current_track_index = 0
        self.current_playlist = 1

    def compute_adaptive_audio_state(self, position, global_time: float, execute_delay_ms: int = 500) -> dict:
        """
        Compute adaptive audio state based on user position.
        
        Args:
            position: numpy array or tuple [x, y, z] in cm
            global_time: Current global time (seconds since epoch)
            execute_delay_ms: Delay in milliseconds before executing commands
            
        Returns:
            dict with keys:
            - 'commands': list of command dicts, each with:
                - 'command': str ("start", "pause", "volume")
                - 'rpi_id': int (0-3) or None for broadcast
                - 'volume': int (0-100) or None
                - 'execute_time': float (global time for execution)
            - 'volumes': dict {0: vol, 1: vol, 2: vol, 3: vol}
            - 'current_pair': str ("front" or "back")
        """
        # Convert to numpy array if needed
        if not isinstance(position, np.ndarray):
            position = np.array(position)
        
        # Check if position actually changed (avoid redundant updates)
        if self._last_position is not None:
            if np.linalg.norm(position - self._last_position) < 1.0:
                # Return current state without new commands
                return {
                    'commands': [],
                    'volumes': self.volumes.copy(),
                    'current_pair': self.current_pair
                }
        
        self._last_position = position.copy()
        
        # Compute pair and volumes
        pair, (left_vol, right_vol) = self._compute_pair_and_volumes(position)
        
        # Calculate execute time
        execute_time = global_time + (execute_delay_ms / 1000.0)
        
        # Generate commands
        commands = []
        
        if pair == "front":
            # Active: speakers 2 (LEFT), 3 (RIGHT). Inactive: 0,1
            # Ensure active pair is started at least once
            if self.started_for_pair != pair:
                # Unmute all first to ensure START is heard
                for r in [0, 1, 2, 3]:
                    commands.append({
                        'command': 'volume',
                        'rpi_id': r,
                        'volume': 70,
                        'execute_time': execute_time
                    })
                for r in [0, 1, 2, 3]:
                    commands.append({
                        'command': 'start',
                        'rpi_id': r,
                        'volume': None,
                        'execute_time': execute_time
                    })
                self.started_for_pair = pair

            # Set active volumes
            commands.append({
                'command': 'volume',
                'rpi_id': 2,
                'volume': left_vol,
                'execute_time': execute_time
            })
            commands.append({
                'command': 'volume',
                'rpi_id': 3,
                'volume': right_vol,
                'execute_time': execute_time
            })
            # Mute inactive
            commands.append({
                'command': 'volume',
                'rpi_id': 0,
                'volume': 0,
                'execute_time': execute_time
            })
            commands.append({
                'command': 'volume',
                'rpi_id': 1,
                'volume': 0,
                'execute_time': execute_time
            })
            
            # Update local state
            self.volumes[2] = left_vol
            self.volumes[3] = right_vol
            self.volumes[0] = 0
            self.volumes[1] = 0

        else:  # back
            # Active: speakers 1 (LEFT), 0 (RIGHT). Inactive: 2,3
            if self.started_for_pair != pair:
                for r in [0, 1, 2, 3]:
                    commands.append({
                        'command': 'volume',
                        'rpi_id': r,
                        'volume': 70,
                        'execute_time': execute_time
                    })
                for r in [0, 1, 2, 3]:
                    commands.append({
                        'command': 'start',
                        'rpi_id': r,
                        'volume': None,
                        'execute_time': execute_time
                    })
                self.started_for_pair = pair

            commands.append({
                'command': 'volume',
                'rpi_id': 1,
                'volume': left_vol,
                'execute_time': execute_time
            })
            commands.append({
                'command': 'volume',
                'rpi_id': 0,
                'volume': right_vol,
                'execute_time': execute_time
            })
            # Mute inactive
            commands.append({
                'command': 'volume',
                'rpi_id': 2,
                'volume': 0,
                'execute_time': execute_time
            })
            commands.append({
                'command': 'volume',
                'rpi_id': 3,
                'volume': 0,
                'execute_time': execute_time
            })
            
            # Update local state
            self.volumes[1] = left_vol
            self.volumes[0] = right_vol
            self.volumes[2] = 0
            self.volumes[3] = 0

        self.current_pair = pair
        
        return {
            'commands': commands,
            'volumes': self.volumes.copy(),
            'current_pair': self.current_pair
        }

    def _compute_pair_and_volumes(self, position) -> Tuple[str, Tuple[int, int]]:
        """
        Returns (pair, (left_vol, right_vol)) where:
        - pair == "front" → speakers (2,3)
        - pair == "back"  → speakers (1,0)
        - Volumes are for LEFT vs RIGHT speaker in the selected pair
        """
        x = float(position[0])
        y = float(position[1])

        # Pair by Y threshold - updated for new coordinate system (600x480)
        pair = "back" if y >= 240.0 else "front"

        # Pan by X around center x == 300 (center of 600-wide space)
        center_x = 300.0
        delta = x - center_x  # >0 → right; <0 → left

        base = 70.0
        k = 0.1  # volume change per cm offset from center

        # Moving right (delta>0): increase LEFT, decrease RIGHT
        left_vol = base + k * delta
        right_vol = base - k * delta

        left_vol = clamp(left_vol)
        right_vol = clamp(right_vol)

        return pair, (left_vol, right_vol)

    def compute_zone_dj_state(self, global_time: float, execute_delay_ms: int = 500) -> dict:
        """
        Compute Zone DJ state: all speakers at 70% volume.
        
        Args:
            global_time: Current global time (seconds since epoch)
            execute_delay_ms: Delay in milliseconds before executing commands
            
        Returns:
            dict with keys:
            - 'commands': list of command dicts
            - 'volumes': dict {0: 70, 1: 70, 2: 70, 3: 70}
        """
        execute_time = global_time + (execute_delay_ms / 1000.0)
        commands = []
        
        # Set all volumes to 70%
        for r in [0, 1, 2, 3]:
            commands.append({
                'command': 'volume',
                'rpi_id': r,
                'volume': 70,
                'execute_time': execute_time
            })
            self.volumes[r] = 70
        
        # Start all speakers
        for r in [0, 1, 2, 3]:
            commands.append({
                'command': 'start',
                'rpi_id': r,
                'volume': None,
                'execute_time': execute_time
            })
        
        return {
            'commands': commands,
            'volumes': self.volumes.copy()
        }

    def compute_pause_all_state(self, global_time: float, execute_delay_ms: int = 500) -> dict:
        """
        Compute pause all state.
        
        Args:
            global_time: Current global time (seconds since epoch)
            execute_delay_ms: Delay in milliseconds before executing commands
            
        Returns:
            dict with 'commands' list
        """
        execute_time = global_time + (execute_delay_ms / 1000.0)
        commands = []
        
        for r in [0, 1, 2, 3]:
            commands.append({
                'command': 'pause',
                'rpi_id': r,
                'volume': None,
                'execute_time': execute_time
            })
        
        return {
            'commands': commands
        }
    
    # ================================================================
    # SONG QUEUE MANAGEMENT METHODS
    # ================================================================
    
    def next_song(self) -> str:
        """
        Skip to the next song in the queue.
        Returns the new current song name.
        """
        if self.song_queue:
            self.current_track_index = (self.current_track_index + 1) % len(self.song_queue)
            return self.song_queue[self.current_track_index]
        return "No songs in queue"
    
    def get_load_track_commands(self, global_time: float, execute_delay_ms: int = 500) -> dict:
        """
        Generate load_track commands for all speakers to switch to current song.
        
        Args:
            global_time: Current global time
            execute_delay_ms: Delay before execution (default 500ms)
            
        Returns:
            Dict with commands to load current track on all speakers
        """
        if not self.song_queue or self.current_track_index >= len(self.song_queue):
            return {'commands': []}
        
        current_track = self.song_queue[self.current_track_index]
        execute_time = global_time + (execute_delay_ms / 1000.0)
        
        # Generate load_track command for all speakers
        commands = []
        for rpi_id in [0, 1, 2, 3]:
            commands.append({
                'command': 'load_track',
                'rpi_id': rpi_id,
                'track_file': current_track,
                'execute_time': execute_time
            })
        
        return {
            'commands': commands,
            'current_track': current_track,
            'track_index': self.current_track_index
        }
    
    def previous_song(self) -> str:
        """
        Go to the previous song in the queue.
        Returns the new current song name.
        """
        if self.song_queue:
            self.current_track_index = (self.current_track_index - 1) % len(self.song_queue)
            return self.song_queue[self.current_track_index]
        return "No songs in queue"
    
    def get_current_song(self) -> str:
        """Get the current song name."""
        if self.song_queue and 0 <= self.current_track_index < len(self.song_queue):
            return self.song_queue[self.current_track_index]
        return "No current song"
    
    def get_queue_preview(self, limit: int = 5) -> list:
        """Get preview of upcoming songs in the queue."""
        if not self.song_queue:
            return []
        
        preview = []
        for i in range(limit):
            index = (self.current_track_index + i) % len(self.song_queue)
            preview.append(self.song_queue[index])
        return preview
    
    def set_playlist(self, playlist_number: int):
        """
        Set the current playlist and update the song queue using PlaylistController.
        """
        self.current_playlist = playlist_number
        
        # Update song queue using the professional playlist controller
        self.song_queue = self.playlist_controller.get_playlist(playlist_number)
        
        # Reset to first track
        self.current_track_index = 0
