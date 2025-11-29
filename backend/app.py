from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import uuid
import json
import sys
import subprocess

app = Flask(__name__)
CORS(app)

# --- Configuration & Path Fixing ---

# 1. Get the folder where THIS file (app.py) lives (e.g., .../backend)
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Get the parent folder (e.g., .../Synthetic-Data)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

# 3. Add the project root to Python's "search path" so it can find run_pipeline.py
sys.path.append(PROJECT_ROOT)

# 4. Now we can safely import the script
try:
    from run_pipeline import run_full_pipeline
except ImportError:
    print("Warning: Could not import run_pipeline. Make sure it exists in the project root.")

# 5. Define folders relative to the BACKEND directory
GENERATED_DATA_DIR = os.path.join(BACKEND_DIR, "generated_data")
UPLOADS_DIR = os.path.join(BACKEND_DIR, "uploads")
MODELS_DIR = os.path.join(BACKEND_DIR, "models")
PRETRAINED_MODELS_DIR = PROJECT_ROOT # Models like .pth are likely in the root

# Create directories if they don't exist
os.makedirs(GENERATED_DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# 6. Define Script Paths
TABULAR_SCRIPT = os.path.join(PROJECT_ROOT, "generate_tabular.py")
IMAGING_SCRIPT = os.path.join(PROJECT_ROOT, "generate_images.py")
GENOMIC_SCRIPT = os.path.join(PROJECT_ROOT, "generate_genomic.py")
TIME_SERIES_SCRIPT = os.path.join(PROJECT_ROOT, "run_pipeline.py")
PYTHON_EXECUTABLE = sys.executable

# --- Helper Function ---
def get_config_and_file():
    config_str = request.form.get('config')
    if not config_str:
        return None, None, jsonify({"status": "error", "message": "Missing config data"}), 400
    config = json.loads(config_str)
    source_file_path = None
    if 'sourceFile' in request.files:
        file = request.files['sourceFile']
        if file.filename != '':
            filename = f"upload_{uuid.uuid4().hex}_{file.filename}"
            source_file_path = os.path.join(UPLOADS_DIR, filename)
            file.save(source_file_path)
    return config, source_file_path, None, None

# --- API Routes ---

@app.route('/')
def home():
    return "Medical Data Generator API is Running!"

@app.route('/generated/<filename>')
def generated_file(filename):
    return send_from_directory(GENERATED_DATA_DIR, filename)

@app.route('/api/generate/tabular', methods=['POST'])
def generate_tabular():
    try:
        config, source_file_path, error_response, status_code = get_config_and_file()
        if error_response: return error_response, status_code
        
        output_filename = f"tabular_output_{uuid.uuid4().hex}.csv"
        output_path = os.path.join(GENERATED_DATA_DIR, output_filename)
        num_rows = config.get('rowCount', 100)
        
        # Check if we are in 'Custom' mode or Pre-trained mode
        # If user uploaded a file, we assume they want to use that.
        # If no file, we look for dataset choice.
        
        command = [PYTHON_EXECUTABLE, TABULAR_SCRIPT, "--output_file", output_path, "--rows", str(num_rows)]

        if source_file_path:
             command.extend(["--input_file", source_file_path])
        else:
             # Handle pre-trained loading if applicable
             dataset_name = config.get('dataset')
             if dataset_name == 'Heart Disease':
                 model_filename = 'heart_disease_model.pkl'
             else:
                 model_filename = 'diabetes_model.pkl'
             
             model_path = os.path.join(PRETRAINED_MODELS_DIR, model_filename)
             # You might need to update generate_tabular.py to accept --model_path if you merged the logic
             # For now, we assume the script handles it or we add it here:
             # command.extend(["--model_path", model_path]) 
             # Note: Ensure generate_tabular.py supports the arguments you send here.

        result = subprocess.run(command, capture_output=True, text=True, cwd=PROJECT_ROOT)
        
        if result.returncode != 0:
            return jsonify({"status": "error", "message": "Script failed.", "details": result.stderr}), 500

        if not os.path.exists(output_path):
            return jsonify({"status": "error", "message": "Output file not found."}), 500

        download_url = f"{request.url_root}generated/{output_filename}"
        return jsonify({"status": "success", "message": "Data generated.", "fileUrl": download_url})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/generate/timeseries', methods=['POST'])
def generate_timeseries():
    config, source_file_path, error_response, status_code = get_config_and_file()
    if error_response: return error_response, status_code
    if not source_file_path:
        return jsonify({"status": "error", "message": "A source CSV file is required."}), 400
    try:
        output_filename = f"timeseries_output_{uuid.uuid4().hex}.npz"
        output_path = os.path.join(GENERATED_DATA_DIR, output_filename)
        model_filename = f"vae_model_{uuid.uuid4().hex}.pt"
        model_path = os.path.join(MODELS_DIR, model_filename)
        
        # Import and run directly
        run_full_pipeline(input_file=source_file_path, output_file=output_path, model_output_file=model_path)
        
        if not os.path.exists(output_path):
            return jsonify({"status": "error", "message": "Pipeline ran, but output file was not created."}), 500
            
        # Use request.url_root to get the correct live URL
        download_url = f"{request.url_root}generated/{output_filename}"
        return jsonify({"status": "success", "message": "Data generated successfully.", "fileUrl": download_url})
    except Exception as e:
        return jsonify({"status": "error", "message": "An error occurred.", "details": str(e)}), 500

@app.route('/api/generate/genomic', methods=['POST'])
def generate_genomic():
    config, source_file_path, error_response, status_code = get_config_and_file()
    if error_response: return error_response, status_code
    if not source_file_path:
        return jsonify({"status": "error", "message": "A source file is required."}), 400
    try:
        output_filename = f"genomic_output_{uuid.uuid4().hex}.csv"
        output_path = os.path.join(GENERATED_DATA_DIR, output_filename)
        num_sequences = config.get('count', 100)
        command = [PYTHON_EXECUTABLE, GENOMIC_SCRIPT, "--input_file", source_file_path, "--output_file", output_path, "--count", str(num_sequences)]
        result = subprocess.run(command, capture_output=True, text=True, cwd=PROJECT_ROOT)
        
        if result.returncode != 0:
            return jsonify({"status": "error", "message": "Script failed.", "details": result.stderr}), 500
            
        download_url = f"{request.url_root}generated/{output_filename}"
        return jsonify({"status": "success", "message": "Data generated.", "fileUrl": download_url})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/generate/imaging', methods=['POST'])
def generate_imaging():
    try:
        config, _, error_response, status_code = get_config_and_file()
        if error_response: return error_response, status_code

        modality = config.get('modality')
        num_images = config.get('count', 10)

        if modality == 'MRI':
            model_filename = 'generator_brain.pth'
        elif modality == 'X-Ray':
            model_filename = 'generator_chest.pth'
        elif modality == 'Skin':
            model_filename = 'generator_skin.pth'
        else:
            return jsonify({"status": "error", "message": "Invalid modality selected."}), 400

        model_path = os.path.join(PRETRAINED_MODELS_DIR, model_filename)
        output_filename = f"imaging_output_{uuid.uuid4().hex}.zip"
        output_path = os.path.join(GENERATED_DATA_DIR, output_filename)

        command = [
            PYTHON_EXECUTABLE,
            IMAGING_SCRIPT,
            "--model_path", model_path,
            "--output_zip_path", output_path,
            "--count", str(num_images)
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, cwd=PROJECT_ROOT)
        
        if result.returncode != 0:
            return jsonify({"status": "error", "message": "Script failed.", "details": result.stderr}), 500

        download_url = f"{request.url_root}generated/{output_filename}"
        return jsonify({"status": "success", "message": "Data generated.", "fileUrl": download_url})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)