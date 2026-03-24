"""
Laptop server for the Unified Demo: MQTT ingest, binning, PGO, and audio command publishing.

Lives under ``Demos/UnifiedDemo/`` next to ``main_demo.py``. Import ``ServerBringUpProMax`` from
here, or run this file directly as a headless server (repo root is added to ``sys.path`` below).

For **localization-only** (no audio MQTT), use ``Server_bring_up.py`` at the repository root.
"""

import sys
import os

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import json
import logging
import threading
import time
import datetime
from datetime import timezone
from collections import defaultdict
from queue import Queue
from typing import Dict, Optional, Union

import numpy as np
import uuid
import paho.mqtt.client as mqtt
from packages.datatypes.datatypes import Measurement, BinnedData, AnchorConfig
from packages.localization_algos.binning.sliding_window import SlidingWindowBinner, BinningMetrics
from packages.localization_algos.edge_creation.transforms import create_relative_measurement
from packages.localization_algos.edge_creation.anchor_edges import create_anchor_anchor_edges
from packages.localization_algos.pgo.solver import PGOSolver
from packages.uwb_mqtt_server.server import UWBMQTTServer
from packages.uwb_mqtt_server.config import MQTTConfig
from packages.audio_mqtt_server.follow_me_audio_server import AdaptiveAudioServer, clamp

# Setup JSON logging
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Defaults
DEFAULT_BROKER_IP = "localhost"
DEFAULT_BROKER_PORT = 1884
DEFAULT_USERNAME = "laptop"
DEFAULT_PASSWORD = "laptop"



class ServerBringUpProMax:
    """
    Central server that coordinates:
    1. MQTT measurement ingestion
    2. Binning and edge creation
    3. PGO solving
    4. State management
    """
    
    def __init__(
        self,
        mqtt_config: MQTTConfig,
        window_size_seconds: float = 1.0,
        jitter_std: float = 0.0  # Standard deviation for anchor position jitter (cm)
    ):
        """Initialize the server with configuration."""
        
        # Ground truth anchor positions (cm) - Consistent with Basic_render_graph
        # Anchors are mounted at 239 cm (2.39m) height
        self.true_nodes = {
            0: np.array([480, 600, 0]),  # top-right
            1: np.array([0, 600, 0]),    # top-left
            2: np.array([480, 0, 0]),    # bottom-right
            3: np.array([0, 0, 0])       # bottom-left (origin)
        } 
        
        # Working copy of nodes that can be jittered (jittering temporarily disabled)
        self.nodes = self.true_nodes.copy()
        self.jitter_std = jitter_std
        
        # Create anchor config for edge creation (using true positions for now)
        self.anchor_config = AnchorConfig(positions=self.nodes)
        
        # Latest state
        self.data: Dict[int, BinnedData] = {}  # phone_node_id -> latest binned data
        self.user_position: Optional[np.ndarray] = None  # User position
        self._position_lock = threading.Lock()  # Thread-safe access to user_position
        
        # Processing settings
        self.window_size_seconds = window_size_seconds
        
        # Thread-safe measurement storage
        self._measurements_lock = threading.Lock()
        self._measurements: Dict[int, Queue[Measurement]] = defaultdict(Queue)
        
        # Binning system (one per phone) - filtered binners for PGO processing
        self._binners_lock = threading.Lock()
        self._filtered_binners: Dict[int, SlidingWindowBinner] = {}

        # PGO solver
        self._pgo_solver = PGOSolver()

        # Pre-compute anchor-anchor edges
        self._anchor_edges = create_anchor_anchor_edges(self.anchor_config)
        
        # Start MQTT server
        self.uwb_mqtt_server = UWBMQTTServer(
            config=mqtt_config,
            on_measurement=self._handle_measurement
        )

        # Audio server (computes state, doesn't publish)
        self.adaptive_audio_server = AdaptiveAudioServer()
        
        # Audio MQTT setup for publishing commands
        client_id = f"server_bring_up_pro_max_{uuid.uuid4()}"
        self.audio_client = mqtt.Client(client_id=client_id)
        self.audio_client.username_pw_set(username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD)
        self.audio_topic = "audio/commands"
        
        # Connect MQTT for audio
        self.audio_client.connect(mqtt_config.broker, mqtt_config.port, mqtt_config.keepalive)
        self.audio_client.loop_start()

        # Audio loop control
        self._adaptive_audio_active = threading.Event()
        self._zone_dj_active = threading.Event()
        self._adaptive_audio_thread: Optional[threading.Thread] = None
        self._zone_dj_thread: Optional[threading.Thread] = None
        
        # Volume tracking (for compatibility with main_demo.py)
        self._volumes_lock = threading.Lock()
        self.volumes = {0: 70, 1: 70, 2: 70, 3: 70}  # Default volumes
        
        # Simulation speed property (for compatibility)
        self.simulation_speed = 1.0
        
        # Track state for playback simulation
        self.current_playlist = 1
        self.current_track_index = 0
        self.current_seek_position = 0.0

        # Processing thread control
        self._stop_event = threading.Event()
        self._processor_thread = threading.Thread(
            target=self._process_measurements,
            daemon=True
        )
        
        print("🎛️ Server Bring-Up Pro Max initialized")
        
        logger.info(json.dumps({
            "event": "server_initialized",
            "n_anchors": len(self.nodes),
            "window_size": window_size_seconds
        }))
        
    def _get_or_create_filtered_binner(self, phone_id: int) -> SlidingWindowBinner:
        """Thread-safe access to per-phone filtered binners (for PGO processing)."""
        with self._binners_lock:
            if phone_id not in self._filtered_binners:
                self._filtered_binners[phone_id] = SlidingWindowBinner(
                    window_size_seconds=self.window_size_seconds
                )
            return self._filtered_binners[phone_id]
        
    def _publish(self, topic: str, payload_obj: dict) -> None:
        """Publish MQTT message."""
        payload = json.dumps(payload_obj, separators=(",", ":"))
        self.audio_client.publish(topic, payload, qos=1)

    def _publish_commands(self, commands: list) -> None:
        """
        Publish audio commands to MQTT.
        
        Args:
            commands (list of command dicts from AdaptiveAudioServer)
        """
        for cmd in commands:
            msg = {
                "command": cmd['command'],
                "execute_time": cmd['execute_time'],
                "rpi_id": cmd['rpi_id'],
                "command_id": str(uuid.uuid4()),
            }
            if cmd.get('volume') is not None:
                msg["target_volume"] = clamp(cmd['volume'])
            if cmd.get('track_file') is not None:
                msg["track_file"] = cmd['track_file']

            if cmd['rpi_id'] is None:
                topic = f"{self.audio_topic}/broadcast"
            else:
                topic = f"{self.audio_topic}/rpi_{cmd['rpi_id']}"
            
            self._publish(topic, msg)


    def start(self):
        """Start the server and processing thread."""
        # Start MQTT
        self.uwb_mqtt_server.start()

        # Start processor
        self._processor_thread.start()

        logger.info(json.dumps({
            "event": "server_started"
        }))
    
    def adaptive_audio_start(self):
        """Start the adaptive audio demo in a background thread."""
        if self._adaptive_audio_thread is None or not self._adaptive_audio_thread.is_alive():
            self._adaptive_audio_active.set()
            self._adaptive_audio_thread = threading.Thread(
                target=self._adaptive_audio_loop,
                daemon=True
            )
            self._adaptive_audio_thread.start()
            logger.info(json.dumps({"event": "adaptive_audio_started"}))

    def adaptive_audio_stop(self):
        """Stop the adaptive audio demo background thread."""
        self._adaptive_audio_active.clear()
        # Send pause commands
        global_time = time.time()
        pause_state = self.adaptive_audio_server.compute_pause_all_state(global_time)
        self._publish_commands(pause_state['commands'])
        logger.info(json.dumps({"event": "adaptive_audio_stopped"}))

    def _adaptive_audio_loop(self):
        """
        Background loop for adaptive audio demo.
        
        Polls user position and publishes commands to specific RPi topics.
        Even though audio_state reports "front" or "back" pairs conceptually,
        the commands contain explicit rpi_id values (0, 1, 2, 3) which are used
        to publish to the correct MQTT topics (e.g., audio/commands/rpi_2).
        """
        update_interval = 0.1  # Update every 100ms
        while self._adaptive_audio_active.is_set() and not self._stop_event.is_set():
            try:
                # Get current position (thread-safe)
                with self._position_lock:
                    position = self.user_position
                
                if position is not None:
                    # Compute audio state (returns commands with explicit rpi_id values)
                    global_time = time.time()
                    audio_state = self.adaptive_audio_server.compute_adaptive_audio_state(
                        position, global_time
                    )
                    
                    # Publish commands to specific RPi topics based on rpi_id in each command
                    if audio_state['commands']:
                        self._publish_commands(audio_state['commands'])
                        
                        # Log status
                        vols = audio_state['volumes']
                        pair = audio_state['current_pair'] or "unknown"
                        logger.debug(json.dumps({
                            "event": "adaptive_audio_update",
                            "pair": pair,
                            "volumes": vols,
                            "n_commands": len(audio_state['commands'])
                        }))
                
                time.sleep(update_interval)
            except Exception as e:
                logger.error(json.dumps({
                    "event": "adaptive_audio_loop_error",
                    "error": str(e)
                }))
                time.sleep(update_interval)

    def zone_dj_start(self):
        """Start the zone DJ demo in a background thread."""
        if self._zone_dj_thread is None or not self._zone_dj_thread.is_alive():
            self._zone_dj_active.set()
            self._zone_dj_thread = threading.Thread(
                target=self._zone_dj_loop,
                daemon=True
            )
            self._zone_dj_thread.start()
            logger.info(json.dumps({"event": "zone_dj_started"}))

    def zone_dj_stop(self):
        """Stop the zone DJ demo background thread."""
        self._zone_dj_active.clear()
        # Send pause commands
        global_time = time.time()
        pause_state = self.adaptive_audio_server.compute_pause_all_state(global_time)
        self._publish_commands(pause_state['commands'])
        logger.info(json.dumps({"event": "zone_dj_stopped"}))

    def _zone_dj_loop(self):
        """Background loop for zone DJ demo."""
        # Zone DJ starts once, then just maintains
        global_time = time.time()
        zone_dj_state = self.adaptive_audio_server.compute_zone_dj_state(global_time)
        self._publish_commands(zone_dj_state['commands'])
        
        logger.info(json.dumps({
            "event": "zone_dj_initialized",
            "volumes": zone_dj_state['volumes']
        }))
        
        # Keep thread alive while active (can be extended for periodic updates)
        while self._zone_dj_active.is_set() and not self._stop_event.is_set():
            time.sleep(0.5)

    def set_playlist(self, playlist_number: int):
        """
        Set the current playlist by number (1-5).
        Updates the AdaptiveAudioServer's song queue.
        """
        # Update AdaptiveAudioServer playlist
        if self.adaptive_audio_server:
            self.adaptive_audio_server.set_playlist(playlist_number)
        
        # Store playlist selection for compatibility
        self.current_playlist = playlist_number
        logger.info(json.dumps({
            "event": "playlist_set",
            "playlist_number": playlist_number
        }))

    def stop(self):
        """Stop all processing."""
        self._stop_event.set()
        
        # Stop audio loops
        self.adaptive_audio_stop()
        self.zone_dj_stop()
        
        # Wait for threads to finish
        if self._adaptive_audio_thread and self._adaptive_audio_thread.is_alive():
            self._adaptive_audio_thread.join(timeout=1.0)
        if self._zone_dj_thread and self._zone_dj_thread.is_alive():
            self._zone_dj_thread.join(timeout=1.0)
        
        # Stop MQTT
        self.uwb_mqtt_server.stop()
        self.audio_client.loop_stop()
        self.audio_client.disconnect()

        logger.info(json.dumps({
            "event": "server_stopped"
        }))
        
    def _handle_measurement(self, measurement: Measurement):
        """
        Callback from MQTT server for new measurements.
        Adds to filtered binner for PGO processing.
        Only filtered measurements are queued for PGO processing.
        """
        # Add to filtered binner for PGO processing
        filtered_binner = self._get_or_create_filtered_binner(measurement.phone_node_id)
        was_added_filtered = filtered_binner.add_measurement(measurement)
        
        # Only queue for processing if it was accepted
        if was_added_filtered:
            with self._measurements_lock:
                self._measurements[measurement.phone_node_id].put(measurement)

        # Log metrics periodically from filtered binner
        filtered_metrics = filtered_binner.get_metrics()
        total_processed = (filtered_metrics.total_measurements +
                          filtered_metrics.rejected_measurements +
                          filtered_metrics.late_drops)

        if total_processed % 100 == 0:  # Every 100 measurements processed
            logger.info(json.dumps({
                "event": "binning_metrics",
                "phone_id": measurement.phone_node_id,
                "metrics": {
                    "accepted": filtered_metrics.total_measurements,
                    "rejected": filtered_metrics.rejected_measurements,
                    "late_drops": filtered_metrics.late_drops,
                    "rejection_rate": f"{100 * filtered_metrics.rejected_measurements / total_processed:.1f}%",
                    "rejection_reasons": filtered_metrics.rejection_reasons,
                    "per_anchor": filtered_metrics.measurements_per_anchor,
                    "window_span": filtered_metrics.window_span_sec
                }
            }))

        # Log individual rejections for debugging (can be disabled later)
        if not was_added_filtered and filtered_metrics.rejected_measurements <= 50:  # Log first 50 rejections
            logger.debug(json.dumps({
                "event": "measurement_rejected",
                "phone_id": measurement.phone_node_id,
                "anchor_id": measurement.anchor_id,
                "rejection_count": filtered_metrics.rejected_measurements,
                "distance": float(np.linalg.norm(measurement.local_vector))
            }))
            
    def _process_measurements(self):
        """
        Main processing loop that runs in a separate thread.
        Uses binned data to create edges and run PGO.
        """
        while not self._stop_event.is_set():
            try:
                # Process each phone's data
                with self._measurements_lock:
                    phone_ids = list(self._measurements.keys())
                    
                for phone_id in phone_ids:
                    # Get filtered binned data for PGO processing
                    filtered_binner = self._get_or_create_filtered_binner(phone_id)
                    binned = filtered_binner.create_binned_data(phone_id)
                    
                    if binned:
                        # Update state
                        self.data[phone_id] = binned
                        
                        # Create phone-anchor edges
                        phone_edges = []
                        for anchor_id, vectors in binned.measurements.items():
                            if vectors:  # Only if we have measurements
                                avg_vector = np.mean(vectors, axis=0)
                                edge = create_relative_measurement(
                                    anchor_id,
                                    phone_id,
                                    avg_vector
                                )
                                phone_edges.append(edge)
                        
                        # Prepare PGO inputs
                        
                        # # Apply per-solve jitter to anchor positions (commented out)
                        # if self.jitter_std > 0:
                        #     # Temporarily jitter nodes for this solve
                        #     temp_nodes = self.true_nodes.copy()
                        #     for anchor_id in temp_nodes:
                        #         jitter = np.random.normal(0, self.jitter_std, size=3)
                        #         temp_nodes[anchor_id] = self.true_nodes[anchor_id] + jitter
                        #     
                        #     # Create temporary anchor config and edges with jittered positions
                        #     temp_anchor_config = AnchorConfig(positions=temp_nodes)
                        #     temp_anchor_edges = create_anchor_anchor_edges(temp_anchor_config)
                        # else:
                        #     # Use non-jittered edges
                        #     temp_anchor_edges = self._anchor_edges

                        nodes: Dict[str, Optional[np.ndarray]] = {
                            # Start with floating anchors
                            'anchor_0': None,
                            'anchor_1': None,
                            'anchor_2': None,
                            'anchor_3': None,
                            f'phone_{phone_id}': None  # Phone to optimize
                        }
                        
                        # Combine all edges (using non-jittered edges for now)
                        edges = phone_edges + self._anchor_edges
                        
                        # Run PGO with anchoring
                        try:
                            pgo_result = self._pgo_solver.solve(
                                nodes=nodes,
                                edges=edges,
                                anchor_positions=self.true_nodes  # Anchor to TRUE positions
                            )
                            
                            if pgo_result.success:
                                # Update user position from anchored results (thread-safe)
                                with self._position_lock:
                                    self.user_position = pgo_result.node_positions[f'phone_{phone_id}']

                                logger.info(json.dumps({
                                    "event": "position_updated",
                                    "phone_id": phone_id,
                                    "position": self.user_position.tolist(),
                                    "error": pgo_result.error,
                                    "metrics": {
                                        "n_edges": len(edges),
                                        "n_phone_edges": len(phone_edges),
                                        "n_anchor_edges": len(self._anchor_edges)
                                    }
                                }))
                                
                        except Exception as e:
                            logger.error(json.dumps({
                                "event": "pgo_failed",
                                "error": str(e)
                            }))
                            
            except Exception as e:
                logger.error(json.dumps({
                    "event": "processing_error",
                    "error": str(e)
                }))
                
            # Sleep briefly to prevent tight loop
            time.sleep(0.01)
    
    # ================================================================
    # MISSING METHODS IMPLEMENTATION
    # ================================================================
    
    def get_speaker_volumes(self) -> Dict[int, int]:
        """Get current speaker volumes from local tracking."""
        with self._volumes_lock:
            return self.volumes.copy()
    
    def get_speaker_positions(self) -> Dict[int, np.ndarray]:
        """Get speaker positions in world coordinates (meters)."""
        positions = {}
        for speaker_id, pos_cm in self.true_nodes.items():
            # Convert from cm to meters
            positions[speaker_id] = pos_cm / 100.0
        return positions
    
    # ================================================================
    # PLAYBACK CONTROL METHODS
    # ================================================================
    
    def play(self):
        """Start playback."""
        if self.adaptive_audio_server:
            # Start all speakers at current volume levels
            global_time = time.time()
            commands = []
            with self._volumes_lock:
                for speaker_id, volume in self.volumes.items():
                    # Start command
                    start_cmd = {
                        'command': 'start',
                        'execute_time': global_time + 0.5,
                        'rpi_id': speaker_id,
                        'volume': None
                    }
                    # Volume command
                    vol_cmd = {
                        'command': 'volume',
                        'execute_time': global_time + 0.6,
                        'rpi_id': speaker_id,
                        'volume': volume
                    }
                    commands.extend([start_cmd, vol_cmd])
            self._publish_commands(commands)
        logger.info(json.dumps({"event": "play_requested"}))
    
    def pause(self):
        """Pause playback."""
        if self.adaptive_audio_server:
            global_time = time.time()
            pause_state = self.adaptive_audio_server.compute_pause_all_state(global_time)
            self._publish_commands(pause_state['commands'])
        logger.info(json.dumps({"event": "pause_requested"}))
    
    def stop_playback(self):
        """Stop playback."""
        self.pause()  # Same as pause for now
        logger.info(json.dumps({"event": "stop_playback_requested"}))
    
    def skip_track(self):
        """Skip to next track."""
        if self.adaptive_audio_server:
            new_song = self.adaptive_audio_server.next_song()
            logger.info(json.dumps({"event": "skip_track_requested", "new_song": new_song}))
            
            # Send load_track commands to all speakers
            global_time = time.time()
            load_commands = self.adaptive_audio_server.get_load_track_commands(global_time)
            if load_commands['commands']:
                self._publish_commands(load_commands['commands'])
                logger.info(json.dumps({"event": "load_track_commands_sent", "track": new_song, "num_commands": len(load_commands['commands'])}))
        else:
            # Fallback: simulate track skipping by updating track counter
            self.current_track_index += 1
            logger.info(json.dumps({"event": "skip_track_requested", "new_index": self.current_track_index}))
    
    def previous_track(self):
        """Go to previous track."""
        if self.adaptive_audio_server:
            new_song = self.adaptive_audio_server.previous_song()
            logger.info(json.dumps({"event": "previous_track_requested", "new_song": new_song}))
            
            # Send load_track commands to all speakers
            global_time = time.time()
            load_commands = self.adaptive_audio_server.get_load_track_commands(global_time)
            if load_commands['commands']:
                self._publish_commands(load_commands['commands'])
                logger.info(json.dumps({"event": "load_track_commands_sent", "track": new_song, "num_commands": len(load_commands['commands'])}))
        else:
            # Fallback: simulate previous track by updating track counter
            self.current_track_index = max(0, self.current_track_index - 1)
            logger.info(json.dumps({"event": "previous_track_requested", "new_index": self.current_track_index}))
    
    def seek(self, position: float):
        """Seek to position in current track."""
        # Store seek position for future use
        self.current_seek_position = max(0.0, min(1.0, position))
        logger.info(json.dumps({"event": "seek_requested", "position": self.current_seek_position}))
    
    # ================================================================
    # AUDIO STATE QUERY METHODS
    # ================================================================
    
    def get_queue_preview(self, limit: int = 5) -> list:
        """Get preview of upcoming tracks."""
        if self.adaptive_audio_server:
            return self.adaptive_audio_server.get_queue_preview(limit)
        # Fallback to playlist-based queue preview
        return [f"Playlist {self.current_playlist} - Track {i+1}" for i in range(limit)]
    
    def get_current_track(self) -> str:
        """Get current track name."""
        if self.adaptive_audio_server:
            return self.adaptive_audio_server.get_current_song()
        # Fallback
        return f"Playlist {self.current_playlist} - Track {self.current_track_index + 1}"
    
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._adaptive_audio_active.is_set() or self._zone_dj_active.is_set()
    
    def get_playback_progress(self) -> float:
        """Get playback progress 0.0-1.0."""
        # Return current seek position or simulate progress
        if hasattr(self, 'current_seek_position'):
            return self.current_seek_position
        # Simulate progress based on time if playing
        if self.is_playing():
            import time
            return (time.time() % 60) / 60.0  # Cycle every minute
        return 0.0
    
    def get_speaker_states(self) -> Dict[int, dict]:
        """Get speaker states."""
        volumes = self.get_speaker_volumes()
        states = {}
        for speaker_id, volume in volumes.items():
            states[speaker_id] = {
                "volume": volume,
                "playing": self.is_playing(),
                "connected": True
            }
        return states
    
    # ================================================================
    # VOLUME CONTROL METHODS
    # ================================================================
    
    def set_global_volume(self, volume: int):
        """Set volume for all speakers."""
        clamped_volume = max(0, min(100, volume))
        
        # Update local tracking
        with self._volumes_lock:
            for speaker_id in self.volumes:
                self.volumes[speaker_id] = clamped_volume
        
        # Send MQTT commands
        if self.adaptive_audio_server:
            global_time = time.time()
            commands = []
            for speaker_id in range(4):
                cmd = {
                    'command': 'volume',
                    'execute_time': global_time + 0.5,
                    'rpi_id': speaker_id,
                    'volume': clamped_volume
                }
                commands.append(cmd)
            self._publish_commands(commands)
        logger.info(json.dumps({"event": "global_volume_set", "volume": clamped_volume}))
    
    def set_volume(self, device_id: int, volume: int):
        """Set volume for specific speaker."""
        clamped_volume = max(0, min(100, volume))
        
        # Update local tracking
        if device_id in range(4):
            with self._volumes_lock:
                self.volumes[device_id] = clamped_volume
        
        # Send MQTT command
        if self.adaptive_audio_server:
            global_time = time.time()
            cmd = {
                'command': 'volume',
                'execute_time': global_time + 0.5,
                'rpi_id': device_id,
                'volume': clamped_volume
            }
            self._publish_commands([cmd])
        logger.info(json.dumps({"event": "volume_set", "device_id": device_id, "volume": clamped_volume}))
    
    # ================================================================
    # AUDIO MODE CONTROL METHODS
    # ================================================================
    
    def enable_adaptive_audio(self, enabled: bool):
        """Enable/disable adaptive audio mode."""
        if enabled:
            self.adaptive_audio_start()
        else:
            self.adaptive_audio_stop()
        logger.info(json.dumps({"event": "adaptive_audio_enabled", "enabled": enabled}))
    
    def enable_zone_dj(self, enabled: bool):
        """Enable/disable zone DJ mode."""
        if enabled:
            self.zone_dj_start()
        else:
            self.zone_dj_stop()
        logger.info(json.dumps({"event": "zone_dj_enabled", "enabled": enabled}))
    
    def bypass_audio_processing(self, bypass: bool):
        """Bypass audio processing."""
        if bypass:
            # Stop all audio processing
            self.adaptive_audio_stop()
            self.zone_dj_stop()
        logger.info(json.dumps({"event": "bypass_audio_processing", "bypass": bypass}))
    
    # Alias methods for compatibility with main_demo.py
    def adaptive_audio_demo(self):
        """Alias for adaptive_audio_start()."""
        self.adaptive_audio_start()
    
    def stop_adaptive_audio_demo(self):
        """Alias for adaptive_audio_stop()."""
        self.adaptive_audio_stop()
    
    def zone_dj_demo(self):
        """Alias for zone_dj_start()."""
        self.zone_dj_start()
    
    def stop_zone_dj_demo(self):
        """Alias for zone_dj_stop()."""
        self.zone_dj_stop()



if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='UWB Server')
    parser.add_argument('--broker', type=str, default='localhost',
                      help='MQTT broker IP address')
    parser.add_argument('--port', type=int, default=1884,
                      help='MQTT broker port')
    args = parser.parse_args()
    
    # Configure MQTT with command line arguments
    mqtt_config = MQTTConfig(
        broker=args.broker,
        port=args.port
    )
    
    logger.info(json.dumps({
        "event": "server_config",
        "broker": args.broker,
        "port": args.port
    }))
    
    # Start server (jitter temporarily disabled)
    server = ServerBringUpProMax(
        mqtt_config=mqtt_config,
        jitter_std=0.0  # Jittering disabled
    )
    
    try:
        server.start()
        
        # Keep main thread alive
        while True:
            if server.user_position is not None:
                print(f"Current position: {server.user_position}")
            time.sleep(1)
            
    except KeyboardInterrupt:
        server.stop()