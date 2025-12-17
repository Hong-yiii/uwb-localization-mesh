#!/usr/bin/env python3
"""
God Plot Generator V5 for UWB Localization System

Correct implementation using measurement masking approach:
- Takes filtered_binned_data from CSV for each measurement
- Masks the measurements to create 1, 2, 3, 4 anchor combinations
- Always provides all 4 anchor positions to PGO
- Finds worst-case combinations for each anchor count
- Shows progression from worst 1-anchor to best 4-anchor performance

Requirements from god_plot_requirements.md:
1. Visualize accuracy against ground truth (avg of pgo_x, pgo_y)
2. Show different orientations (A, B, C, U) in separate plots  
3. Show effect of anchor count (1-4 anchors, WORST CASE selection via masking)
4. Show accuracy across 4 measured positions
5. Use crosshair error bars (SD_x, SD_y) from multiple PGO estimates
6. Ignore Z readings, work in 2D only
7. Transform local measurements to global coordinates using filtered_binned_data
"""

import csv
import json
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Optional
from itertools import combinations
from collections import defaultdict
import sys
import os

# Add packages to path
sys.path.append('/Users/hongyilin/projects/uwb-localization-mesh/packages')
sys.path.append('/Users/hongyilin/projects/uwb-localization-mesh')

from packages.datatypes.datatypes import AnchorConfig
from packages.localization_algos.edge_creation.transforms import create_relative_measurement
from packages.localization_algos.edge_creation.anchor_edges import create_anchor_anchor_edges
from packages.localization_algos.pgo.solver import PGOSolver

# Default anchor positions (from datatypes README)
DEFAULT_ANCHOR_POSITIONS = {
    0: np.array([480, 600, 0]),  # top-right
    1: np.array([0, 600, 0]),    # top-left  
    2: np.array([480, 0, 0]),    # bottom-right
    3: np.array([0, 0, 0])       # bottom-left
}

def load_data(csv_path: str) -> List[Dict]:
    """Load and parse the CSV data."""
    data = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Parse the filtered_binned_data_json
                filtered_data = json.loads(row['filtered_binned_data_json'])
                row['filtered_data'] = filtered_data
                
                # Parse numeric fields
                row['ground_truth_x'] = float(row['ground_truth_x'])
                row['ground_truth_y'] = float(row['ground_truth_y'])
                row['ground_truth_z'] = float(row['ground_truth_z'])
                row['pgo_x'] = float(row['pgo_x'])
                row['pgo_y'] = float(row['pgo_y'])
                row['pgo_z'] = float(row['pgo_z'])
                
                data.append(row)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Warning: Skipping row due to parsing error: {e}")
                continue
    return data

def mask_measurements(measurements: Dict[str, List[List[float]]], 
                     selected_anchors: List[int]) -> Dict[str, List[List[float]]]:
    """Mask measurements to only include selected anchors."""
    masked = {}
    for anchor_id in selected_anchors:
        anchor_key = str(anchor_id)
        if anchor_key in measurements:
            masked[anchor_key] = measurements[anchor_key]
    return masked

def transform_measurements_to_global(measurements: Dict[str, List[List[float]]], 
                                   phone_node_id: int = 0) -> List[Tuple[str, str, np.ndarray]]:
    """Transform local measurements to global coordinates and create edges."""
    edges = []
    
    for anchor_id_str, vectors in measurements.items():
        anchor_id = int(anchor_id_str)
        for vector in vectors:
            # Convert to numpy array and transform to global coordinates
            local_vector = np.array(vector)
            try:
                from_node, to_node, global_vector = create_relative_measurement(
                    anchor_id, phone_node_id, local_vector
                )
                edges.append((from_node, to_node, global_vector))
            except ValueError as e:
                # Skip invalid measurements
                continue
    
    return edges

def run_pgo_with_masked_measurements(measurements: Dict[str, List[List[float]]], 
                                   selected_anchors: List[int]) -> Optional[np.ndarray]:
    """Run PGO with measurements masked to selected anchors."""
    
    # Mask measurements to only include selected anchors
    masked_measurements = mask_measurements(measurements, selected_anchors)
    
    if not masked_measurements:
        return None
    
    # Transform measurements to global coordinates
    edges = transform_measurements_to_global(masked_measurements)
    
    if not edges:
        return None
    
    # Create anchor config for ALL anchors (positions always available)
    anchor_config = AnchorConfig(positions=DEFAULT_ANCHOR_POSITIONS)
    
    # Add anchor-anchor edges for ALL anchors
    anchor_edges = create_anchor_anchor_edges(anchor_config)
    all_edges = edges + anchor_edges
    
    # Set up nodes (ALL anchors are fixed, phone is unknown)
    nodes = {}
    for anchor_id in DEFAULT_ANCHOR_POSITIONS.keys():
        nodes[f'anchor_{anchor_id}'] = DEFAULT_ANCHOR_POSITIONS[anchor_id]
    nodes['phone_0'] = None  # Unknown position
    
    # Run PGO
    solver = PGOSolver()
    try:
        result = solver.solve(nodes, all_edges, DEFAULT_ANCHOR_POSITIONS)
        if result.success and 'phone_0' in result.node_positions:
            return result.node_positions['phone_0'][:2]  # Return only x, y (ignore z)
    except Exception as e:
        # PGO failed
        pass
    
    return None

def estimate_positions_single_anchor(measurements: Dict[str, List[List[float]]], 
                                   anchor_id: int,
                                   ground_truth: Tuple[float, float]) -> List[np.ndarray]:
    """
    Estimate position using a single anchor with bin averaging.
    For 1-anchor case, we first take the average of filtered measurements in the bin,
    then transform to global coordinates and use the actual measured position.
    This matches the approach used for multi-anchor PGO cases.
    """
    anchor_id_str = str(anchor_id)
    if anchor_id_str not in measurements:
        return []
    
    vectors = measurements[anchor_id_str]
    if not vectors:
        return []
    
    # First: Calculate the mean of the bin in local coordinates (same as multi-anchor approach)
    local_mean = np.mean(vectors, axis=0)
    
    # Then: Transform the bin mean to global coordinates
    try:
        _, _, global_mean_vector = create_relative_measurement(anchor_id, 0, local_mean)
    except ValueError:
        return []
    
    # Use actual measured position (anchor position + measurement vector)
    anchor_pos_2d = DEFAULT_ANCHOR_POSITIONS[anchor_id][:2]
    
    # Create single position estimate using the bin mean
    estimated_pos = anchor_pos_2d + global_mean_vector[:2]  # Only use x,y components
    
    # Return as single-element list to maintain consistency with function signature
    return [estimated_pos]

def find_worst_case_combinations_with_masking(data_group: List[Dict], 
                                            ground_truth: Tuple[float, float]) -> Dict[int, List[int]]:
    """Find worst-case anchor combinations using measurement masking."""
    
    # Get all available anchors from the data
    all_available_anchors = set()
    for row in data_group:
        available_anchors = list(map(int, row['filtered_data']['measurements'].keys()))
        all_available_anchors.update(available_anchors)
    
    all_anchor_ids = sorted(list(all_available_anchors))
    print(f"    Available anchors for this position: {all_anchor_ids}")
    
    worst_combinations = {}
    
    # Handle 1 anchor case separately (simple distance-based estimation)
    if len(all_anchor_ids) >= 1:
        worst_distance_1 = -1
        worst_anchor_1 = None
        
        for anchor_id in all_anchor_ids:
            distances = []
            for row in data_group:
                available_anchors = list(map(int, row['filtered_data']['measurements'].keys()))
                if anchor_id not in available_anchors:
                    continue
                
                pos_estimates = estimate_positions_single_anchor(
                    row['filtered_data']['measurements'], 
                    anchor_id, 
                    ground_truth
                )
                
                for pos_estimate in pos_estimates:
                    distance = np.sqrt((pos_estimate[0] - ground_truth[0])**2 + 
                                     (pos_estimate[1] - ground_truth[1])**2)
                    distances.append(distance)
            
            if distances:
                avg_distance = np.mean(distances)
                if avg_distance > worst_distance_1:
                    worst_distance_1 = avg_distance
                    worst_anchor_1 = anchor_id
        
        if worst_anchor_1 is not None:
            worst_combinations[1] = [worst_anchor_1]
            print(f"    1 anchor - worst case: [{worst_anchor_1}] (avg error: {worst_distance_1:.1f}cm)")
    
    # Handle 2-4 anchor cases with PGO and masking
    for num_anchors in range(2, 5):
        if num_anchors > len(all_anchor_ids):
            continue
            
        worst_distance = -1
        worst_combination = None
        
        # Test all combinations of num_anchors
        for anchor_combination in combinations(all_anchor_ids, num_anchors):
            anchor_combination = list(anchor_combination)
            
            # Run PGO for all measurements in this group with this anchor combination
            distances = []
            successful_runs = 0
            
            for row in data_group:
                # Check if this row has measurements from all required anchors
                available_anchors = list(map(int, row['filtered_data']['measurements'].keys()))
                if not all(anchor_id in available_anchors for anchor_id in anchor_combination):
                    continue
                
                # Run PGO with masked measurements
                pgo_result = run_pgo_with_masked_measurements(
                    row['filtered_data']['measurements'], 
                    anchor_combination
                )
                
                if pgo_result is not None:
                    # Calculate distance from ground truth (ignore z)
                    distance = np.sqrt((pgo_result[0] - ground_truth[0])**2 + 
                                     (pgo_result[1] - ground_truth[1])**2)
                    distances.append(distance)
                    successful_runs += 1
            
            if distances:
                avg_distance = np.mean(distances)
                # For worst case selection: choose the combination with highest average error
                if avg_distance > worst_distance:
                    worst_distance = avg_distance
                    worst_combination = anchor_combination
        
        if worst_combination is not None:
            worst_combinations[num_anchors] = worst_combination
            print(f"    {num_anchors} anchors - worst case: {worst_combination} (avg error: {worst_distance:.1f}cm)")
        else:
            print(f"    Warning: No valid combination found for {num_anchors} anchors")
    
    return worst_combinations

def calculate_position_statistics_with_masking(data_group: List[Dict], 
                                             anchor_combinations: Dict[int, List[int]],
                                             ground_truth: Tuple[float, float]) -> Dict[int, Tuple[float, float, float, float]]:
    """Calculate position statistics for each anchor combination using masking."""
    
    statistics = {}
    
    for num_anchors, anchor_ids in anchor_combinations.items():
        positions = []
        
        if num_anchors == 1:
            # Handle single anchor case
            anchor_id = anchor_ids[0]
            for row in data_group:
                available_anchors = list(map(int, row['filtered_data']['measurements'].keys()))
                if anchor_id not in available_anchors:
                    continue
                
                pos_estimates = estimate_positions_single_anchor(
                    row['filtered_data']['measurements'], 
                    anchor_id, 
                    ground_truth
                )
                
                positions.extend(pos_estimates)
        else:
            # Handle multi-anchor case with PGO and masking
            for row in data_group:
                # Check if this row has measurements from all required anchors
                available_anchors = list(map(int, row['filtered_data']['measurements'].keys()))
                if not all(anchor_id in available_anchors for anchor_id in anchor_ids):
                    continue
                    
                # Run PGO with masked measurements
                pgo_result = run_pgo_with_masked_measurements(
                    row['filtered_data']['measurements'], 
                    anchor_ids
                )
                
                if pgo_result is not None:
                    positions.append(pgo_result)
        
        if positions:
            positions_array = np.array(positions)
            mean_x = np.mean(positions_array[:, 0])
            mean_y = np.mean(positions_array[:, 1])
            std_x = np.std(positions_array[:, 0])
            std_y = np.std(positions_array[:, 1])
            
            statistics[num_anchors] = (mean_x, mean_y, std_x, std_y)
            print(f"    {num_anchors} anchors: {len(positions)} successful position estimates")
        else:
            print(f"    Warning: No valid position estimates for {num_anchors} anchors")
    
    return statistics

def create_god_plot_v5(orientation: str, data: List[Dict], output_dir: str):
    """Create a god plot for a specific orientation with proper measurement masking."""
    
    # Group data by ground truth position
    position_groups = defaultdict(list)
    for row in data:
        if row['orientation'] == orientation:
            pos_key = (row['ground_truth_x'], row['ground_truth_y'])
            position_groups[pos_key].append(row)
    
    if not position_groups:
        print(f"Warning: No data found for orientation {orientation}")
        return
    
    print(f"\nProcessing orientation {orientation}:")
    print(f"Found {len(position_groups)} positions: {list(position_groups.keys())}")
    
    # Set up the plot
    fig, ax = plt.subplots(figsize=(18, 14))
    
    # Plot anchor positions
    for anchor_id, pos in DEFAULT_ANCHOR_POSITIONS.items():
        ax.plot(pos[0], pos[1], 's', markersize=15, color='red', 
                label='Anchor' if anchor_id == 0 else '', zorder=10)
        ax.annotate(f'A{anchor_id}', (pos[0], pos[1]), xytext=(8, 8), 
                   textcoords='offset points', fontsize=12, color='red', 
                   fontweight='bold', zorder=11)
    
    # Colors for different anchor counts (worst to best) - Red to Green progression
    # Darker colors for error bars (better visibility)
    plot_colors = {1: '#FF1A1A', 2: '#FF6600', 3: '#FFCC00', 4: '#00CC44'}
    # Pastel colors for labels (softer, less intrusive)
    label_colors = {1: '#FFB3B3', 2: '#FFD1A3', 3: '#FFF4A3', 4: '#A3E6A3'}
    # Use same marker for all anchor counts for consistency
    marker = 'o'
    
    # Process each position
    position_data = {}
    for pos_key, data_group in position_groups.items():
        ground_truth = pos_key
        
        print(f"\n  Processing position {ground_truth}:")
        
        # Plot ground truth position (smaller size)
        ax.plot(ground_truth[0], ground_truth[1], 'ko', markersize=8, 
                label='Ground Truth' if pos_key == list(position_groups.keys())[0] else '',
                zorder=8)
        ax.annotate(f'GT({ground_truth[0]:.0f},{ground_truth[1]:.0f})', 
                   (ground_truth[0], ground_truth[1]), xytext=(10, -20), 
                   textcoords='offset points', fontsize=11, 
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9),
                   zorder=9)
        
        # Find worst-case anchor combinations using masking
        worst_combinations = find_worst_case_combinations_with_masking(data_group, ground_truth)
        
        # Calculate statistics for each anchor combination
        statistics = calculate_position_statistics_with_masking(data_group, worst_combinations, ground_truth)
        position_data[pos_key] = {'combinations': worst_combinations, 'statistics': statistics}
        
        # Plot position estimates with error bars for each anchor count
        for num_anchors in sorted(statistics.keys()):
            stats = statistics[num_anchors]
            mean_x, mean_y, std_x, std_y = stats
            
            plot_color = plot_colors.get(num_anchors, 'gray')
            label_color = label_colors.get(num_anchors, 'gray')
            
            # Plot crosshair error bars only (no center marker to avoid clutter)
            ax.errorbar(mean_x, mean_y, xerr=std_x, yerr=std_y, 
                       fmt='none',  # No center marker
                       color=plot_color, 
                       capsize=4, capthick=1, elinewidth=0.8,  # Thinner lines
                       label=f'{num_anchors} Anchor{"s" if num_anchors > 1 else ""} (Worst Case)' 
                             if pos_key == list(position_groups.keys())[0] else '',
                       zorder=7)
            
            # Calculate distance error for annotation
            distance_error = np.sqrt((mean_x - ground_truth[0])**2 + (mean_y - ground_truth[1])**2)
            
            # Add text annotation with anchor combination and error
            # Use different offsets for different anchor counts to avoid collisions
            offsets = {1: (20, 20), 2: (-60, 20), 3: (20, -40), 4: (-60, -40)}
            offset_x, offset_y = offsets.get(num_anchors, (15, 15))
            
            anchor_text = f"Err: {distance_error:.1f}cm"
            ax.annotate(anchor_text, (mean_x, mean_y), 
                       xytext=(offset_x, offset_y), textcoords='offset points', fontsize=8, 
                       bbox=dict(boxstyle='round,pad=0.3', facecolor=label_color, alpha=0.8),
                       zorder=6)
    
    # Add summary statistics text
    summary_text = f"Orientation {orientation} - Worst Case Analysis (Realistic Measurements):\n"
    
    for num_anchors in sorted(plot_colors.keys()):
        anchor_errors = []
        
        for pos_key in position_groups.keys():
            if pos_key in position_data and num_anchors in position_data[pos_key]['statistics']:
                stats = position_data[pos_key]['statistics'][num_anchors]
                mean_x, mean_y, std_x, std_y = stats
                distance_error = np.sqrt((mean_x - pos_key[0])**2 + (mean_y - pos_key[1])**2)
                anchor_errors.append(distance_error)
        
        if anchor_errors:
            avg_error = np.mean(anchor_errors)
            std_error = np.std(anchor_errors)
            summary_text += f"{num_anchors} Anchors: {avg_error:.1f}±{std_error:.1f}cm avg error\n"
    
    # Add summary text box
    ax.text(0.02, 0.98, summary_text, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', 
            facecolor='lightgray', alpha=0.9))
    
    # Formatting
    ax.set_xlabel('X Position (cm)', fontsize=14)
    ax.set_ylabel('Y Position (cm)', fontsize=14)
    ax.set_title(f'God Plot - Orientation {orientation}\n'
                f'PGO Accuracy vs Ground Truth (Realistic Measurements, Worst Case Selection)', fontsize=16)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right', fontsize=12)
    
    # Set equal aspect ratio and adjust limits
    ax.set_aspect('equal')
    
    # Set fixed plot limits to provide more space and prevent legend overlap
    ax.set_xlim(-100, 700)
    ax.set_ylim(-100, 700)
    
    # Save plot
    output_path = os.path.join(output_dir, f'god_plot_v5_orientation_{orientation}.png')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"\nSaved god plot v5 for orientation {orientation} to {output_path}")

def create_detailed_comparison_table(data: List[Dict], output_dir: str):
    """Create detailed PGO vs Single Anchor comparison table matching the format from pgo_vs_single_anchor_analysis.py"""
    
    # Group data by ground truth position and orientation
    position_groups = defaultdict(list)
    for row in data:
        pos_key = (row['ground_truth_x'], row['ground_truth_y'], row['orientation'])
        position_groups[pos_key].append(row)
    
    # Collect results for each position/orientation group
    table_results = []
    
    for pos_key, data_group in position_groups.items():
        ground_truth_x, ground_truth_y, orientation = pos_key
        ground_truth = (ground_truth_x, ground_truth_y)
        
        # Get PGO results (from CSV)
        pgo_positions = []
        pgo_errors = []
        for row in data_group:
            pgo_pos = np.array([row['pgo_x'], row['pgo_y']])
            pgo_positions.append(pgo_pos)
            gt_pos = np.array([ground_truth_x, ground_truth_y])
            pgo_error = np.linalg.norm(pgo_pos - gt_pos)
            pgo_errors.append(pgo_error)
        
        # Find worst-case single anchor combinations
        worst_combinations = find_worst_case_combinations_with_masking(data_group, ground_truth)
        
        # Get single anchor results (worst case for 1 anchor)
        worst_anchor_errors = []
        worst_anchor_id = None
        
        if 1 in worst_combinations:
            worst_anchor_id = worst_combinations[1][0]
            
            for row in data_group:
                available_anchors = list(map(int, row['filtered_data']['measurements'].keys()))
                if worst_anchor_id not in available_anchors:
                    continue
                
                pos_estimates = estimate_positions_single_anchor(
                    row['filtered_data']['measurements'], 
                    worst_anchor_id, 
                    ground_truth
                )
                
                for pos_estimate in pos_estimates:
                    error = np.sqrt((pos_estimate[0] - ground_truth_x)**2 + 
                                  (pos_estimate[1] - ground_truth_y)**2)
                    worst_anchor_errors.append(error)
        
        # Calculate statistics
        mean_pgo_x = np.mean([pos[0] for pos in pgo_positions])
        mean_pgo_y = np.mean([pos[1] for pos in pgo_positions])
        mean_pgo_error = np.mean(pgo_errors)
        pgo_stderr = np.std(pgo_errors) / np.sqrt(len(pgo_errors)) if len(pgo_errors) > 1 else 0.0
        
        if worst_anchor_errors:
            mean_worst_error = np.mean(worst_anchor_errors)
            worst_stderr = np.std(worst_anchor_errors) / np.sqrt(len(worst_anchor_errors)) if len(worst_anchor_errors) > 1 else 0.0
        else:
            mean_worst_error = 0.0
            worst_stderr = 0.0
            worst_anchor_id = 0
        
        table_results.append({
            'ground_truth_x': int(ground_truth_x),
            'ground_truth_y': int(ground_truth_y),
            'orientation': orientation,
            'count': len(data_group),
            'mean_pgo_x': mean_pgo_x,
            'mean_pgo_y': mean_pgo_y,
            'mean_pgo_error': mean_pgo_error,
            'pgo_stderr': pgo_stderr,
            'worst_anchor_id': worst_anchor_id if worst_anchor_id is not None else 0,
            'mean_worst_error': mean_worst_error,
            'worst_stderr': worst_stderr
        })
    
    # Sort results for consistent output
    table_results.sort(key=lambda x: (x['ground_truth_x'], x['ground_truth_y'], x['orientation']))
    
    # Create the formatted table
    table_lines = []
    table_lines.append("")
    table_lines.append("=" * 120)
    table_lines.append("PGO vs SINGLE ANCHOR ACCURACY ANALYSIS RESULTS (2D - X,Y only)")
    table_lines.append("Generated from God Plot Script with Realistic Bin Averaging")
    table_lines.append("=" * 120)
    table_lines.append("Position     PGO X    PGO Y    Orient   Count  PGO Error    PGO StdErr   Worst Anchor Worst Error  Worst StdErr")
    table_lines.append("-" * 120)
    
    for result in table_results:
        row = f"({result['ground_truth_x']:6d},{result['ground_truth_y']:6d},{result['orientation']}) {result['mean_pgo_x']:6.1f}    {result['mean_pgo_y']:6.1f}    {result['orientation']}        {result['count']}      {result['mean_pgo_error']:6.1f}        {result['pgo_stderr']:4.1f}          {result['worst_anchor_id']}            {result['mean_worst_error']:6.1f}        {result['worst_stderr']:4.1f}"
        table_lines.append(row)
    
    table_lines.append("=" * 120)
    table_lines.append("")
    
    # Save table
    table_content = "\n".join(table_lines)
    output_path = os.path.join(output_dir, 'pgo_vs_single_anchor_detailed_table_from_godplot.txt')
    with open(output_path, 'w') as f:
        f.write(table_content)
    
    print(f"Detailed comparison table saved to {output_path}")
    print(table_content)
    
    return table_content

def main():
    """Main function to generate all god plots with proper measurement masking."""
    
    # Paths
    csv_path = '/Users/hongyilin/projects/uwb-localization-mesh/Data_collection/Data/28oct/datapoints28oct.csv'
    output_dir = '/Users/hongyilin/projects/uwb-localization-mesh/Data_collection/Data/28oct/god_plots'
    
    print("Loading data...")
    data = load_data(csv_path)
    print(f"Loaded {len(data)} data points")
    
    # Get unique orientations
    orientations = sorted(set(row['orientation'] for row in data))
    print(f"Found orientations: {orientations}")
    
    # Generate god plot for each orientation
    for orientation in orientations:
        print(f"\n{'='*60}")
        print(f"Generating god plot v5 for orientation {orientation}...")
        print(f"{'='*60}")
        create_god_plot_v5(orientation, data, output_dir)
    
    print(f"\n{'='*60}")
    print(f"All god plots v5 generated successfully in {output_dir}")
    print(f"{'='*60}")
    
    # Generate detailed comparison table
    print(f"\n{'='*60}")
    print(f"Generating detailed comparison table...")
    print(f"{'='*60}")
    create_detailed_comparison_table(data, output_dir)

if __name__ == "__main__":
    main()
