#!/usr/bin/env python3
"""
Script to visualize measurements from all 4 anchors for a specific position.
Shows raw measurements without PGO processing.
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, List, Tuple
import sys

# Make `packages/` importable
sys.path.append(str(Path(__file__).parent.parent.parent.parent / 'packages'))

from localization_algos.edge_creation.transforms import create_relative_measurement

def get_default_anchor_positions() -> Dict[int, np.ndarray]:
    """Ground-truth anchor positions (cm) in room frame."""
    return {
        0: np.array([480.0, 600.0, 0.0]),  # top-right
        1: np.array([0.0,   600.0, 0.0]),  # top-left
        2: np.array([480.0,   0.0, 0.0]),  # bottom-right
        3: np.array([0.0,     0.0, 0.0]),  # bottom-left
    }

def load_data_for_position(csv_path: str, target_x: float, target_y: float, orientation: str) -> List[Dict]:
    """Load data for a specific ground truth position and orientation."""
    df = pd.read_csv(csv_path)
    
    # Filter for the specific position and orientation
    filtered_df = df[
        (df['ground_truth_x'] == target_x) & 
        (df['ground_truth_y'] == target_y) & 
        (df['orientation'] == orientation)
    ]
    
    return filtered_df.to_dict('records')

def extract_measurements(row: Dict) -> Dict[int, List[np.ndarray]]:
    """Extract measurements from filtered_binned_data_json."""
    binned_data_str = row['filtered_binned_data_json']
    binned_data = json.loads(binned_data_str)
    
    measurements = {}
    for anchor_id_str, vectors in binned_data['measurements'].items():
        anchor_id = int(anchor_id_str)
        measurements[anchor_id] = [np.array(vec) for vec in vectors]
    
    return measurements

def transform_to_global(measurements: Dict[int, List[np.ndarray]], phone_node_id: int = 0) -> Dict[int, np.ndarray]:
    """Transform local measurements to global coordinates and return bin means."""
    global_bin_means = {}
    
    for anchor_id, vectors in measurements.items():
        if not vectors:
            continue
            
        # Calculate mean of the bin first (in local coordinates)
        local_mean = np.mean(vectors, axis=0)
        
        # Transform the bin mean to global coordinates
        _, _, global_mean = create_relative_measurement(anchor_id, phone_node_id, local_mean)
        global_bin_means[anchor_id] = global_mean
    
    return global_bin_means

def visualize_measurements(
    anchor_positions: Dict[int, np.ndarray],
    bin_means: Dict[int, List[np.ndarray]],  # Now contains bin means for each data row
    ground_truth_pos: Tuple[float, float],
    orientation: str,
    output_path: str
):
    """Create visualization showing anchor positions and measurements."""
    
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    
    # Plot anchor positions
    anchor_colors = ['red', 'blue', 'green', 'orange']
    anchor_markers = ['s', '^', 'D', 'o']
    
    for anchor_id, pos in anchor_positions.items():
        ax.scatter(pos[0], pos[1], 
                  c=anchor_colors[anchor_id], 
                  marker=anchor_markers[anchor_id], 
                  s=200, 
                  label=f'Anchor {anchor_id}',
                  edgecolors='black',
                  linewidth=2,
                  zorder=5)
    
    # Plot ground truth position
    ax.scatter(ground_truth_pos[0], ground_truth_pos[1], 
              c='black', marker='*', s=300, 
              label='Ground Truth (240,0)',
              edgecolors='white',
              linewidth=2,
              zorder=6)
    
    # Plot bin means from each anchor
    for anchor_id, bin_mean_vectors in bin_means.items():
        anchor_pos = anchor_positions[anchor_id]
        color = anchor_colors[anchor_id]
        
        # Plot each bin mean as an estimated position
        estimated_positions = []
        for bin_mean_vec in bin_mean_vectors:
            # The measurement vector points from anchor to phone
            estimated_pos = anchor_pos + bin_mean_vec
            estimated_positions.append(estimated_pos)
            
            # Plot bin mean measurement
            ax.scatter(estimated_pos[0], estimated_pos[1], 
                      c=color, alpha=0.7, s=60, 
                      label=f'Anchor {anchor_id} Bin Mean' if len(estimated_positions) == 1 else "",
                      zorder=3)
        
        # Calculate and plot overall mean position for this anchor (mean of bin means)
        if estimated_positions:
            overall_mean_pos = np.mean(estimated_positions, axis=0)
            ax.scatter(overall_mean_pos[0], overall_mean_pos[1], 
                      c=color, marker='x', s=150, 
                      label=f'Anchor {anchor_id} Overall Mean',
                      linewidth=4,
                      zorder=4)
    
    # Formatting
    ax.set_xlabel('X Position (cm)', fontsize=12)
    ax.set_ylabel('Y Position (cm)', fontsize=12)
    ax.set_title(f'UWB Bin Means for Position (240,0) - Orientation {orientation}\n'
                f'Bin means from all 4 anchors (no PGO)', fontsize=14, fontweight='bold')
    
    # Set equal aspect ratio and reasonable limits
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    # Add room boundaries
    room_width, room_height = 480, 600
    ax.plot([0, room_width, room_width, 0, 0], 
           [0, 0, room_height, room_height, 0], 
           'k--', alpha=0.5, linewidth=2, label='Room Boundary')
    
    # Set limits with some padding
    padding = 50
    ax.set_xlim(-padding, room_width + padding)
    ax.set_ylim(-padding, room_height + padding)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Visualization saved to: {output_path}")

def print_measurement_statistics(bin_means: Dict[int, List[np.ndarray]], ground_truth_pos: Tuple[float, float]):
    """Print statistics about the bin means."""
    print(f"\nBin Mean Statistics for Ground Truth Position {ground_truth_pos}:")
    print("=" * 60)
    
    anchor_positions = get_default_anchor_positions()
    
    for anchor_id, bin_mean_vectors in bin_means.items():
        if not bin_mean_vectors:
            continue
            
        anchor_pos = anchor_positions[anchor_id]
        estimated_positions = [anchor_pos + vec for vec in bin_mean_vectors]
        
        # Calculate statistics
        mean_pos = np.mean(estimated_positions, axis=0)
        std_pos = np.std(estimated_positions, axis=0)
        
        # Distance from ground truth
        gt_pos = np.array([ground_truth_pos[0], ground_truth_pos[1], 0])
        mean_error = np.linalg.norm(mean_pos - gt_pos)
        
        print(f"\nAnchor {anchor_id}:")
        print(f"  Number of bins: {len(bin_mean_vectors)}")
        print(f"  Mean estimated position: ({mean_pos[0]:.1f}, {mean_pos[1]:.1f}, {mean_pos[2]:.1f})")
        print(f"  Standard deviation: ({std_pos[0]:.1f}, {std_pos[1]:.1f}, {std_pos[2]:.1f})")
        print(f"  Error from ground truth: {mean_error:.1f} cm")

def main():
    # Configuration
    csv_path = "/Users/hongyilin/projects/uwb-localization-mesh/Data_collection/Data/28oct/datapoints28oct.csv"
    target_x, target_y = 240.0, 0.0
    orientation = "A"
    output_dir = Path("/Users/hongyilin/projects/uwb-localization-mesh/Data_collection/Data/28oct/god_plots")
    output_path = output_dir / f"anchor_measurements_position_{int(target_x)}_{int(target_y)}_orientation_{orientation}.png"
    
    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)
    
    # Load data
    print(f"Loading data for position ({target_x}, {target_y}) orientation {orientation}...")
    data_rows = load_data_for_position(csv_path, target_x, target_y, orientation)
    
    if not data_rows:
        print(f"No data found for position ({target_x}, {target_y}) orientation {orientation}")
        return
    
    print(f"Found {len(data_rows)} data rows")
    
    # Get anchor positions
    anchor_positions = get_default_anchor_positions()
    
    # Collect bin means from all rows
    all_bin_means = {}
    for row in data_rows:
        measurements = extract_measurements(row)
        global_bin_means = transform_to_global(measurements)  # Now returns bin means
        
        # Combine with existing bin means
        for anchor_id, bin_mean_vec in global_bin_means.items():
            if anchor_id not in all_bin_means:
                all_bin_means[anchor_id] = []
            all_bin_means[anchor_id].append(bin_mean_vec)
    
    # Print statistics
    print_measurement_statistics(all_bin_means, (target_x, target_y))
    
    # Create visualization
    print(f"\nCreating visualization...")
    visualize_measurements(
        anchor_positions=anchor_positions,
        bin_means=all_bin_means,
        ground_truth_pos=(target_x, target_y),
        orientation=orientation,
        output_path=str(output_path)
    )

if __name__ == "__main__":
    main()
