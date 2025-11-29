import argparse
import os
import traceback
import torch
import torch.nn as nn
import torchvision.utils as vutils
from zipfile import ZipFile

# --- Configuration (from your script) ---
nc = 3      # Number of channels (assumed RGB for consistency)
nz = 100    # Size of latent vector
ngf = 64    # Generator feature map size
# --- End of Configuration ---

# --- Generator Model (Copied directly from your script) ---
class Generator(nn.Module):
    def __init__(self):
        super(Generator, self).__init__()
        self.main = nn.Sequential(
            nn.ConvTranspose2d(nz, ngf * 8, 4, 1, 0, bias=False),
            nn.BatchNorm2d(ngf * 8),
            nn.ReLU(True),
            nn.ConvTranspose2d(ngf * 8, ngf * 4, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ngf * 4),
            nn.ReLU(True),
            nn.ConvTranspose2d(ngf * 4, ngf * 2, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ngf * 2),
            nn.ReLU(True),
            nn.ConvTranspose2d(ngf * 2, ngf, 4, 2, 1, bias=False),
            nn.BatchNorm2d(ngf),
            nn.ReLU(True),
            nn.ConvTranspose2d(ngf, nc, 4, 2, 1, bias=False),
            nn.Tanh()
        )

    def forward(self, input):
        return self.main(input)

# --- Main Generation Function ---
def generate_images(model_path, output_zip_path, num_images):
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"GAN model not found at: {model_path}")

    print(f"Loading pre-trained GAN from: {model_path}")
    
    device = torch.device("cpu")

    # Initialize Generator and load the saved state
    netG = Generator().to(device)
    netG.load_state_dict(torch.load(model_path, map_location=device))
    netG.eval()

    # Generate images from random noise
    print(f"Generating {num_images} synthetic images...")
    with torch.no_grad():
        noise = torch.randn(num_images, nz, 1, 1, device=device)
        # Renamed 'fake_images' to 'generated_images'
        all_generated_images = netG(noise).detach().cpu()

    # --- Save images to a zip file ---
    temp_dir = "temp_image_generation"
    os.makedirs(temp_dir, exist_ok=True)

    # Determine how many images to show in the grid. Max 64 (8x8).
    images_in_grid = min(num_images, 64) 
    grid_tensor = all_generated_images[:images_in_grid]

    # Renamed the output file
    grid_image_filename = "synthetic_image_grid.png"
    vutils.save_image(grid_tensor, os.path.join(temp_dir, grid_image_filename), normalize=True, nrow=8)

    with ZipFile(output_zip_path, 'w') as zipf:
        zipf.write(os.path.join(temp_dir, grid_image_filename), arcname=grid_image_filename)

    # Clean up temporary files
    for file in os.listdir(temp_dir):
        os.remove(os.path.join(temp_dir, file))
    os.rmdir(temp_dir)
    
    print(f"Synthetic image grid saved to {output_zip_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic images from a pre-trained GAN.")
    parser.add_argument('--model_path', type=str, required=True, help='Path to the pre-trained GAN model .pth file.')
    parser.add_argument('--output_zip_path', type=str, required=True, help='Path to save the output .zip file.')
    parser.add_argument('--count', type=int, required=True, help='Number of images to generate.')
    
    args = parser.parse_args()
    
    try:
        generate_images(args.model_path, args.output_zip_path, args.count)
    except Exception as e:
        error_log_path = os.path.join(os.path.dirname(__file__), "imaging_error_log.txt")
        with open(error_log_path, "w") as f:
            f.write(traceback.format_exc())
        print(f"An error occurred: {traceback.format_exc()}")
        exit(1)
