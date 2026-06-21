import hashlib
import zipfile
import shutil
import os
from pathlib import Path

ROOT = Path(r"D:\PyCharm\Quant\monetary_policy_project").resolve()

def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def gate_12():
    zip_path = ROOT / "final_submission.zip"
    if not zip_path.exists():
        # Maybe it's final_submission(1).zip?
        for p in ROOT.glob("final_submission*.zip"):
            zip_path = p
            break
            
    if not zip_path.exists():
        raise FileNotFoundError("Could not find final_submission.zip")
        
    print(f"Verifying {zip_path.name}")
    
    temp_dir = ROOT / "output" / "diagnostics" / "temp_unzip"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(temp_dir)
        
    # The zip contains the files at the root of the zip (or maybe inside a final_submission/ folder)
    # Check where paper/ is located
    unzipped_paper_docx = temp_dir / "paper" / "课程论文_提交版.docx"
    unzipped_paper_pdf = temp_dir / "paper" / "课程论文_提交版.pdf"
    
    if not unzipped_paper_docx.exists():
        # Maybe it extracted into final_submission/paper/
        unzipped_paper_docx = temp_dir / "final_submission" / "paper" / "课程论文_提交版.docx"
        unzipped_paper_pdf = temp_dir / "final_submission" / "paper" / "课程论文_提交版.pdf"
        
    root_docx = ROOT / "paper" / "课程论文_提交版.docx"
    root_pdf = ROOT / "paper" / "课程论文_提交版.pdf"
    
    unzipped_docx_hash = compute_sha256(unzipped_paper_docx)
    root_docx_hash = compute_sha256(root_docx)
    print(f"Packaged DOCX: {unzipped_docx_hash}")
    print(f"Root DOCX:     {root_docx_hash}")
    assert unzipped_docx_hash == root_docx_hash, "Packaged DOCX is not byte-identical to root DOCX"
    
    unzipped_pdf_hash = compute_sha256(unzipped_paper_pdf)
    root_pdf_hash = compute_sha256(root_pdf)
    print(f"Packaged PDF:  {unzipped_pdf_hash}")
    print(f"Root PDF:      {root_pdf_hash}")
    assert unzipped_pdf_hash == root_pdf_hash, "Packaged PDF is not byte-identical to root PDF"
    
    print("Byte-level delivery verification PASSED.")
    
    shutil.rmtree(temp_dir)

if __name__ == "__main__":
    gate_12()
