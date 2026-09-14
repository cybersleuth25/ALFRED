import os
import urllib.request
import zipfile
import shutil

REPO_ZIP_URL = "https://github.com/aivsomkar/PinViz/archive/refs/heads/main.zip"
TARGET_DIR = os.path.join("frontend", "src", "components", "PinViz")
ZIP_PATH = "pinviz_temp.zip"
EXTRACT_DIR = "pinviz_temp_extract"

def main():
    print(f"Downloading PinViz source from {REPO_ZIP_URL}...")
    urllib.request.urlretrieve(REPO_ZIP_URL, ZIP_PATH)

    print("Extracting files...")
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

    # The zip contains a folder named 'PinViz-main'
    src_dir = os.path.join(EXTRACT_DIR, "PinViz-main", "src")
    
    if os.path.exists(TARGET_DIR):
        print(f"Cleaning up existing {TARGET_DIR}...")
        shutil.rmtree(TARGET_DIR)
        
    print(f"Moving source files to {TARGET_DIR}...")
    shutil.copytree(src_dir, TARGET_DIR)
    
    # Clean up
    print("Cleaning up temporary files...")
    os.remove(ZIP_PATH)
    shutil.rmtree(EXTRACT_DIR)
    
    print("✅ PinViz source files successfully integrated!")
    print(f"You can find them in: {TARGET_DIR}")

if __name__ == "__main__":
    main()
