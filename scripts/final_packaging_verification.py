import os
import sys
import json
import csv
import shutil
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(r"D:\PyCharm\Quant\monetary_policy_project").resolve()

def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def zip_member_sha256(zip_path: Path, member_name: str) -> str:
    with zipfile.ZipFile(zip_path, 'r') as zf:
        with zf.open(member_name) as f:
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
            return h.hexdigest()

def main():
    # 2. First verify the latest root paper
    root_docx = ROOT / "paper" / "课程论文_提交版.docx"
    root_pdf = ROOT / "paper" / "课程论文_提交版.pdf"
    
    hashes = {}
    for p in [root_docx, root_pdf]:
        hashes[p.relative_to(ROOT).as_posix()] = {
            "sha256": file_sha256(p),
            "bytes": p.stat().st_size,
            "mtime": str(p.stat().st_mtime)
        }
    
    diag_dir = ROOT / "output" / "diagnostics"
    diag_dir.mkdir(parents=True, exist_ok=True)
    with (diag_dir / "final_packaging_root_hashes.json").open("w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, ensure_ascii=False)

    # 3. Delete stale packaging outputs
    stale_dirs = [ROOT / "final_submission"]
    stale_files = [ROOT / "final_submission.zip", ROOT / "delivery" / "final_submission.zip"]
    
    for d in stale_dirs:
        assert d.resolve().is_relative_to(ROOT)
        if d.exists():
            shutil.rmtree(d)
            
    for f in stale_files:
        assert f.resolve().is_relative_to(ROOT)
        if f.exists():
            f.unlink()

    # 5. Rebuild final_submission after the paper is already final
    sys.path.insert(0, str(ROOT / "src"))
    from monetary_policy.reporting.delivery_builder import build_final_submission
    result = build_final_submission()
    print("build_final_submission result:", result)
    
    staging_docx = ROOT / "final_submission" / "paper" / "课程论文_提交版.docx"
    staging_pdf = ROOT / "final_submission" / "paper" / "课程论文_提交版.pdf"
    
    assert file_sha256(root_docx) == file_sha256(staging_docx)
    assert file_sha256(root_pdf) == file_sha256(staging_pdf)

    # 6. Verify that staging contains the latest modified source files
    check_files = [
        "paper/课程论文_提交版.docx",
        "paper/课程论文_提交版.pdf",
        "src/monetary_policy/reporting/journal_paper_builder.py",
        "src/monetary_policy/reporting/journal_style.py",
        "src/monetary_policy/reporting/journal_tables.py",
        "src/monetary_policy/reporting/journal_figures.py",
        "src/monetary_policy/reporting/delivery_builder.py",
        "notebooks/货币政策沟通与金融市场反应.ipynb"
    ]
    
    hash_check_rows = []
    for rel_path in check_files:
        r = ROOT / rel_path
        s = ROOT / "final_submission" / rel_path
        r_hash = file_sha256(r)
        s_hash = file_sha256(s)
        hash_check_rows.append({
            "path": rel_path,
            "root_sha256": r_hash,
            "staging_sha256": s_hash,
            "match": r_hash == s_hash,
            "root_bytes": r.stat().st_size,
            "staging_bytes": s.stat().st_size
        })
        assert r_hash == s_hash, f"Hash mismatch for {rel_path}"
        
    with (diag_dir / "final_packaging_staging_hash_check.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "root_sha256", "staging_sha256", "match", "root_bytes", "staging_bytes"])
        writer.writeheader()
        writer.writerows(hash_check_rows)

    # 7. Build the ZIP in delivery, not at the project root
    FINAL_SUBMISSION_DIR = ROOT / "final_submission"
    DELIVERY_DIR = ROOT / "delivery"
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    zip_base = DELIVERY_DIR / "final_submission"
    zip_path = Path(shutil.make_archive(
        base_name=str(zip_base),
        format="zip",
        root_dir=str(FINAL_SUBMISSION_DIR),
    ))

    # 8. Byte-level verification inside the ZIP
    assert zip_member_sha256(zip_path, "paper/课程论文_提交版.docx") == file_sha256(root_docx)
    assert zip_member_sha256(zip_path, "paper/课程论文_提交版.pdf") == file_sha256(root_pdf)
    assert zip_member_sha256(zip_path, "src/monetary_policy/reporting/journal_paper_builder.py") == file_sha256(ROOT / "src/monetary_policy/reporting/journal_paper_builder.py")

    # 9. Compare ZIP contents with the staging directory
    staging_files = set()
    for p in FINAL_SUBMISSION_DIR.rglob("*"):
        if p.is_file():
            staging_files.add(p.relative_to(FINAL_SUBMISSION_DIR).as_posix())
            
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zip_files = set(info.filename for info in zf.infolist() if not info.is_dir())
        
    assert staging_files == zip_files, "Staging files do not match ZIP files"
    
    manifest_paths = set()
    with zipfile.ZipFile(zip_path, 'r') as zf:
        with zf.open("delivery/FINAL_SUBMISSION_MANIFEST.csv") as f:
            reader = csv.DictReader(f.read().decode("utf-8-sig").splitlines())
            for row in reader:
                manifest_paths.add(row["path"])
                
    assert manifest_paths == zip_files - {"delivery/FINAL_SUBMISSION_MANIFEST.csv"}
    
    # 10. Remove accidental root ZIP
    bad_zip = ROOT / "final_submission.zip"
    if bad_zip.exists():
        bad_zip.unlink()

    # Create the report
    report = {
        "1. Root DOCX SHA256": file_sha256(root_docx),
        "2. Staging DOCX SHA256": file_sha256(staging_docx),
        "3. ZIP DOCX SHA256": zip_member_sha256(zip_path, "paper/课程论文_提交版.docx"),
        "4. Root PDF SHA256": file_sha256(root_pdf),
        "5. Staging PDF SHA256": file_sha256(staging_pdf),
        "6. ZIP PDF SHA256": zip_member_sha256(zip_path, "paper/课程论文_提交版.pdf"),
        "7. All six hashes match in their respective groups": (
            file_sha256(root_docx) == file_sha256(staging_docx) == zip_member_sha256(zip_path, "paper/课程论文_提交版.docx") and
            file_sha256(root_pdf) == file_sha256(staging_pdf) == zip_member_sha256(zip_path, "paper/课程论文_提交版.pdf")
        ),
        "8. Staging file count": len(staging_files),
        "9. ZIP file count": len(zip_files),
        "10. Manifest row count": len(manifest_paths),
        "11. Manifests found inside ZIP": [f for f in zip_files if "manifest" in f.lower()],
        "12. Root-level accidental ZIP existence": bad_zip.exists(),
        "15. Final ZIP absolute path": str(zip_path.resolve()),
        "16. Final ZIP size": zip_path.stat().st_size
    }
    
    with (ROOT / "output" / "diagnostics" / "final_packaging_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    for k, v in report.items():
        print(f"{k}: {v}")

if __name__ == '__main__':
    main()
