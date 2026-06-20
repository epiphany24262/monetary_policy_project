from __future__ import annotations

import csv
import shutil
from pathlib import Path

from ..paths import FINAL_SUBMISSION_DIR, ROOT


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_tree(src: Path, dst: Path, ignore=None) -> None:
    if dst.exists():
        shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)
    else:
        shutil.copytree(src, dst, ignore=ignore)


def _clear_submission_dir(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True)
        return
    for item in sorted(path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                item.rmdir()
        except OSError:
            # Windows may keep recently viewed files open. They are overwritten below
            # when possible and still checked by the final manifest gate.
            pass


COMMON_IGNORES = shutil.ignore_patterns(
    "__pycache__",
    ".pytest_cache",
    ".ipynb_checkpoints",
    "*.pyc",
    "*.pyo",
    "phase*.py",
    "test_phase*.py",
    "*phase*",
    "final_package_manifest.csv",
)


def build_final_submission() -> dict:
    _clear_submission_dir(FINAL_SUBMISSION_DIR)
    include_files = ["README.md", "requirements.txt", "run_all.py", "DATA_LICENSE_AND_REDISTRIBUTION.md"]
    for file in include_files:
        _copy_file(ROOT / file, FINAL_SUBMISSION_DIR / file)
    _copy_tree(ROOT / "configs", FINAL_SUBMISSION_DIR / "configs", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "src" / "monetary_policy", FINAL_SUBMISSION_DIR / "src" / "monetary_policy", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "scripts", FINAL_SUBMISSION_DIR / "scripts", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "tests", FINAL_SUBMISSION_DIR / "tests", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "notebooks", FINAL_SUBMISSION_DIR / "notebooks", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "paper", FINAL_SUBMISSION_DIR / "paper", ignore=COMMON_IGNORES)
    _copy_tree(
        ROOT / "research",
        FINAL_SUBMISSION_DIR / "research",
        ignore=shutil.ignore_patterns("*FEASIBILITY*", "*SOURCE_DECISION*", "*JOURNAL_TEMPLATE*", "REFACTOR_*", "__pycache__", "*.pyc"),
    )
    for rel in ["data/processed", "data/dictionaries", "data/source_registry.csv", "output/figures", "output/tables", "output/results"]:
        src = ROOT / rel
        dst = FINAL_SUBMISSION_DIR / rel
        if src.is_dir():
            _copy_tree(
                src,
                dst,
                ignore=shutil.ignore_patterns(
                    "primary",
                    "__pycache__",
                    ".pytest_cache",
                    "*.pyc",
                    "*.pyo",
                    "*phase*",
                    "*gate*",
                    "*diagnostic*",
                    "*notebook_execution_refactor.json",
                    "*pdf_visual*",
                ),
            )
        elif src.exists():
            _copy_file(src, dst)
    manifest_rows = []
    forbidden_parts = {".codex", "archive", "phases", "prompts", "output/diagnostics"}
    for path in sorted(p for p in FINAL_SUBMISSION_DIR.rglob("*") if p.is_file()):
        rel = path.relative_to(FINAL_SUBMISSION_DIR).as_posix()
        manifest_rows.append({"path": rel, "bytes": path.stat().st_size})
        lower_name = Path(rel).name.lower()
        if (
            any(rel.startswith(part) for part in forbidden_parts)
            or "phase" in lower_name
            or lower_name.endswith((".pyc", ".pyo"))
            or "__pycache__" in rel
            or ".pytest_cache" in rel
        ):
            raise RuntimeError(f"Forbidden file in final submission: {rel}")
    delivery = ROOT / "delivery"
    delivery.mkdir(exist_ok=True)
    stale_manifest = delivery / "final_package_manifest.csv"
    if stale_manifest.exists():
        stale_manifest.unlink()
    manifest_path = FINAL_SUBMISSION_DIR / "final_package_manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "bytes"])
        writer.writeheader()
        writer.writerows(manifest_rows)
    with (delivery / "FINAL_SUBMISSION_MANIFEST.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "bytes"])
        writer.writeheader()
        writer.writerows(manifest_rows)
    (delivery / "FINAL_SUBMISSION_README.md").write_text(
        "# 最终提交包说明\n\n"
        "`final_submission/` 是面向课程教师的精简提交目录，排除了提示词工程、内部审计日志、历史归档和原始许可不确定数据。\n\n"
        "复现命令：\n\n"
        "```bash\npython -m venv .venv\n.venv\\Scripts\\python -m pip install -r requirements.txt\n.venv\\Scripts\\python run_all.py --offline\n.venv\\Scripts\\python -m pytest -q\n```\n",
        encoding="utf-8",
    )
    return {"included_files": len(manifest_rows), "manifest": "final_submission/final_package_manifest.csv"}
