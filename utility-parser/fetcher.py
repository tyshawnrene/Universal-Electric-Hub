import os
import requests
from pathlib import Path
from datetime import datetime

script_dir = Path(__file__).resolve().parent

def download_latest_utility_pdf(target_url: str, custom_filename: str = None):
    print(f"Connecting to source to check for the most recent filing...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GridSync-Bot/1.0"
    }
    
    try:
        response = requests.get(target_url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()
        
        # Check content-type to ensure it's a PDF
        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type.lower() and not target_url.endswith(".pdf"):
            print(f"Warning: Target URL may not be a direct PDF link (Content-Type: {content_type})")

        # Determine filename
        if not custom_filename:
            filename = target_url.split("/")[-1].split("?")[0]
            if not filename.endswith(".pdf"):
                filename = f"latest_filing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        else:
            filename = custom_filename

        file_path = script_dir / filename
        
        # Write file chunks
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"Successfully downloaded latest filing to: {file_path}")
        return str(file_path)

    except Exception as e:
        print(f"Failed to download PDF: {e}")
        return None

# At the end of your fetcher.py script:
if __name__ == "__main__":
    target_url = "https://www.psc.state.fl.us/Files/PDF/Utilities/Electricgas/IRP/SampleFiling.pdf"
    downloaded_path = download_latest_utility_pdf(target_url, "fpl_irp_2026.pdf")
    
    if downloaded_path:
        # Automatically trigger the parser main script workflow
        from main import process_single_pdf
        process_single_pdf(Path(downloaded_path))