from flask import Flask, request, send_file, render_template_string
from pathlib import Path
import pandas as pd
from data_catalog import load_dataset, get_dataset_profile, save_dataset
from main import run_cleaning_pipeline
import asyncio

app = Flask(__name__)

# Custom 404 error page template
ERROR_404_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>404 - Page Not Found</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
        }
        h1 { color: #333; }
        p { color: #666; }
    </style>
</head>
<body>
    <h1>404 - Page Not Found</h1>
    <p>The requested URL was not found on the server.</p>
    <p>Please check the URL or return to the <a href="/">homepage</a>.</p>
</body>
</html>
'''

@app.errorhandler(404)
def page_not_found(e):
    return render_template_string(ERROR_404_TEMPLATE), 404

@app.route("/")
def home():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Data Processing API</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }
                h1 { color: #333; }
                code { 
                    background: #f4f4f4;
                    padding: 2px 5px;
                    border-radius: 3px;
                }
            </style>
        </head>
        <body>
            <h1>Data Processing API</h1>
            <p>Use POST request to <code>/process_dataset</code> with a file upload to process your data.</p>
        </body>
        </html>
    ''')
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
    app.run(host="localhost", port=5000)
