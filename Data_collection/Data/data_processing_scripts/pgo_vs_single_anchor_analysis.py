#!/usr/bin/env python3
"""
PGO vs Single Anchor Performance Analysis (2D - X,Y only)

This script analyzes the performance of PGO (Pose Graph Optimization) compared to 
single anchor measurements in 2D space (X,Y coordinates only, Z dimension ignored).
It calculates statistics and creates visualizations to show how much better PGO 
performs compared to using only one anchor.

Usage:
    python pgo_vs_single_anchor_analysis.py <csv_file>
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import sys
from typing import Dict, List, Tuple, Optional
import seaborn as sns
from pathlib import Path

# Set up plotting style
try:
    plt.style.use('seaborn-v0_8')
except OSError:
    try:
        plt.style.use('seaborn')
    except OSError:
        pass  # Use default style
sns.set_palette("husl")

# Anchor positions from the codebase (in cm)
ANCHOR_POSITIONS = {
    0: np.array([480, 600, 0]),
    1: np.array([0, 600, 0]), 
    2: np.array([480, 0, 0]),
    3: np.array([0, 0, 0])
}

# Anchor rotation matrices for transforming local to global coordinates
def Rz(deg: float) -> np.ndarray:
    """Rotation matrix around Z axis."""
    rad = np.radians(deg)
    c, s = np.cos(rad), np.sin(rad)
    return np.array([
        [c, -s, 0.0],
        [s, c, 0.0],
        [0.0, 0.0, 1.0]
    ], dtype=float)

def Ry(deg: float) -> np.ndarray:
    """Rotation matrix around Y axis."""
    rad = np.radians(deg)
    c, s = np.cos(rad), np.sin(rad)
    return np.array([
        [c, 0.0, s],
        [0.0, 1.0, 0.0],
        [-s, 0.0, c]
    ], dtype=float)

# Anchor transformation matrices (from codebase)
ANCHOR_R = {
    0: Rz(225.0) @ Ry(+45.0),  # top-right faces SW, tilted down
    1: Rz(315.0) @ Ry(+45.0),  # top-left faces SE, tilted down
    2: Rz(135.0) @ Ry(+45.0),  # bottom-right faces NW, tilted down
    3: Rz(45.0) @ Ry(+45.0),   # bottom-left faces NE, tilted down
}

def transform_local_to_global(anchor_id: int, local_vector: np.ndarray) -> np.ndarray:
    """Transform local anchor measurement to global coordinates."""
    return ANCHOR_R[anchor_id] @ local_vector

def calculate_single_anchor_position(anchor_id: int, local_measurements: List[np.ndarray]) -> np.ndarray:
    """
    Calculate phone position using only one anchor with proper bin averaging (2D only - X,Y coordinates).
    
    Args:
        anchor_id: ID of the anchor
        local_measurements: List of local measurements from this anchor
        
    Returns:
        Estimated phone position in global coordinates (X, Y only)
    """
    if not local_measurements:
        return np.array([np.nan, np.nan])
    
    # First: Calculate mean of local measurements (bin averaging)
    mean_local_measurement = np.mean(local_measurements, axis=0)
    
    # Then: Transform the mean to global coordinates
    mean_global_measurement = transform_local_to_global(anchor_id, mean_local_measurement)
    
    # Phone position = anchor position + mean measurement vector (only X,Y)
    anchor_pos = ANCHOR_POSITIONS[anchor_id][:2]  # Only X,Y
    phone_position = anchor_pos + mean_global_measurement[:2]  # Only X,Y
    
    return phone_position

def analyze_single_row(row) -> Dict:
    """Analyze a single row of data (2D analysis only - X,Y coordinates)."""
    # Ground truth (only X,Y)
    gt_pos = np.array([row['ground_truth_x'], row['ground_truth_y']])
    
    # PGO result (only X,Y)
    pgo_pos = np.array([row['pgo_x'], row['pgo_y']])
    
    # Parse measurement data
    filtered_data = json.loads(row['filtered_binned_data_json'])
    measurements = filtered_data['measurements']
    
    # Calculate single anchor positions for each anchor that has measurements
    single_anchor_results = {}
    single_anchor_errors = {}
    
    for anchor_id_str, local_measurements in measurements.items():
        anchor_id = int(anchor_id_str)
        if local_measurements:  # Only if we have measurements
            # Convert to numpy arrays
            local_vecs = [np.array(meas) for meas in local_measurements]
            
            # Calculate position using only this anchor (2D only)
            single_pos = calculate_single_anchor_position(anchor_id, local_vecs)
            
            if not np.any(np.isnan(single_pos)):
                single_anchor_results[anchor_id] = single_pos
                # Calculate 2D error from ground truth
                error = np.linalg.norm(single_pos - gt_pos)
                single_anchor_errors[anchor_id] = error
    
    # Find worst case (highest error) single anchor
    worst_anchor_id = None
    worst_error = 0
    worst_position = None
    
    if single_anchor_errors:
        worst_anchor_id = max(single_anchor_errors.keys(), key=lambda k: single_anchor_errors[k])
        worst_error = single_anchor_errors[worst_anchor_id]
        worst_position = single_anchor_results[worst_anchor_id]
    
    # Calculate PGO error (2D only)
    pgo_error = np.linalg.norm(pgo_pos - gt_pos)
    
    return {
        'ground_truth': gt_pos,
        'pgo_position': pgo_pos,
        'pgo_error': pgo_error,
        'orientation': row['orientation'],
        'single_anchor_results': single_anchor_results,
        'single_anchor_errors': single_anchor_errors,
        'worst_anchor_id': worst_anchor_id,
        'worst_anchor_position': worst_position,
        'worst_anchor_error': worst_error,
        'num_anchors_used': len(single_anchor_results)
    }

def create_detailed_position_table(results: List[Dict]) -> str:
    """Create detailed position-by-position analysis table in the requested format."""
    
    # Group results by ground truth position and orientation
    position_groups = {}
    for result in results:
        gt_pos = result['ground_truth']
        orientation = result['orientation']
        key = (int(gt_pos[0]), int(gt_pos[1]), orientation)
        
        if key not in position_groups:
            position_groups[key] = []
        position_groups[key].append(result)
    
    # Create the formatted table
    table_lines = []
    table_lines.append("")
    table_lines.append("=" * 120)
    table_lines.append("PGO vs SINGLE ANCHOR ACCURACY ANALYSIS RESULTS (2D - X,Y only)")
    table_lines.append("=" * 120)
    table_lines.append("Position     PGO X    PGO Y    Orient   Count  PGO Error    PGO StdErr   Worst Anchor Worst Error  Worst StdErr")
    table_lines.append("-" * 120)
    
    # Sort positions for consistent output
    sorted_positions = sorted(position_groups.keys())
    
    for pos_key in sorted_positions:
        gt_x, gt_y, orientation = pos_key
        group_results = position_groups[pos_key]
        
        if not group_results:
            continue
            
        # Calculate statistics for this position/orientation group
        pgo_errors = [r['pgo_error'] for r in group_results]
        pgo_positions = [r['pgo_position'] for r in group_results]
        worst_errors = [r['worst_anchor_error'] for r in group_results if r['worst_anchor_error'] > 0]
        worst_anchor_ids = [r['worst_anchor_id'] for r in group_results if r['worst_anchor_id'] is not None]
        
        # Calculate means
        mean_pgo_x = np.mean([pos[0] for pos in pgo_positions])
        mean_pgo_y = np.mean([pos[1] for pos in pgo_positions])
        mean_pgo_error = np.mean(pgo_errors)
        pgo_stderr = np.std(pgo_errors) / np.sqrt(len(pgo_errors)) if len(pgo_errors) > 1 else 0.0
        
        if worst_errors:
            mean_worst_error = np.mean(worst_errors)
            worst_stderr = np.std(worst_errors) / np.sqrt(len(worst_errors)) if len(worst_errors) > 1 else 0.0
            most_common_worst_anchor = max(set(worst_anchor_ids), key=worst_anchor_ids.count) if worst_anchor_ids else 0
        else:
            mean_worst_error = 0.0
            worst_stderr = 0.0
            most_common_worst_anchor = 0
        
        # Format the row
        row = f"({gt_x:6d},{gt_y:6d},{orientation}) {mean_pgo_x:6.1f}    {mean_pgo_y:6.1f}    {orientation}        {len(group_results)}      {mean_pgo_error:6.1f}        {pgo_stderr:4.1f}          {most_common_worst_anchor}            {mean_worst_error:6.1f}        {worst_stderr:4.1f}"
        table_lines.append(row)
    
    table_lines.append("=" * 120)
    table_lines.append("")
    
    return "\n".join(table_lines)

def create_summary_table(results: List[Dict]) -> pd.DataFrame:
    """Create summary statistics table."""
    summary_data = []
    
    # Group by orientation
    orientations = ['A', 'B', 'C', 'U']
    
    for orientation in orientations:
        orient_results = [r for r in results if r['orientation'] == orientation]
        if not orient_results:
            continue
            
        # PGO statistics
        pgo_errors = [r['pgo_error'] for r in orient_results]
        pgo_mean = np.mean(pgo_errors)
        pgo_std = np.std(pgo_errors)
        pgo_stderr = pgo_std / np.sqrt(len(pgo_errors))
        
        # Worst case single anchor statistics
        worst_errors = [r['worst_anchor_error'] for r in orient_results if r['worst_anchor_error'] > 0]
        if worst_errors:
            worst_mean = np.mean(worst_errors)
            worst_std = np.std(worst_errors)
            worst_stderr = worst_std / np.sqrt(len(worst_errors))
        else:
            worst_mean = worst_std = worst_stderr = np.nan
        
        summary_data.append({
            'Orientation': orientation,
            'Ground_Truth_X': 0.0,  # All measurements are at origin
            'Ground_Truth_Y': 0.0,
            'PGO_Mean_Error': pgo_mean,
            'PGO_Std_Error': pgo_std,
            'PGO_Stderr': pgo_stderr,
            'Worst_Single_Anchor_Mean_Error': worst_mean,
            'Worst_Single_Anchor_Std_Error': worst_std,
            'Worst_Single_Anchor_Stderr': worst_stderr,
            'Improvement_Factor': worst_mean / pgo_mean if pgo_mean > 0 and not np.isnan(worst_mean) else np.nan,
            'Sample_Count': len(orient_results)
        })
    
    # Overall statistics (all orientations combined)
    all_pgo_errors = [r['pgo_error'] for r in results]
    all_worst_errors = [r['worst_anchor_error'] for r in results if r['worst_anchor_error'] > 0]
    
    pgo_mean_all = np.mean(all_pgo_errors)
    pgo_std_all = np.std(all_pgo_errors)
    pgo_stderr_all = pgo_std_all / np.sqrt(len(all_pgo_errors))
    
    if all_worst_errors:
        worst_mean_all = np.mean(all_worst_errors)
        worst_std_all = np.std(all_worst_errors)
        worst_stderr_all = worst_std_all / np.sqrt(len(all_worst_errors))
    else:
        worst_mean_all = worst_std_all = worst_stderr_all = np.nan
    
    summary_data.append({
        'Orientation': 'ALL',
        'Ground_Truth_X': 0.0,
        'Ground_Truth_Y': 0.0,
        'PGO_Mean_Error': pgo_mean_all,
        'PGO_Std_Error': pgo_std_all,
        'PGO_Stderr': pgo_stderr_all,
        'Worst_Single_Anchor_Mean_Error': worst_mean_all,
        'Worst_Single_Anchor_Std_Error': worst_std_all,
        'Worst_Single_Anchor_Stderr': worst_stderr_all,
        'Improvement_Factor': worst_mean_all / pgo_mean_all if pgo_mean_all > 0 and not np.isnan(worst_mean_all) else np.nan,
        'Sample_Count': len(results)
    })
    
    return pd.DataFrame(summary_data)

def create_visualizations(results: List[Dict], output_dir: Path):
    """Create visualization plots."""
    
    # Prepare data for plotting
    orientations = []
    pgo_errors = []
    worst_single_errors = []
    
    for result in results:
        if result['worst_anchor_error'] > 0:  # Only include if we have single anchor data
            orientations.append(result['orientation'])
            pgo_errors.append(result['pgo_error'])
            worst_single_errors.append(result['worst_anchor_error'])
    
    # Create DataFrame for easier plotting
    plot_data = pd.DataFrame({
        'Orientation': orientations,
        'PGO_Error': pgo_errors,
        'Worst_Single_Anchor_Error': worst_single_errors
    })
    
    # Figure 1: Error comparison by orientation
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Box plot comparison
    plot_data_melted = pd.melt(plot_data, 
                              id_vars=['Orientation'], 
                              value_vars=['PGO_Error', 'Worst_Single_Anchor_Error'],
                              var_name='Method', 
                              value_name='Error_cm')
    
    sns.boxplot(data=plot_data_melted, x='Orientation', y='Error_cm', hue='Method', ax=ax1)
    ax1.set_title('Error Distribution by Orientation')
    ax1.set_ylabel('Error (cm)')
    ax1.legend(title='Method')
    
    # Mean error with error bars
    summary_stats = []
    for orient in ['A', 'B', 'C', 'U']:
        orient_data = plot_data[plot_data['Orientation'] == orient]
        if len(orient_data) > 0:
            pgo_mean = orient_data['PGO_Error'].mean()
            pgo_stderr = orient_data['PGO_Error'].std() / np.sqrt(len(orient_data))
            worst_mean = orient_data['Worst_Single_Anchor_Error'].mean()
            worst_stderr = orient_data['Worst_Single_Anchor_Error'].std() / np.sqrt(len(orient_data))
            
            summary_stats.append({
                'Orientation': orient,
                'PGO_Mean': pgo_mean,
                'PGO_Stderr': pgo_stderr,
                'Worst_Mean': worst_mean,
                'Worst_Stderr': worst_stderr
            })
    
    if summary_stats:
        summary_df = pd.DataFrame(summary_stats)
        x_pos = np.arange(len(summary_df))
        width = 0.35
        
        ax2.bar(x_pos - width/2, summary_df['PGO_Mean'], width, 
                yerr=summary_df['PGO_Stderr'], label='PGO', capsize=5)
        ax2.bar(x_pos + width/2, summary_df['Worst_Mean'], width,
                yerr=summary_df['Worst_Stderr'], label='Worst Single Anchor', capsize=5)
        
        ax2.set_xlabel('Orientation')
        ax2.set_ylabel('Mean Error (cm)')
        ax2.set_title('Mean Error with Standard Error')
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(summary_df['Orientation'])
        ax2.legend()
    
    plt.tight_layout()
    plt.savefig(output_dir / 'pgo_vs_single_anchor_comparison.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Figure 2: Scatter plot of PGO vs Single Anchor errors
    plt.figure(figsize=(10, 8))
    colors = {'A': 'red', 'B': 'blue', 'C': 'green', 'U': 'orange'}
    
    for orient in ['A', 'B', 'C', 'U']:
        orient_data = plot_data[plot_data['Orientation'] == orient]
        if len(orient_data) > 0:
            plt.scatter(orient_data['PGO_Error'], orient_data['Worst_Single_Anchor_Error'], 
                       c=colors[orient], label=f'Orientation {orient}', alpha=0.7, s=50)
    
    # Add diagonal line (y=x) for reference
    max_error = max(plot_data['PGO_Error'].max(), plot_data['Worst_Single_Anchor_Error'].max())
    plt.plot([0, max_error], [0, max_error], 'k--', alpha=0.5, label='Equal Error Line')
    
    plt.xlabel('PGO Error (cm)')
    plt.ylabel('Worst Single Anchor Error (cm)')
    plt.title('PGO vs Single Anchor Error Comparison')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(output_dir / 'pgo_vs_single_anchor_scatter.png', dpi=300, bbox_inches='tight')
    plt.show()

def main():
    if len(sys.argv) != 2:
        print("Usage: python pgo_vs_single_anchor_analysis.py <csv_file>")
        sys.exit(1)
    
    csv_file = Path(sys.argv[1])
    if not csv_file.exists():
        print(f"Error: File {csv_file} does not exist")
        sys.exit(1)
    
    # Create output directory
    output_dir = csv_file.parent
    
    print(f"Loading data from {csv_file}...")
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} data points")
    
    # Analyze each row
    print("Analyzing data...")
    results = []
    for _, row in df.iterrows():
        try:
            result = analyze_single_row(row)
            results.append(result)
        except Exception as e:
            print(f"Error processing row: {e}")
            continue
    
    print(f"Successfully analyzed {len(results)} data points")
    
    # Create detailed position table
    print("Creating detailed position table...")
    detailed_table = create_detailed_position_table(results)
    
    # Save detailed table
    detailed_file = output_dir / 'pgo_vs_single_anchor_detailed_table.txt'
    with open(detailed_file, 'w') as f:
        f.write(detailed_table)
    print(f"Detailed table saved to {detailed_file}")
    
    # Display detailed table
    print(detailed_table)
    
    # Create summary table
    print("Creating summary table...")
    summary_df = create_summary_table(results)
    
    # Save summary table
    summary_file = output_dir / 'pgo_vs_single_anchor_summary.csv'
    summary_df.to_csv(summary_file, index=False)
    print(f"Summary table saved to {summary_file}")
    
    # Display summary table
    print("\n" + "="*80)
    print("SUMMARY TABLE")
    print("="*80)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.float_format', '{:.2f}'.format)
    print(summary_df.to_string(index=False))
    
    # Create visualizations
    print("\nCreating visualizations...")
    create_visualizations(results, output_dir)
    
    print(f"\nAnalysis complete! Results saved to {output_dir}")
    
    # Print key insights
    print("\n" + "="*80)
    print("KEY INSIGHTS")
    print("="*80)
    
    overall_row = summary_df[summary_df['Orientation'] == 'ALL'].iloc[0]
    pgo_mean = overall_row['PGO_Mean_Error']
    worst_mean = overall_row['Worst_Single_Anchor_Mean_Error']
    improvement = overall_row['Improvement_Factor']
    
    print(f"Overall PGO Mean Error: {pgo_mean:.2f} ± {overall_row['PGO_Stderr']:.2f} cm")
    print(f"Overall Worst Single Anchor Mean Error: {worst_mean:.2f} ± {overall_row['Worst_Single_Anchor_Stderr']:.2f} cm")
    print(f"Improvement Factor: {improvement:.2f}x")
    print(f"PGO reduces error by {((worst_mean - pgo_mean) / worst_mean * 100):.1f}%")

if __name__ == "__main__":
    main()
