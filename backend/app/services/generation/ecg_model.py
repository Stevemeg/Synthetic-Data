"""Existing convolutional VAE with a dimension-safe decoder."""

import torch
from torch import nn


class VAE(nn.Module):
    def __init__(self, seq_len: int, latent_dim: int = 16):
        super().__init__()
        if type(seq_len) is not int or seq_len < 4 or type(latent_dim) is not int or latent_dim < 1:
            raise ValueError("Invalid VAE dimensions")
        self.seq_len = seq_len
        self.latent_dim = latent_dim
        self.encoder = nn.Sequential(
            nn.Conv1d(1, 32, 3, 2, 1),
            nn.ReLU(),
            nn.Conv1d(32, 64, 3, 2, 1),
            nn.ReLU(),
            nn.Flatten(),
        )
        with torch.no_grad():
            flattened_size = self.encoder(torch.zeros(1, 1, seq_len)).shape[1]
        self.fc_mean = nn.Linear(flattened_size, latent_dim)
        self.fc_log_var = nn.Linear(flattened_size, latent_dim)
        self.decoder_fc = nn.Linear(latent_dim, flattened_size)
        self.unflatten = nn.Unflatten(1, (64, flattened_size // 64))
        self.decoder = nn.Sequential(
            nn.ConvTranspose1d(64, 32, 3, 2, 1, output_padding=1),
            nn.ReLU(),
            nn.ConvTranspose1d(32, 1, 3, 2, 1, output_padding=1),
            nn.Sigmoid(),
        )

    def decode(self, latent):
        return self.decoder(self.unflatten(self.decoder_fc(latent)))[..., : self.seq_len]

    def reparameterize(self, mean, logvar):
        return mean + torch.randn_like(mean) * torch.exp(0.5 * logvar)

    def forward(self, signals):
        encoded = self.encoder(signals)
        mean, logvar = self.fc_mean(encoded), self.fc_log_var(encoded).clamp(-20, 20)
        return self.decode(self.reparameterize(mean, logvar)), mean, logvar


def loss_function(reconstruction, source, mean, logvar):
    return nn.functional.mse_loss(reconstruction, source, reduction="sum") - 0.5 * torch.sum(
        1 + logvar - mean.pow(2) - logvar.exp()
    )
