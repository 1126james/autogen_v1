from flask import Flask, request, send_file
from pathlib import Path
import pandas as pd
from data_catalog import load_dataset, get_dataset_profile, save_dataset
from main import run_cleaning_pipeline
import asyncio

app = Flask(__name__)
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.route("/process_dataset", methods=["POST"])
def process_dataset():
    if 'file' not in request.files:
        return {"error": "No file provided"}, 400
        
    file = request.files['file']
    if file.filename == '':
        return {"error": "No selected file"}, 400
    
    # Save uploaded file
    temp_path = UPLOAD_DIR / file.filename
    file.save(temp_path)
    
    # Load and profile the dataset
    df = load_dataset(temp_path)
    initial_profile = get_dataset_profile(df)
    
    # Run the cleaning and transformation pipeline
    processed_df = asyncio.run(run_cleaning_pipeline(df, initial_profile))
    
    # Save processed dataset
    output_path = UPLOAD_DIR / f"processed_{file.filename}"
    save_dataset(processed_df, output_path)
    
    return send_file(
        output_path,
        as_attachment=True,
        download_name=f"processed_{file.filename}",
        mimetype="application/octet-stream"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
