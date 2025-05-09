#!/usr/bin/env python3

import sys
import os
import numpy as np
import matplotlib as mpl

# Configure matplotlib before importing pyplot
mpl.use('Agg')
mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
mpl.rcParams['mathtext.default'] = 'regular'

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

"""
You probably saw that post on ccp4bb about how we should be looking at Wilson plots before we fret about the $I/{\sigma}$ in the high-resolution shell.
I think this is excellent advice, but the problem has been that gaining access to the Wilson plot is a pain.

Usage:

python ./wilsonplot.py ./3173d_1_xds/3173d_1_truncate.log 3173d-wilson.png && preview 3173d-wilson.png


On your Mac, you can use a bash function that takes the image filename stem and the run number (e.g. wilson 3091 1).
Paste the bash function into ~/.bashrc or wherever you store your bash functions. 

wilson () {
echo "This script calls wilsonplot.py to generate a Wilson Plot using the data in the truncate.log file."
echo "It assumes that the output files are stored by run number following the convention used by autoxds."
echo "This function has to be invoked from the directory with the images."
echo "This script takes the file stem of an image filename and the run number as two arguments in that order."

if [ $# -lt 2 ]; then
   echo 1>&2 "$0: not enough arguments"
   echo "Usage: wilson 3091 1"
   return 2
elif [ $# -gt 2 ]; then
   echo 1>&2 "$0: too many arguments"
   echo "Usage: wilson 3091 1"
   return 2
fi
python ~/Scripts/SMBscripts/wilsonplot.py ./$1_$2_xds/$1_$2_truncate.log $1_$2-WilsonPlot.png && open -a preview $1_$2-WilsonPlot.png
}


You can use the bash function and the Python script on the SMB server. 
Change the file paths and replace 'open -a preview' with 'open'.
This makes it really fast to check data quality on the SMB server.


Blaine Mooers, PhD
OUHSC

May 9, 2025
"""

def parse_truncate_log(log_file):
    """Parse TRUNCATE log file to extract Wilson plot data."""
    print(f"Processing: {log_file}")
    
    # Will store extracted data
    resolution_inv_sq = []
    ln_intensity = []
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        # Look for different data section markers
        data_markers = [
            "i  nref  N_unq",
            "Range N_obs",
            "$   i   nref",
            "Wilson Plot - Suggested Bfactor"
        ]
        
        # Try to locate the data section
        in_data_section = False
        data_header_line = -1
        
        for i, line in enumerate(lines):
            # Check for data section markers
            for marker in data_markers:
                if marker in line:
                    data_header_line = i
                    break
            
            # If we found a marker, look for actual data lines
            if data_header_line > 0 and i > data_header_line:
                # Skip any remaining header lines
                if '$' in line and not in_data_section:
                    in_data_section = True
                    continue
                
                # Check if this is a data line (starts with a number)
                if in_data_section and line.strip() and line.lstrip()[0].isdigit():
                    parts = line.split()
                    
                    # Make sure we have enough columns
                    if len(parts) >= 8:
                        try:
                            # Try column 4 first (0-indexed) for 1/resol^2
                            res_idx = 4 if len(parts) > 4 else 1
                            # Try column 7 first for ln(I/Σf²)
                            ln_idx = 7 if len(parts) > 7 else 3
                            
                            res_sq = float(parts[res_idx])
                            ln_i = float(parts[ln_idx])
                            
                            resolution_inv_sq.append(res_sq)
                            ln_intensity.append(ln_i)
                        except (ValueError, IndexError):
                            continue
                
                # Check for end of data section
                if in_data_section and ('$' in line or line.strip() == ""):
                    if len(resolution_inv_sq) > 0:  # Only end if we got some data
                        break
        
        # If we didn't find data through markers, try direct parsing
        if not resolution_inv_sq:
            # Reset flags
            in_data_section = False
            
            for i, line in enumerate(lines):
                # Look for numerical data directly
                parts = line.split()
                if len(parts) >= 8 and parts[0].isdigit():
                    try:
                        # Columns 4 and 7 for 1/d² and ln(I)
                        res_sq = float(parts[4])
                        ln_i = float(parts[7])
                        
                        # Sanity check - 1/d² should be positive
                        if res_sq > 0:
                            resolution_inv_sq.append(res_sq)
                            ln_intensity.append(ln_i)
                            in_data_section = True
                    except (ValueError, IndexError):
                        continue
                # If we've started collecting data and hit a non-data line, we might be done
                elif in_data_section and len(parts) < 8:
                    break
        
        if not resolution_inv_sq:
            print("ERROR: Failed to extract Wilson plot data")
            return None, None
        
        print(f"Successfully extracted {len(resolution_inv_sq)} data points")
        return resolution_inv_sq, ln_intensity
    
    except Exception as e:
        print(f"Error processing log file: {e}")
        return None, None

def create_wilson_plot(resolution_inv_sq, ln_intensity, output_file):
    """Create a Wilson plot with dual x-axes."""
    if not resolution_inv_sq or len(resolution_inv_sq) < 2:
        print("Not enough data points for plotting")
        return False
    
    try:
        # Convert to numpy arrays
        x = np.array(resolution_inv_sq)
        y = np.array(ln_intensity)
        
        # Perform linear regression
        A = np.vstack([x, np.ones(len(x))]).T
        m, b = np.linalg.lstsq(A, y, rcond=None)[0]
        
        # Wilson B-factor = -2 * slope
        wilson_b = -2 * m
        print(f"Wilson B-factor: {wilson_b:.2f} Å²")
        
        # Calculate fit line
        fit_y = m * x + b
        
        # Create figure with a specific size
        fig = plt.figure(figsize=(8, 6))
        
        # Create the primary axis - this will show 1/d²
        ax1 = fig.add_subplot(111)
        
        # Plot data and fit line on the primary axis
        ax1.scatter(x, y, color='blue', marker='o', alpha=0.7, label='Observed')
        ax1.plot(x, fit_y, 'r-', linewidth=2, label=f'Wilson Fit (B = {wilson_b:.2f} Å²)')
        
        # Set up the primary axis (1/d²)
        ax1.set_xlabel(r'1/d² (Å$^{-2}$)')
        ax1.set_ylabel(r'ln<I/$\Sigma$f$^2$>')
        # ax1.set_title('Wilson Plot')
        
        # Add grid based on the primary axis ticks
        ax1.grid(True, alpha=0.3)
        
        # Add the legend
        ax1.legend(loc='upper right')
        
        # Create a second x-axis at the top for resolution
        ax2 = ax1.twiny()
        
        # Function to convert 1/d² to resolution in Å
        def inv_d_sq_to_resolution(x):
            # Convert 1/d² to resolution: d = sqrt(1/x)
            # But protect against division by zero
            with np.errstate(divide='ignore', invalid='ignore'):
                return np.sqrt(1.0 / np.maximum(x, 1e-10))
        
        # Function to convert resolution to 1/d²
        def resolution_to_inv_d_sq(x):
            # Convert resolution to 1/d²: x = 1/d²
            # But protect against division by zero
            with np.errstate(divide='ignore', invalid='ignore'):
                return 1.0 / np.power(np.maximum(x, 1e-10), 2)
        
        # Get the current x-limits
        x_min, x_max = ax1.get_xlim()
        
        # Calculate the corresponding resolution limits
        res_max = inv_d_sq_to_resolution(x_min)
        res_min = inv_d_sq_to_resolution(x_max)
        
        # Create common resolution tick points based on the range
        if res_min > 1.2:
            # Include lower resolution markers
            resolutions = [5.5, 3.0, 2.0, 1.5, 1.3, 1.2]
        else:
            # Focus on higher resolution markers
            resolutions = [5.5, 3.0, 2.0, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8]
        
        # Filter to include only resolutions within our range
        tick_resolutions = [r for r in resolutions if res_min <= r <= res_max]
        
        # Convert to 1/d² for tick positions
        tick_positions = [resolution_to_inv_d_sq(r) for r in tick_resolutions]
        
        # Create tick labels
        tick_labels = [f"{r:.1f}" for r in tick_resolutions]
        
        # Set ticks on the top x-axis
        ax2.set_xticks(tick_positions)
        ax2.set_xticklabels(tick_labels)
        ax2.set_xlim(ax1.get_xlim())
        
        # Set the label for the top axis
        ax2.set_xlabel('Resolution (Å)')
        
        # Adjust layout to make room for both axes
        plt.tight_layout()
        
        # Save figure
        plt.savefig(output_file, dpi=150)
        print(f"Wilson plot saved to: {output_file}")
        
        return True
    
    except Exception as e:
        print(f"Error creating plot: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python dual_axis_wilson.py <truncate_log_file> <output_image>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Parse log file
    resolution_inv_sq, ln_intensity = parse_truncate_log(log_file)
    
    # Create plot if data was extracted
    if resolution_inv_sq and ln_intensity:
        success = create_wilson_plot(resolution_inv_sq, ln_intensity, output_file)
        sys.exit(0 if success else 1)
    else:
        print("Failed to extract data from log file")
        sys.exit(1)