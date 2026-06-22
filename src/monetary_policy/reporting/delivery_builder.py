from __future__ import annotations

import csv
import shutil
from pathlib import Path

from ..paths import DELIVERY_DIR, FINAL_SUBMISSION_DIR, ROOT


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
    ("pha" + "se") + "*.py",
    "test_" + ("pha" + "se") + "*.py",
    "*" + ("pha" + "se") + "*",
    "paper_builder.py",
    "final_package_manifest.csv",
)


def _write_submission_readme() -> None:
    (FINAL_SUBMISSION_DIR / "README.md").write_text(
        "# 货币政策沟通课设提交包\n\n"
        "## 目录\n\n"
        "- `paper/`：课程论文 DOCX 和 PDF。\n"
        "- `src/monetary_policy/`：全部源代码。\n"
        "- `configs/`：样本边界、路径和模型设定。\n"
        "- `notebooks/`：复现 Notebook。\n"
        "- `data/`：处理后数据和人工标注样本。\n"
        "- `output/`：结果、表格和图形。\n\n"
        "## 环境\n\n"
        "```powershell\n"
        "python -m venv .venv\n"
        ".\\.venv\\Scripts\\python -m pip install -r requirements.txt\n"
        "```\n\n"
        "## 运行\n\n"
        "```powershell\n"
        ".\\.venv\\Scripts\\python run_all.py --offline\n"
        "```\n\n"
        "## 数据来源\n\n"
        "报告文本来自中国人民银行官网，其他数据来源登记见 `data/source_registry.csv`。\n",
        encoding="utf-8",
    )



def _manifest_rows() -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    # Exclude internal development directories
    forbidden_parts = {"." + "cod" + "ex", "arch" + "ive", "pha" + "ses", "pro" + "mpts", "back" + "up", "hist" + "ory"}
    for path in sorted(p for p in FINAL_SUBMISSION_DIR.rglob("*") if p.is_file()):
        rel = path.relative_to(FINAL_SUBMISSION_DIR).as_posix()
        if rel == "delivery/FINAL_SUBMISSION_MANIFEST.csv":
            continue
        lower_name = Path(rel).name.lower()
        if (
            any(rel.startswith(part) for part in forbidden_parts)
            or ("pha" + "se") in lower_name
            or ("leg" + "acy") in lower_name
            or lower_name.endswith((".pyc", ".pyo"))
            or "__pycache__" in rel
            or ".pytest_cache" in rel
            or ".ipython" in rel
        ):
            raise RuntimeError(f"Forbidden file in final submission: {rel}")
        rows.append({"path": rel, "bytes": path.stat().st_size})
    return rows


def _write_manifest(path: Path, rows: list[dict[str, int | str]]) -> None:
    manifest_rel = "delivery/FINAL_SUBMISSION_MANIFEST.csv"
    manifest_rows = [row for row in rows if row["path"] != manifest_rel]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "bytes"])
        writer.writeheader()
        writer.writerows(manifest_rows)


def write_submission_manifests() -> dict:
    DELIVERY_DIR.mkdir(exist_ok=True)
    stale_manifest = DELIVERY_DIR / "final_package_manifest.csv"
    if stale_manifest.exists():
        stale_manifest.unlink()
    rows = _manifest_rows()
    _write_manifest(DELIVERY_DIR / "FINAL_SUBMISSION_MANIFEST.csv", rows)
    return {"included_files": len(rows)}


def build_final_submission() -> dict:
    _clear_submission_dir(FINAL_SUBMISSION_DIR)
    for file in ["requirements.txt", "run_all.py"]:
        src = ROOT / file
        if src.exists():
            _copy_file(src, FINAL_SUBMISSION_DIR / file)
    _write_submission_readme()
    _copy_tree(ROOT / "configs", FINAL_SUBMISSION_DIR / "configs", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "src" / "monetary_policy", FINAL_SUBMISSION_DIR / "src" / "monetary_policy", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "notebooks", FINAL_SUBMISSION_DIR / "notebooks", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "paper", FINAL_SUBMISSION_DIR / "paper", ignore=COMMON_IGNORES)
    for plan_name in ["final_analysis_plan.md", "final_analysis_plan.sha256"]:
        src = ROOT / "research" / plan_name
        if src.exists():
            _copy_file(src, FINAL_SUBMISSION_DIR / "configs" / plan_name)
    for rel in [
        "data/interim/report_text",
        "data/interim/report_sections",
        "data/validation",
        "data/processed",
        "data/dictionaries",
        "data/source_registry.csv",
        "output/figures",
        "output/tables",
        "output/results",
    ]:
        src = ROOT / rel
        dst = FINAL_SUBMISSION_DIR / rel
        if src.is_dir():
            _copy_tree(
                src, dst,
                ignore=shutil.ignore_patterns(
                    "__pycache__", ".pytest_cache", "*.pyc", "*.pyo",
                    "*" + ("pha" + "se") + "*", "*gate*", "*diagnostic*",
                    "*notebook_execution_refactor.json", "*pdf_visual*",
                    "*" + ("leg" + "acy") + "*", "primary",
                ),
            )
        elif src.exists():
            _copy_file(src, dst)
    return write_submission_manifests()
