import os
import sys
import json
import hashlib
import zipfile
import fitz  # PyMuPDF
from pathlib import Path
from PIL import Image

ROOT = Path(r"D:\PyCharm\Quant\monetary_policy_project").resolve()

def file_sha256(path: Path) -> str:
    if not path.exists(): return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def zip_member_sha256(zip_path: Path, member_name: str) -> str:
    if not zip_path.exists(): return None
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            with zf.open(member_name) as f:
                h = hashlib.sha256()
                for chunk in iter(lambda: f.read(4096), b""):
                    h.update(chunk)
                return h.hexdigest()
    except KeyError:
        return None

def render_pdf_to_images(pdf_path: Path, output_dir: Path, dpi: int = 180):
    output_dir.mkdir(parents=True, exist_ok=True)
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return []
    
    doc = fitz.open(str(pdf_path))
    image_paths = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for i in range(len(doc)):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_path = output_dir / f"page_{i+1:03d}.png"
        pix.save(str(img_path))
        image_paths.append(img_path)
    return image_paths

def create_contact_sheet(image_paths, output_path, cols=4):
    if not image_paths: return
    images = [Image.open(p) for p in image_paths]
    w, h = images[0].size
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new('RGB', (w * cols, h * rows), (255, 255, 255))
    
    for idx, img in enumerate(images):
        row = idx // cols
        col = idx % cols
        sheet.paste(img, (col * w, row * h))
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)

def main():
    # 4. Diagnose the current package before editing
    diag_dir = ROOT / "output" / "diagnostics" / "final_journal_repair"
    diag_dir.mkdir(parents=True, exist_ok=True)
    
    hashes = {
        "paper/课程论文_提交版.docx": file_sha256(ROOT / "paper" / "课程论文_提交版.docx"),
        "paper/课程论文_提交版.pdf": file_sha256(ROOT / "paper" / "课程论文_提交版.pdf"),
        "final_submission/paper/课程论文_提交版.docx": file_sha256(ROOT / "final_submission" / "paper" / "课程论文_提交版.docx"),
        "final_submission/paper/课程论文_提交版.pdf": file_sha256(ROOT / "final_submission" / "paper" / "课程论文_提交版.pdf"),
        "ZIP member paper/课程论文_提交版.docx": zip_member_sha256(ROOT / "delivery" / "final_submission.zip", "paper/课程论文_提交版.docx"),
        "ZIP member paper/课程论文_提交版.pdf": zip_member_sha256(ROOT / "delivery" / "final_submission.zip", "paper/课程论文_提交版.pdf"),
    }
    
    with (diag_dir / "pre_repair_hashes.json").open("w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, ensure_ascii=False)
        
    # 5. Render all reference and current files
    before_dir = diag_dir / "before"
    
    # Render current PDF
    curr_images = render_pdf_to_images(
        ROOT / "paper" / "课程论文_提交版.pdf", 
        before_dir / "current_pages"
    )
    create_contact_sheet(curr_images, before_dir / "current_contact_sheet.png")
    
    # Render original SNA PDF
    sna_pdf = ROOT / "references" / "journal_format" / "SNA全球化核算框架及其应用_杨仲山.pdf"
    ref_images = render_pdf_to_images(sna_pdf, before_dir / "reference_pdf_pages")
    create_contact_sheet(ref_images, before_dir / "reference_pdf_contact_sheet.png")

if __name__ == "__main__":
    main()
