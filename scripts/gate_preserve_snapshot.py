import hashlib
import json
import math
import shutil
import zipfile
from pathlib import Path
import fitz
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def compute_sha256(path: Path) -> str:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def compute_sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def write_contact_sheet(paths: list[Path], out_path: Path) -> None:
    if not paths:
        return
    thumbs = []
    for path in paths:
        img = Image.open(path).convert("RGB")
        img.thumbnail((220, 310))
        thumbs.append((path, img.copy()))
    cols = 4
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 250, rows * 350), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, (path, img) in enumerate(thumbs):
        x = (idx % cols) * 250 + 15
        y = (idx // cols) * 350 + 20
        sheet.paste(img, (x, y))
        draw.text((x, y + img.height + 6), path.stem, fill="black")
    sheet.save(out_path)

def gate_1():
    out_dir = PROJECT_ROOT / "output" / "diagnostics"
    snap_dir = out_dir / "pre_fix_snapshot"
    snap_dir.mkdir(parents=True, exist_ok=True)
    
    root_docx = PROJECT_ROOT / "paper" / "课程论文_提交版.docx"
    root_pdf = PROJECT_ROOT / "paper" / "课程论文_提交版.pdf"
    
    snap_docx = snap_dir / "课程论文_提交版_pre_fix.docx"
    snap_pdf = snap_dir / "课程论文_提交版_pre_fix.pdf"
    
    if root_docx.exists(): shutil.copy2(root_docx, snap_docx)
    if root_pdf.exists(): shutil.copy2(root_pdf, snap_pdf)
    
    staging_docx = PROJECT_ROOT / "final_submission" / "paper" / "课程论文_提交版.docx"
    staging_pdf = PROJECT_ROOT / "final_submission" / "paper" / "课程论文_提交版.pdf"
    
    zip_path = PROJECT_ROOT / "delivery" / "final_submission.zip"
    zip_docx_hash = None
    zip_pdf_hash = None
    
    if zip_path.exists():
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for info in zf.infolist():
                if info.filename.endswith("课程论文_提交版.docx"):
                    zip_docx_hash = compute_sha256_bytes(zf.read(info.filename))
                elif info.filename.endswith("课程论文_提交版.pdf"):
                    zip_pdf_hash = compute_sha256_bytes(zf.read(info.filename))
                    
    root_docx_hash = compute_sha256(root_docx)
    root_pdf_hash = compute_sha256(root_pdf)
    staging_docx_hash = compute_sha256(staging_docx)
    staging_pdf_hash = compute_sha256(staging_pdf)
    
    hashes = {
        "root_docx": root_docx_hash,
        "root_pdf": root_pdf_hash,
        "staging_docx": staging_docx_hash,
        "staging_pdf": staging_pdf_hash,
        "zip_member_docx": zip_docx_hash,
        "zip_member_pdf": zip_pdf_hash,
        "root_matches_staging_docx": root_docx_hash == staging_docx_hash if root_docx_hash else False,
        "root_matches_zip_docx": root_docx_hash == zip_docx_hash if root_docx_hash else False,
        "root_matches_staging_pdf": root_pdf_hash == staging_pdf_hash if root_pdf_hash else False,
        "root_matches_zip_pdf": root_pdf_hash == zip_pdf_hash if root_pdf_hash else False,
    }
    
    with open(out_dir / "pre_fix_paper_hashes.json", "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2)
        
    print("Saved pre_fix_paper_hashes.json")
    
    if snap_pdf.exists():
        render_dir = out_dir / "pre_fix_render"
        render_dir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(str(snap_pdf))
        page_images = []
        for i in range(len(doc)):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=180)
            img_path = render_dir / f"page_{i+1:03d}.png"
            pix.save(str(img_path))
            page_images.append(img_path)
        
        write_contact_sheet(page_images, out_dir / "pre_fix_contact_sheet.png")
        print("Rendered pre-fix PDF.")

if __name__ == "__main__":
    gate_1()
