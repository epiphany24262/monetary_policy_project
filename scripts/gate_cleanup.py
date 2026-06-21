import os
import shutil
import time
from pathlib import Path
import win32com.client
import pythoncom

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def safe_close_word():
    try:
        pythoncom.CoInitialize()
        # Connect to an existing instance if available
        word = win32com.client.Dispatch("Word.Application")
        for doc in word.Documents:
            try:
                print(f"Closing stranded document: {doc.Name}")
                doc.Close(False)
            except Exception as e:
                print(f"Failed to close doc: {e}")
        word.Quit()
        print("Safely quit Word COM instance.")
    except Exception as e:
        print(f"No existing Word instance found or could not connect: {e}")

def delete_stale():
    targets = [
        PROJECT_ROOT / "paper",
        PROJECT_ROOT / "final_submission",
        PROJECT_ROOT / "delivery" / "final_submission.zip",
    ]
    
    # Also delete ~$*.docx
    for p in PROJECT_ROOT.rglob("~$*.docx"):
        try:
            p.unlink(missing_ok=True)
            print(f"Deleted {p.name}")
        except Exception as e:
            print(f"Failed to delete {p.name}: {e}")

    for target in targets:
        if target.is_dir():
            try:
                shutil.rmtree(target)
                print(f"Deleted directory: {target.relative_to(PROJECT_ROOT)}")
            except Exception as e:
                print(f"Failed to delete {target.relative_to(PROJECT_ROOT)}: {e}")
        elif target.is_file():
            try:
                target.unlink()
                print(f"Deleted file: {target.relative_to(PROJECT_ROOT)}")
            except Exception as e:
                print(f"Failed to delete {target.relative_to(PROJECT_ROOT)}: {e}")

def main():
    safe_close_word()
    time.sleep(1)
    delete_stale()

if __name__ == "__main__":
    main()
