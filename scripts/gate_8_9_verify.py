import fitz
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def gate_8_9():
    pdf_path = PROJECT_ROOT / "paper" / "课程论文_提交版.pdf"
    if not pdf_path.exists():
        print("PDF not found!")
        return

    doc = fitz.open(str(pdf_path))
    
    ref_heading_text = None
    ref_heading_font = None
    ref_heading_size = None
    ref_heading_flags = None
    ref_heading_bbox = None
    ref_heading_alignment = None
    ref_heading_additional_bold = False
    
    target_page = None
    target_page_idx = None
    
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        text = s["text"].strip()
                        if "参考文献" in text:
                            ref_heading_text = text
                            ref_heading_font = s["font"]
                            ref_heading_size = s["size"]
                            ref_heading_flags = s["flags"]
                            ref_heading_bbox = s["bbox"]
                            target_page = page
                            target_page_idx = page_num
                            break
                    if ref_heading_text: break
            if ref_heading_text: break
        if ref_heading_text: break

    if ref_heading_text:
        # Check alignment: if x0 is less than 150 (approx 2 chars from left margin), it is left-aligned.
        # PAGE_STYLE left margin is 2.5cm which is ~70 points.
        is_left_aligned = ref_heading_bbox[0] < 100
        ref_heading_alignment = "left" if is_left_aligned else "center/right"
        
        # Check bold: Bit 4 (value 16) corresponds to superscript? Actually bit 4 (16) is bold in PyMuPDF flags.
        # But wait, SimHei is already black.
        is_bold = bool(ref_heading_flags & 2**4)
        ref_heading_additional_bold = is_bold
        
        results = {
            "references_heading_text": ref_heading_text,
            "references_heading_font": ref_heading_font,
            "references_heading_size": round(ref_heading_size, 1),
            "references_heading_flags": ref_heading_flags,
            "references_heading_bbox": ref_heading_bbox,
            "references_heading_alignment": ref_heading_alignment,
            "references_heading_additional_bold": ref_heading_additional_bold
        }
        
        out_dir = PROJECT_ROOT / "output" / "diagnostics"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "final_paper_validation.json"
        
        # Save image
        pix = target_page.get_pixmap(dpi=150)
        pix.save(str(out_dir / "final_references_verified.png"))
        
        # Load or create final_paper_validation.json
        if out_file.exists():
            with open(out_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
            
        data.update(results)
        
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        print("Gate 8/9 Verification complete.")
        print(json.dumps(results, indent=2))
        
        assert "Hei" in ref_heading_font or "黑" in ref_heading_font, f"Expected Heiti-style font, got {ref_heading_font}"
        assert 8.5 <= round(ref_heading_size, 1) <= 9.5, f"Expected size ~9.0, got {ref_heading_size}"
        assert is_left_aligned, "Heading is not left aligned."
        assert not ref_heading_additional_bold, "Heading should not have mechanical bold."
    else:
        print("References heading not found in PDF!")

if __name__ == "__main__":
    gate_8_9()
