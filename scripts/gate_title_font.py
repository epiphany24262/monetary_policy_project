import json
from pathlib import Path
import fitz

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def gate_13():
    pdf_path = PROJECT_ROOT / "paper" / "课程论文_提交版.pdf"
    if not pdf_path.exists():
        print("PDF not found")
        return
        
    doc = fitz.open(str(pdf_path))
    
    title_fonts = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        text = s["text"].strip()
                        if "中国货币政策报告" in text:
                            title_fonts.append({"page": page_num, "text": text, "font": s["font"]})
        
    result = {
        "title_string": "中国货币政策报告文本特征与金融市场反应",
        "embedded_font_name": title_fonts
    }
    
    out_dir = PROJECT_ROOT / "output" / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "final_title_font_verification.json"
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        
    print(f"Title font: {title_font}")
    doc.close()

if __name__ == "__main__":
    gate_13()
