import json
import re
from pathlib import Path
from docx import Document
import fitz

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PHRASE = "A Student-t EGARCH-X model estimated on the full daily return sequence"
FORBIDDEN_PHRASE = "EGARCH-X 模型"

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def extract_docx_english_abstract(path: Path) -> str:
    if not path.exists():
        return ""
    doc = Document(path)
    parts = []
    collecting = False
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text.startswith("Abstract:"):
            collecting = True
            parts.append(text)
            continue
        if collecting and text.startswith("Key words:"):
            break
        if collecting and text:
            parts.append(text)
    return normalize_space(" ".join(parts))

def extract_pdf_english_abstract(path: Path) -> str:
    if not path.exists():
        return ""
    doc = fitz.open(str(path))
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    
    m = re.search(r"Abstract:(.*?)(?:Key words:|Keywords:)", text, re.DOTALL)
    if m:
        extracted = "Abstract:" + m.group(1)
        return normalize_space(extracted)
    return ""

def gate_2():
    out_dir = PROJECT_ROOT / "output" / "diagnostics"
    snap_docx = out_dir / "pre_fix_snapshot" / "课程论文_提交版_pre_fix.docx"
    snap_pdf = out_dir / "pre_fix_snapshot" / "课程论文_提交版_pre_fix.pdf"
    
    docx_text = extract_docx_english_abstract(snap_docx)
    pdf_text = extract_pdf_english_abstract(snap_pdf)
    
    has_chinese_docx = bool(re.search(r"[\u4e00-\u9fa5]", docx_text))
    has_chinese_pdf = bool(re.search(r"[\u4e00-\u9fa5]", pdf_text))
    
    expected_docx = EXPECTED_PHRASE in docx_text
    expected_pdf = EXPECTED_PHRASE in pdf_text
    
    forbidden_docx = FORBIDDEN_PHRASE in docx_text
    forbidden_pdf = FORBIDDEN_PHRASE in pdf_text
    
    docx_pass = expected_docx and not forbidden_docx and not has_chinese_docx
    pdf_pass = expected_pdf and not forbidden_pdf and not has_chinese_pdf
    
    result = {
        "snapshot_docx": str(snap_docx.name),
        "snapshot_pdf": str(snap_pdf.name),
        "expected_phrase_present_in_docx": expected_docx,
        "expected_phrase_present_in_pdf": expected_pdf,
        "forbidden_phrase_present_in_docx": forbidden_docx,
        "forbidden_phrase_present_in_pdf": forbidden_pdf,
        "has_chinese_docx": has_chinese_docx,
        "has_chinese_pdf": has_chinese_pdf,
        "docx_validation_result": "PASS" if docx_pass else "FAIL",
        "pdf_validation_result": "PASS" if pdf_pass else "FAIL"
    }
    
    with open(out_dir / "pre_fix_english_abstract_validation.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        
    print(f"Before source fix: {'PASS' if docx_pass and pdf_pass else 'FAIL'}")

if __name__ == "__main__":
    gate_2()
