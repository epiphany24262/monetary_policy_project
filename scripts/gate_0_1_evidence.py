import hashlib
import json
import math
import shutil
import zipfile
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

ROOT = Path(r"D:\PyCharm\Quant\monetary_policy_project").resolve()

def compute_sha256(path: Path) -> str:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def gate_0():
    print("--- GATE 0 ---")
    sources = [
        ROOT / "output" / "results",
        ROOT / "data" / "processed",
        ROOT / "data" / "validation",
    ]
    hashes = {}
    for d in sources:
        if d.exists():
            for f in sorted(d.rglob("*")):
                if f.is_file() and not f.name.endswith(".gitkeep"):
                    hashes[str(f.relative_to(ROOT))] = compute_sha256(f)
    out_path = ROOT / "output" / "diagnostics" / "immutable_source_hashes.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(hashes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Computed {len(hashes)} immutable source hashes.")

def get_zip_member_hash(zip_path: Path, member_name: str) -> str:
    if not zip_path.exists():
        return None
    with zipfile.ZipFile(zip_path, "r") as zf:
        if member_name in zf.namelist():
            h = hashlib.sha256()
            with zf.open(member_name, "r") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
    return None

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
    print("--- GATE 1 ---")
    root_docx = ROOT / "paper" / "课程论文_提交版.docx"
    root_pdf = ROOT / "paper" / "课程论文_提交版.pdf"
    
    pre_fix_dir = ROOT / "output" / "diagnostics" / "pre_fix_snapshot"
    pre_fix_dir.mkdir(parents=True, exist_ok=True)
    
    if root_docx.exists():
        shutil.copy2(root_docx, pre_fix_dir / root_docx.name)
    if root_pdf.exists():
        shutil.copy2(root_pdf, pre_fix_dir / root_pdf.name)
        
    staging_docx = ROOT / "final_submission" / "paper" / "课程论文_提交版.docx"
    staging_pdf = ROOT / "final_submission" / "paper" / "课程论文_提交版.pdf"
    zip_path = ROOT / "delivery" / "final_submission.zip"
    
    hashes = {
        "root_docx": compute_sha256(root_docx),
        "root_pdf": compute_sha256(root_pdf),
        "staging_docx": compute_sha256(staging_docx),
        "staging_pdf": compute_sha256(staging_pdf),
        "zip_docx": get_zip_member_hash(zip_path, "final_submission/paper/课程论文_提交版.docx") or get_zip_member_hash(zip_path, "paper/课程论文_提交版.docx"),
        "zip_pdf": get_zip_member_hash(zip_path, "final_submission/paper/课程论文_提交版.pdf") or get_zip_member_hash(zip_path, "paper/课程论文_提交版.pdf")
    }
    
    hash_out = ROOT / "output" / "diagnostics" / "pre_fix_paper_hashes.json"
    hash_out.write_text(json.dumps(hashes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved pre-fix hashes to {hash_out}")
    
    render_dir = ROOT / "output" / "diagnostics" / "pre_fix_render"
    render_dir.mkdir(parents=True, exist_ok=True)
    
    if root_pdf.exists():
        print("Rendering pre-fix PDF...")
        doc = fitz.open(str(root_pdf))
        page_images = []
        for i in range(len(doc)):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=180)
            img_path = render_dir / f"page_{i+1:03d}.png"
            pix.save(str(img_path))
            page_images.append(img_path)
        write_contact_sheet(page_images, ROOT / "output" / "diagnostics" / "pre_fix_contact_sheet.png")
        print("Render complete.")

if __name__ == "__main__":
    gate_0()
    gate_1()
