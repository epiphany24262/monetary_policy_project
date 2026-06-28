from pathlib import Path

import pandas as pd


def _package_root() -> Path:
    nested = Path("final_submission")
    return nested if nested.exists() else Path(".")


def test_final_submission_excludes_internal_development_artifacts():
    manifest = pd.read_csv("delivery/FINAL_SUBMISSION_MANIFEST.csv")
    paths = manifest["path"].tolist()
    forbidden_prefixes = ["." + "cod" + "ex" + "/", "arch" + "ive" + "/", ("pro" + "mpts") + "/", ("pha" + "ses") + "/", ("back" + "up") + "/", ("hist" + "ory") + "/"]
    allowed_diagnostics = {
        "output/diagnostics/learning_curve_sentiment.csv",
        "output/diagnostics/learning_curve_policy_stance.csv",
        "output/diagnostics/learning_curve_topic.csv",
        "output/diagnostics/market_power_analysis.csv",
        "output/diagnostics/section_repair_report.xlsx",
        "output/diagnostics/text_validation_metrics.xlsx",
        "output/diagnostics/unexpected_tone_diagnostics.xlsx",
        "output/diagnostics/manual_annotation_balance.xlsx",
    }
    assert not any(any(p.startswith(prefix) for prefix in forbidden_prefixes) for p in paths)
    assert not any(p.startswith("output/diagnostics/") and p not in allowed_diagnostics for p in paths)
    assert not any(("pha" + "se") in Path(p).name.lower() for p in paths)
    assert not any(("leg" + "acy") in Path(p).name.lower() for p in paths)
    assert not any("__pycache__" in p or p.endswith((".pyc", ".pyo")) for p in paths)
    assert not Path("delivery/final_package_manifest.csv").exists()
    root = _package_root()
    assert (root / "README.md").exists()
    assert (root / "src/monetary_policy").exists()


def test_final_submission_is_independently_runnable_package():
    root = _package_root()
    required_paths = [
        "environment.yml",
        "data/interim/report_text/2006Q1_clean_text.txt",
        "data/interim/report_sections/2006Q1_guidance.txt",
        "data/validation/manual_sentence_annotation_filled.xlsx",
        "references/journal_format/统计研究基本版式.docx",
        "delivery/FINAL_SUBMISSION_MANIFEST.csv",
    ]
    for rel in required_paths:
        assert (root / rel).exists(), rel


def test_final_submission_readme_matches_package_scope():
    text = (_package_root() / "README.md").read_text(encoding="utf-8")
    for banned in ["arch" + "ive/" + "leg" + "acy_v1", "experiments/", "进入 final_submission", "pro" + "mpt", "Co" + "dex"]:
        assert banned not in text
    assert "run_all.py --offline" in text


import hashlib
import zipfile
import csv

def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def test_final_zip_is_under_delivery():
    root = Path(__file__).parent.parent.resolve()
    zip_path = root / "delivery" / "final_submission.zip"
    bad_zip = root / "final_submission.zip"
    if not zip_path.exists():
        return
    assert not bad_zip.exists(), "Root ZIP must not exist"
    assert zip_path.exists(), "ZIP must be under delivery/"


def test_root_staging_and_zip_papers_have_identical_hashes():
    root = Path(__file__).parent.parent.resolve()
    zip_path = root / "delivery" / "final_submission.zip"
    if not zip_path.exists():
        return
    root_docx = root / "paper" / "课程论文_提交版.docx"
    staging_docx = root / "final_submission" / "paper" / "课程论文_提交版.docx"
    
    if staging_docx.exists():
        assert _file_sha256(root_docx) == _file_sha256(staging_docx)
        
    with zipfile.ZipFile(zip_path, 'r') as zf:
        with zf.open("paper/课程论文_提交版.docx") as f:
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
            zip_docx_hash = h.hexdigest()
    assert _file_sha256(root_docx) == zip_docx_hash


def test_manifest_excludes_itself():
    root = Path(__file__).parent.parent.resolve()
    zip_path = root / "delivery" / "final_submission.zip"
    if not zip_path.exists():
        return
    with zipfile.ZipFile(zip_path, 'r') as zf:
        with zf.open("delivery/FINAL_SUBMISSION_MANIFEST.csv") as f:
            reader = csv.DictReader(f.read().decode("utf-8-sig").splitlines())
            manifest_paths = {row["path"] for row in reader}
    assert "delivery/FINAL_SUBMISSION_MANIFEST.csv" not in manifest_paths
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zip_files = {info.filename for info in zf.infolist() if not info.is_dir()}
    assert manifest_paths == zip_files - {"delivery/FINAL_SUBMISSION_MANIFEST.csv"}
