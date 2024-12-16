from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
import pandas as pd
from data_catalog import load_dataset, get_dataset_profile, save_dataset
from main import run_cleaning_pipeline
import tempfile
import uvicorn

app = FastAPI()
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.post("/process_dataset")
async def process_dataset(file: UploadFile = File(...)):
    # Save uploaded file
    temp_path = UPLOAD_DIR / file.filename
    with temp_path.open("wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Load and profile the dataset
    df = load_dataset(temp_path)
    initial_profile = get_dataset_profile(df)
    
    # Run the cleaning and transformation pipeline
    processed_df = await run_cleaning_pipeline(df, initial_profile)
    
    # Save processed dataset
    output_path = UPLOAD_DIR / f"processed_{file.filename}"
    save_dataset(processed_df, output_path)
    
    return FileResponse(
        path=output_path,
        filename=f"processed_{file.filename}",
        media_type="application/octet-stream"
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
