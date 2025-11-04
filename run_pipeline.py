import pandas as pd
import numpy as np
import neurokit2 as nk
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm
import os
import argparse
import sys

# --- PyTorch VAE Model Definition (No changes) ---
class VAE(nn.Module):
    def __init__(self, seq_len, latent_dim=16):
        super(VAE, self).__init__()
        self.encoder = nn.Sequential(
            nn.Conv1d(1, 32, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.Flatten()
        )
        with torch.no_grad():
            dummy_input = torch.zeros(1, 1, seq_len)
            flattened_size = self.encoder(dummy_input).shape[1]
        self.fc_mean = nn.Linear(flattened_size, latent_dim)
        self.fc_log_var = nn.Linear(flattened_size, latent_dim)
        self.decoder_fc = nn.Linear(latent_dim, flattened_size)
        self.unflatten = nn.Unflatten(1, (64, seq_len // 4))
        self.decoder = nn.Sequential(
            nn.ConvTranspose1d(64, 32, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.ReLU(),
            nn.ConvTranspose1d(32, 1, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.Sigmoid()
        )
    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std
    def forward(self, x):
        h = self.encoder(x)
        mu, logvar = self.fc_mean(h), self.fc_log_var(h)
        z = self.reparameterize(mu, logvar)
        z = self.decoder_fc(z)
        z = self.unflatten(z)
        return self.decoder(z), mu, logvar

def loss_function(recon_x, x, mu, logvar):
    BCE = nn.functional.mse_loss(recon_x, x, reduction='sum')
    KLD = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    return BCE + KLD

# --- Main Pipeline Function ---
def run_full_pipeline(input_file, output_file, model_output_file):
    # --- Configuration ---
    SAMPLING_RATE = 125
    SAMPLES_BEFORE = 32
    SAMPLES_AFTER = 64
    LATENT_DIM = 16
    EPOCHS = 50
    BATCH_SIZE = 128
    LEARNING_RATE = 1e-3
    # --- End of Configuration ---

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found at '{input_file}'")
    print(f"Loading and processing data from '{input_file}'...")
    df = pd.read_csv(input_file, header=None, engine='python')
    df.dropna(axis=1, how='all', inplace=True)
    df.fillna(0, inplace=True)
    all_sequences, all_labels = [], []
    for index, row in tqdm(df.iterrows(), total=df.shape[0], file=sys.stdout):
        raw_signal, label = row.iloc[:-1].values.astype(float), row.iloc[-1]
        try:
            cleaned_signal = nk.ecg_clean(raw_signal, sampling_rate=SAMPLING_RATE)
            rpeaks_info = nk.ecg_findpeaks(cleaned_signal, sampling_rate=SAMPLING_RATE)
            
            # --- THIS IS THE FIX ---
            # Check if the 'ECG_R_Peaks' key exists and if the list is not empty
            if 'ECG_R_Peaks' in rpeaks_info and len(rpeaks_info['ECG_R_Peaks']) > 0:
                r_peaks = rpeaks_info['ECG_R_Peaks']
            else:
                # If no peaks are found, skip to the next row
                continue
            # --- END OF FIX ---

            for peak in r_peaks:
                start, end = peak - SAMPLES_BEFORE, peak + SAMPLES_AFTER
                if start >= 0 and end < len(cleaned_signal):
                    segment = cleaned_signal[start:end]
                    if np.std(segment) > 0:
                        normalized_segment = (segment - np.mean(segment)) / np.std(segment)
                    else:
                        normalized_segment = segment - np.mean(segment)
                    all_sequences.append(normalized_segment)
                    all_labels.append(label)
        except Exception as e:
            print(f"Skipping row {index} due to processing error: {e}", file=sys.stdout)
            continue
    sequences_array = np.array(all_sequences)
    labels_array = np.array(all_labels)
    print(f"\nProcessing complete. Total sequences extracted: {sequences_array.shape[0]}", file=sys.stdout)
    if len(sequences_array) == 0:
        raise ValueError("No valid heartbeat sequences could be extracted from the provided file.")
    print("\nPreparing data for PyTorch training...", file=sys.stdout)
    sequences_tensor = torch.from_numpy(sequences_array).float().unsqueeze(1)
    dataset = TensorDataset(sequences_tensor)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    seq_len = sequences_array.shape[1]
    model = VAE(seq_len=seq_len, latent_dim=LATENT_DIM)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    print("Training the PyTorch VAE model...", file=sys.stdout)
    model.train()
    for epoch in range(EPOCHS):
        train_loss = 0
        for batch_idx, (data,) in enumerate(dataloader):
            optimizer.zero_grad()
            recon_batch, mu, logvar = model(data)
            loss = loss_function(recon_batch, data, mu, logvar)
            loss.backward()
            train_loss += loss.item()
            optimizer.step()
        print(f'====> Epoch: {epoch+1} Average loss: {train_loss / len(dataloader.dataset):.4f}', file=sys.stdout)
    print("✅ Training complete.", file=sys.stdout)
    print("Generating synthetic data...", file=sys.stdout)
    model.eval()
    with torch.no_grad():
        z = torch.randn(len(sequences_array), LATENT_DIM)
        synthetic_sequences = model.decoder(model.unflatten(model.decoder_fc(z))).squeeze().numpy()
    np.savez_compressed(output_file, synthetic_sequences=synthetic_sequences, labels=labels_array[:len(synthetic_sequences)])
    print(f"✅ Synthetic data saved to '{output_file}'", file=sys.stdout)
    torch.save(model.decoder.state_dict(), model_output_file)
    print(f"✅ Decoder model saved to '{model_output_file}'", file=sys.stdout)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run the full ECG data synthesis pipeline with PyTorch.")
    parser.add_argument('--input_file', type=str, required=True, help='Path to the input CSV file.')
    parser.add_-argument('--output_file', type=str, required=True, help='Path to save the generated synthetic data (.npz).')
    parser.add_argument('--model_output_file', type=str, required=True, help='Path to save the trained decoder model (.pt).')
    
    args = parser.parse_args()
    
    try:
        run_full_pipeline(args.input_file, args.output_file, args.model_output_file)
    except Exception as e:
        print(f"An error occurred during pipeline execution: {e}")
        exit(1)