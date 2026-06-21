import re
import fitz
import pytest
from pathlib import Path
from docx import Document

def get_root():
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()

ROOT = get_root()

PRE_FIX_DOCX = ROOT / "output" / "diagnostics" / "pre_fix_snapshot" / "课程论文_提交版.docx"
PRE_FIX_PDF = ROOT / "output" / "diagnostics" / "pre_fix_snapshot" / "课程论文_提交版.pdf"
PAPER_DOCX = ROOT / "paper" / "课程论文_提交版.docx"
PAPER_PDF = ROOT / "paper" / "课程论文_提交版.pdf"

def extract_docx_abstract(docx_path):
    if not docx_path.exists():
        return ""
    doc = Document(str(docx_path))
    in_abstract = False
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text.startswith("Abstract:"):
            in_abstract = True
            lines.append(text)
        elif text.startswith("Key words:"):
            break
        elif in_abstract and text:
            lines.append(text)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()

def extract_pdf_abstract(pdf_path):
    if not pdf_path.exists():
        return ""
    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    
    # Simple extraction between Abstract: and Key words:
    m = re.search(r"Abstract:(.*?)(?:Key words:|Keywords:)", text, re.DOTALL)
    if m:
        extracted = "Abstract:" + m.group(1)
        return re.sub(r"\s+", " ", extracted).strip()
    return ""

def test_pre_fix_english_abstract_fails():
    """Verify that the pre-fix snapshot indeed contains the bug."""
    if not PRE_FIX_DOCX.exists():
        pytest.skip("Pre-fix snapshot not found")
        
    docx_text = extract_docx_abstract(PRE_FIX_DOCX)
    assert docx_text, "Abstract not found in pre-fix DOCX"
    
    # The pre-fix abstract should fail the test (i.e. contains Chinese and 'EGARCH-X 模型')
    has_chinese = bool(re.findall(r"[\u4e00-\u9fff]", docx_text))
    has_mixed = "EGARCH-X 模型" in docx_text
    
    # This test PASSES if the defective snapshot fails the validation.
    assert has_chinese and has_mixed, "Before source fix: FAIL (Snapshot does not contain expected bug)"

def test_docx_english_abstract_is_english_only():
    if not PAPER_DOCX.exists():
        pytest.skip("DOCX not found")
    docx_text = extract_docx_abstract(PAPER_DOCX)
    assert docx_text, "Abstract not found"
    chinese = re.findall(r"[\u4e00-\u9fff]", docx_text)
    assert not chinese, f"DOCX abstract contains Chinese: {chinese}"

def test_pdf_english_abstract_is_english_only():
    if not PAPER_PDF.exists():
        pytest.skip("PDF not found")
    pdf_text = extract_pdf_abstract(PAPER_PDF)
    assert pdf_text, "Abstract not found"
    chinese = re.findall(r"[\u4e00-\u9fff]", pdf_text)
    assert not chinese, f"PDF abstract contains Chinese: {chinese}"

def test_expected_egarch_sentence_exists():
    if not PAPER_DOCX.exists():
        pytest.skip("DOCX not found")
    docx_text = extract_docx_abstract(PAPER_DOCX)
    expected = "A Student-t EGARCH-X model estimated on the full daily return sequence"
    assert expected in docx_text, f"Expected phrase not found in DOCX abstract"
    
    if PAPER_PDF.exists():
        pdf_text = extract_pdf_abstract(PAPER_PDF)
        assert expected in pdf_text, f"Expected phrase not found in PDF abstract"

def test_forbidden_mixed_phrase_absent():
    if not PAPER_DOCX.exists():
        pytest.skip("DOCX not found")
    docx_text = extract_docx_abstract(PAPER_DOCX)
    forbidden = "EGARCH-X 模型"
    assert forbidden not in docx_text, f"Forbidden phrase '{forbidden}' found in DOCX abstract"
    
    if PAPER_PDF.exists():
        pdf_text = extract_pdf_abstract(PAPER_PDF)
        assert forbidden not in pdf_text, f"Forbidden phrase '{forbidden}' found in PDF abstract"
