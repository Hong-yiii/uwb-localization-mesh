"""
Basic UWB Position Visualizer (deprecated).

Superseded by Demos/UnifiedDemo/main_demo.py (tabbed PyQt app with PGO plot and more).
Kept for a minimal matplotlib-only path during bring-up debugging.
"""
import matplotlib
# matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import threading
from datetime import datetime
from pathlib import Path
import logging

from packages.uwb_mqtt_server.config import MQTTConfig
from Server_bring_up import ServerBringUp

# Room and anchor configuration
ROOM_WIDTH_CM = 480   # Width of room in cm
ROOM_HEIGHT_CM = 600  # Height of room in cm
GRID_SIZE_CM = 110    # Grid square size in cm

# Anchor positions (cm)
ANCHORS = {
    0: np.array([ROOM_WIDTH_CM, ROOM_HEIGHT_CM, 0]),  # Top-right
    1: np.array([0, ROOM_HEIGHT_CM, 0]),              # Top-left
    2: np.array([ROOM_WIDTH_CM, 0, 0]),              # Bottom-right
    3: np.array([0, 0, 0])                           # Bottom-left (origin)
}

class BasicVisualizer(ServerBringUp):
    """
    Simple visualization server that extends ServerBringUp.
    Provides clean, real-time display of UWB positioning.
    """
    
    def __init__(
        self,
        mqtt_config: MQTTConfig,
        window_size_seconds: float = 1.0,
        history_length: int = 5
    ):
        """Initialize the visualization server."""
        # Initialize base server
        super().__init__(mqtt_config, window_size_seconds)
        # Store config for visualization
        self.mqtt_config = mqtt_config
        
        # Tracking data
        self.position_history = deque(maxlen=history_length)
        self.current_position = None
        self.last_update = None
        
        # Visualization components
        self.fig = None
        self.ax = None
        self.trajectory_line = None
        self.current_marker = None
        self.status_text = None
        self.animation = None
        
        # Thread safety
        self.viz_lock = threading.Lock()
        
        # Setup logging
        logging.basicConfig(
            level=logging.WARNING,  # Only show warnings and errors
            format='%(levelname)s: %(message)s'
        )
        
    def setup_visualization(self):
        """Initialize the matplotlib visualization."""
        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        
        # Draw room grid
        self._draw_grid()
        
        # Draw anchors
        self._draw_anchors()
        
        # Initialize trajectory and current position
        self.trajectory_line, = self.ax.plot(
            [], [], 'b-', alpha=0.6, linewidth=2, 
            label="Trajectory"
        )
        self.current_marker = self.ax.scatter(
            [], [], s=200, c='yellow', marker='*',
            edgecolors='black', linewidth=1.5,
            label="Current Position", zorder=10
        )
        
        # Add status text
        self.status_text = self.ax.text(
            0.02, 0.98, "",
            transform=self.ax.transAxes,
            verticalalignment='top',
            bbox=dict(
                boxstyle='round',
                facecolor='white',
                alpha=0.8
            )
        )
        
        # Set plot properties
        self.ax.set_xlim(-50, ROOM_WIDTH_CM + 50)
        self.ax.set_ylim(-50, ROOM_HEIGHT_CM + 50)
        self.ax.set_xlabel("X (cm)")
        self.ax.set_ylabel("Y (cm)")
        self.ax.set_title("UWB Position Tracking")
        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3)
        self.ax.legend(loc='upper right')
        
        plt.tight_layout()
        
    def _draw_grid(self):
        """Draw the room grid."""
        # Vertical lines
        for x in np.arange(0, ROOM_WIDTH_CM + 1, GRID_SIZE_CM):
            self.ax.axvline(
                x=x, color='gray', linestyle='-',
                linewidth=0.5, alpha=0.3
            )
            
        # Horizontal lines
        for y in np.arange(0, ROOM_HEIGHT_CM + 1, GRID_SIZE_CM):
            self.ax.axhline(
                y=y, color='gray', linestyle='-',
                linewidth=0.5, alpha=0.3
            )
            
    def _draw_anchors(self):
        """Draw the UWB anchors."""
        # Plot anchor points
        for anchor_id, pos in ANCHORS.items():
            self.ax.scatter(
                pos[0], pos[1],
                s=100, c='red', marker='s',
                label=f"Anchor {anchor_id}" if anchor_id == 0 else "",
                zorder=5
            )
            # Add anchor labels
            self.ax.text(
                pos[0], pos[1], f"A{anchor_id}",
                horizontalalignment='center',
                verticalalignment='center',
                fontweight='bold'
            )
            
    def _update_animation(self, frame):
        """Update the animation frame."""
        with self.viz_lock:
            if self.user_position is not None:
                # Update position history
                self.position_history.append(self.user_position.copy())
                self.current_position = self.user_position.copy()
                self.last_update = datetime.now()
                
                # Update trajectory
                if len(self.position_history) > 1:
                    positions = np.array(self.position_history)
                    self.trajectory_line.set_data(
                        positions[:, 0],
                        positions[:, 1]
                    )
                
                # Update current position marker
                self.current_marker.set_offsets([
                    [self.current_position[0], self.current_position[1]]
                ])
                
                # Update status text
                status = [
                    f"Connected to: {self.mqtt_config.broker}:{self.mqtt_config.port}",
                    f"Position: ({self.current_position[0]:.1f}, {self.current_position[1]:.1f}, {self.current_position[2]:.1f}) cm",
                    f"History: {len(self.position_history)} points",
                    f"Last Update: {self.last_update.strftime('%H:%M:%S')}"
                ]
                self.status_text.set_text('\n'.join(status))
            else:
                # No position data yet
                status = [
                    f"Connected to: {self.mqtt_config.broker}:{self.mqtt_config.port}",
                    "Waiting for position data...",
                    "Make sure anchors are running and connected"
                ]
                self.status_text.set_text('\n'.join(status))
                
        return self.trajectory_line, self.current_marker, self.status_text
        
    def start_visualization(self):
        """Start the visualization."""
        # Setup visualization
        self.setup_visualization()
        
        # Start animation
        self.animation = animation.FuncAnimation(
            self.fig, self._update_animation,
            interval=100,  # 10 FPS
            blit=True
        )
        
        print("\nVisualization started!")
        print("Close the plot window to exit.")
        
        # Show plot (blocking)
        plt.show()
        
    def start(self):
        """Start both server and visualization."""
        # Start base server
        super().start()
        
        # Start visualization in the main thread
        self.start_visualization()
        
    def stop(self):
        """Stop the server and visualization."""
        # Stop animation
        if self.animation:
            self.animation.event_source.stop()
            
        # Stop base server
        super().stop()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='UWB Position Visualizer')
    parser.add_argument('--broker', type=str, default='localhost',
                      help='MQTT broker IP address')
    parser.add_argument('--port', type=int, default=1884,
                      help='MQTT broker port')
    parser.add_argument('--history', type=int, default=100,
                      help='Number of historical positions to show')
    args = parser.parse_args()
    
    # Configure MQTT
    mqtt_config = MQTTConfig(
        broker=args.broker,
        port=args.port
    )
    
    print(f"\nConnecting to MQTT broker at {args.broker}:{args.port}")
    
    # Create and start visualizer
    viz = BasicVisualizer(
        mqtt_config=mqtt_config,
        window_size_seconds=1.0,
        history_length=args.history
    )
    
    try:
        viz.start()
    except KeyboardInterrupt:
        print("\nStopping visualization...")
    finally:
        viz.stop()
