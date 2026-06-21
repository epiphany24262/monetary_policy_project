import hashlib
import json
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def hash_file(path: Path) -> str:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def hash_zip_member(zip_path: Path, member_name: str) -> str:
    if not zip_path.exists():
        return None
    h = hashlib.sha256()
    with zipfile.ZipFile(zip_path, "r") as z:
        try:
            with z.open(member_name, "r") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()
        except KeyError:
            return None

def gate_23():
    files = {
        "root_docx": PROJECT_ROOT / "paper" / "课程论文_提交版.docx",
        "root_pdf": PROJECT_ROOT / "paper" / "课程论文_提交版.pdf",
        "staged_docx": PROJECT_ROOT / "final_submission" / "paper" / "课程论文_提交版.docx",
        "staged_pdf": PROJECT_ROOT / "final_submission" / "paper" / "课程论文_提交版.pdf",
    }
    
    zip_path = PROJECT_ROOT / "delivery" / "final_submission.zip"
    
    results = {}
    for k, v in files.items():
        results[k] = hash_file(v)
        
    results["zip_docx"] = hash_zip_member(zip_path, "paper/课程论文_提交版.docx")
    results["zip_pdf"] = hash_zip_member(zip_path, "paper/课程论文_提交版.pdf")
    
    out_dir = PROJECT_ROOT / "output" / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "final_delivery_hashes.json"
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print(json.dumps(results, indent=2))
    
    # Assertions
    assert results["root_docx"] == results["staged_docx"] == results["zip_docx"], "DOCX hashes do not match!"
    assert results["root_pdf"] == results["staged_pdf"] == results["zip_pdf"], "PDF hashes do not match!"
    print("All hashes match perfectly!")

if __name__ == "__main__":
    gate_23()
