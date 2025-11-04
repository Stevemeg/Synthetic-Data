import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv1D, MaxPooling1D, Flatten, Dense, Dropout
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
import pandas as pd
import neurokit2 as nk
from tqdm import tqdm
import os

# --- Configuration ---
SYNTHETIC_DATA_PATH = 'synthetic_ecg_data_vae.npz'
# Path to the REAL test data CSV
REAL_TEST_CSV_PATH = r'C:\Users\konab\OneDrive\Desktop\Major project\local_data\ECG_Extracted\mitbih_test.csv'
SAMPLING_RATE = 125 # MIT-BIH is typically sampled at 360Hz, but this dataset version is 125Hz.
SAMPLES_BEFORE = 32
SAMPLES_AFTER = 64
# --- End of Configuration ---


def process_real_test_data(file_path):
    """A helper function to process the real test CSV on the fly."""
    if not os.path.exists(file_path):
        return None, None
    print(f"\nProcessing real test data from '{file_path}'...")
    df = pd.read_csv(file_path, header=None, engine='python')
    all_sequences, all_labels = [], []
    for index, row in tqdm(df.iterrows(), total=df.shape[0]):
        raw_signal, label = row.iloc[:-1].values, row.iloc[-1]
        try:
            cleaned_signal = nk.ecg_clean(raw_signal, sampling_rate=SAMPLING_RATE)
            rpeaks_info = nk.ecg_findpeaks(cleaned_signal, sampling_rate=SAMPLING_RATE)
            r_peaks = rpeaks_info['ECG_R_Peaks']
            if len(r_peaks) == 0: continue
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
        except Exception:
            continue
    return np.array(all_sequences), np.array(all_labels)


def run_final_evaluation():
    # Load synthetic data for TRAINING
    print("Loading synthetic training data...")
    if not os.path.exists(SYNTHETIC_DATA_PATH):
        print(f"Error: Synthetic data not found at '{SYNTHETIC_DATA_PATH}'. Please run run_pipeline.py first.")
        return
    synth_data = np.load(SYNTHETIC_DATA_PATH)
    X_synth, y_synth = synth_data['synthetic_sequences'], synth_data['labels']
    
    # Process real test data for EVALUATION
    X_real_test, y_real_test = process_real_test_data(REAL_TEST_CSV_PATH)
    if X_real_test is None: return

    # Encode labels to integers
    le = LabelEncoder()
    y_synth_encoded = le.fit_transform(y_synth)
    y_real_test_encoded = le.transform(y_real_test)
    
    # Reshape data for Conv1D layer
    X_synth = np.expand_dims(X_synth, -1)
    X_real_test = np.expand_dims(X_real_test, -1)
    
    num_classes = len(le.classes_)
    input_shape = (X_synth.shape[1], 1)
    
    print(f"\nTraining on {len(X_synth)} synthetic samples from multiple classes.")
    print(f"Testing on {len(X_real_test)} real samples from multiple classes.")
    print(f"Number of classes: {num_classes}")

    # Build and compile the 1D CNN Model
    model = Sequential([
        Conv1D(filters=32, kernel_size=5, activation='relu', input_shape=input_shape),
        MaxPooling1D(pool_size=2), Dropout(0.2),
        Conv1D(filters=64, kernel_size=5, activation='relu'),
        MaxPooling1D(pool_size=2), Dropout(0.2),
        Flatten(),
        Dense(64, activation='relu'),
        Dense(num_classes, activation='softmax')
    ])
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    model.summary()

    # Train the Model on SYNTHETIC Data
    print("\n--- Training model on SYNTHETIC data ---")
    model.fit(X_synth, y_synth_encoded, epochs=20, batch_size=32, validation_split=0.2)

    # Evaluate the Model on REAL Test Data
    print("\n--- Evaluating model on REAL test data ---")
    loss, accuracy = model.evaluate(X_real_test, y_real_test_encoded, verbose=0)
    print(f"\nFinal Model Accuracy on Real Test Data: {accuracy * 100:.2f}%")
    
    # Generate a detailed classification report
    y_pred_probs = model.predict(X_real_test)
    y_pred = np.argmax(y_pred_probs, axis=1)
    
    print("\nClassification Report:")
    target_names = [str(c) for c in le.classes_]
    print(classification_report(y_real_test_encoded, y_pred, target_names=target_names))


if __name__ == '__main__':
    run_final_evaluation()