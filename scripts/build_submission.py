import shutil
import sys
from pathlib import Path
from src.monetary_policy.reporting.delivery_builder import build_final_submission

def main():
    print("Building final submission directory...")
    res = build_final_submission()
    print(f"Manifest written. {res['included_files']} files included.")
    
    root = Path(__file__).resolve().parent.parent
    submission_dir = root / "final_submission"
    
    zip_path = root / "delivery" / "final_submission.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
        
    print(f"Creating zip archive at {zip_path}...")
    shutil.make_archive(str(zip_path.with_suffix('')), 'zip', str(submission_dir))
    print("Done.")

if __name__ == "__main__":
    main()
