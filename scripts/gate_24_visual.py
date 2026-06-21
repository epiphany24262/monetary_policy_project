import fitz
import math
from pathlib import Path
from PIL import Image
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def gate_24():
    pdf_path = PROJECT_ROOT / "paper" / "课程论文_提交版.pdf"
    if not pdf_path.exists():
        print("PDF not found!")
        return
        
    doc = fitz.open(str(pdf_path))
    out_dir = PROJECT_ROOT / "output" / "diagnostics" / "final_visual"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Save all pages as PNG
    images = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        img_path = out_dir / f"page_{i}.png"
        pix.save(str(img_path))
        images.append(Image.open(img_path))
        
        # also save page 1 (abstract page) specifically for easy viewing
        if i == 1:
            pix.save(str(out_dir / "abstract_page.png"))
            
    # Create contact sheet
    if images:
        width, height = images[0].size
        cols = 4
        rows = math.ceil(len(images) / cols)
        
        sheet = Image.new("RGB", (width * cols, height * rows), "white")
        
        for i, img in enumerate(images):
            col = i % cols
            row = i // cols
            sheet.paste(img, (col * width, row * height))
            
        sheet.save(str(out_dir / "contact_sheet.png"))
        print(f"Contact sheet saved to {out_dir / 'contact_sheet.png'}")

if __name__ == "__main__":
    gate_24()
