import numpy as np
import matplotlib.pyplot as plt
import os

# --- Configuration ---
# File paths for the data you have created
REAL_DATA_PATH = 'processed_ecg_data.npz'
SYNTHETIC_DATA_PATH = 'synthetic_ecg_data_vae.npz'

# Number of sample heartbeats to plot
N_SAMPLES_TO_PLOT = 5
# --- End of Configuration ---


def plot_ecg_comparisons():
    """
    Loads real and synthetic ECG data and plots random samples
    from each for visual comparison.
    """
    # --- 1. Load Data ---
    print("Loading data...")
    if not os.path.exists(REAL_DATA_PATH) or not os.path.exists(SYNTHETIC_DATA_PATH):
        print("Error: Make sure both 'processed_ecg_data.npz' and 'synthetic_ecg_data_vae.npz' exist.")
        return

    real_data = np.load(REAL_DATA_PATH)['sequences']
    synthetic_data = np.load(SYNTHETIC_DATA_PATH)['synthetic_sequences']
    
    print(f"Loaded {len(real_data)} real sequences and {len(synthetic_data)} synthetic sequences.")

    # --- 2. Create Plots ---
    print("Generating comparison plots...")
    fig, axes = plt.subplots(nrows=N_SAMPLES_TO_PLOT, ncols=2, figsize=(10, 12))
    fig.suptitle('Real vs. Synthetic ECG Heartbeat Comparison', fontsize=16)

    for i in range(N_SAMPLES_TO_PLOT):
        # Select a random index for the real and synthetic data
        real_idx = np.random.randint(0, len(real_data))
        synth_idx = np.random.randint(0, len(synthetic_data))

        # Plot Real Data on the left column
        ax_real = axes[i, 0]
        ax_real.plot(real_data[real_idx])
        ax_real.set_title(f"Real Heartbeat #{real_idx}")
        ax_real.set_xticks([])
        ax_real.set_yticks([])

        # Plot Synthetic Data on the right column
        ax_synth = axes[i, 1]
        ax_synth.plot(synthetic_data[synth_idx])
        ax_synth.set_title(f"Synthetic Heartbeat #{synth_idx}")
        ax_synth.set_xticks([])
        ax_synth.set_yticks([])

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()


if __name__ == '__main__':
    plot_ecg_comparisons()