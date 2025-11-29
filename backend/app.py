from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import uuid
import json
import sys
import subprocess

# --- Import the script directly (works because it's now in the same folder) ---
try:
    from run_pipeline import run_full_pipeline
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import run_pipeline: {e}")

app = Flask(__name__)
CORS(app)

# --- Configuration ---
# Everything is now relative to the current directory (backend)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DATA_DIR = os.path.join(BASE_DIR, "generated_data")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# Since we moved the models into backend, they are here:
PRETRAINED_MODELS_DIR = BASE_DIR 

os.makedirs(GENERATED_DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# --- SCRIPT PATHS (Now in the same folder) ---
TABULAR_SCRIPT = os.path.join(BASE_DIR, "generate_tabular.py")
IMAGING_SCRIPT = os.path.join(BASE_DIR, "generate_images.py")
GENOMIC_SCRIPT = os.path.join(BASE_DIR, "generate_genomic.py")
TIME_SERIES_SCRIPT = os.path.join(BASE_DIR, "run_pipeline.py")
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
        
        command = [PYTHON_EXECUTABLE, TABULAR_SCRIPT, "--output_file", output_path, "--rows", str(num_rows)]

        if source_file_path:
             command.extend(["--input_file", source_file_path])
        else:
             dataset_name = config.get('dataset')
             if dataset_name == 'Heart Disease':
                 model_filename = 'heart_disease_model.pkl'
             else:
                 model_filename = 'diabetes_model.pkl'
             
             model_path = os.path.join(PRETRAINED_MODELS_DIR, model_filename)
             command.extend(["--model_path", model_path]) 

        result = subprocess.run(command, capture_output=True, text=True, cwd=BASE_DIR)
        
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
        
        # Run imported function directly
        run_full_pipeline(input_file=source_file_path, output_file=output_path, model_output_file=model_path)
        
        if not os.path.exists(output_path):
            return jsonify({"status": "error", "message": "Pipeline ran, but output file was not created."}), 500
            
        download_url = f"{request.url_root}generated/{output_filename}"
        return jsonify({"status": "success", "message": "Data generated successfully.", "fileUrl": download_url})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
        result = subprocess.run(command, capture_output=True, text=True, cwd=BASE_DIR)
        
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
        
        result = subprocess.run(command, capture_output=True, text=True, cwd=BASE_DIR)
        
        if result.returncode != 0:
            return jsonify({"status": "error", "message": "Script failed.", "details": result.stderr}), 500

        download_url = f"{request.url_root}generated/{output_filename}"
        return jsonify({"status": "success", "message": "Data generated.", "fileUrl": download_url})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)