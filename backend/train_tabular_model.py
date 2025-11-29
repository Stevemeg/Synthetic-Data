import argparse
import pandas as pd
import os
from sdv.metadata import SingleTableMetadata
from sdv.single_table import TVAESynthesizer

def train_and_save_model(input_path, model_output_path):
    """
    Loads a dataset, trains a TVAE synthesizer, and saves the model.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Dataset not found at: {input_path}")

    print(f"Loading data from {input_path}...")
    data = pd.read_csv(input_path)

    # --- Preprocessing ---
    # You can add more of your specific preprocessing steps here if needed
    data.dropna(inplace=True)
    print("Data preprocessed.")

    # --- SDV Metadata ---
    print("Detecting metadata...")
    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(data=data)

    # --- Train the Synthesizer ---
    synthesizer = TVAESynthesizer(metadata)
    print("Training TVAE model... (This may take a few minutes)")
    synthesizer.fit(data)

    # --- Save the Trained Model ---
    synthesizer.save(filepath=model_output_path)
    print(f"✅ Model successfully trained and saved to: {model_output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and save a synthesizer model.")
    parser.add_argument('--dataset', type=str, required=True, help='Path to the input dataset CSV file.')
    parser.add_argument('--model_path', type=str, required=True, help='Path to save the output model .pkl file.')
    
    args = parser.parse_args()
    
    train_and_save_model(args.dataset, args.model_path)