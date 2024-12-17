from pathlib import Path
import shutil

def copy_file(source_file, destination_path):
    try:
        # Convert strings to Path objects
        source = Path(source_file)
        dest = Path(destination_path)
        
        # Ensure the destination directory exists
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy the file
        shutil.copy2(source, dest)
        print(f"File successfully copied to {dest}")
        
    except FileNotFoundError:
        print(f"Source file '{source_file}' not found")
    except PermissionError:
        print("Permission denied. Check file and folder permissions")
    except Exception as e:
        print(f"An error occurred: {str(e)}")