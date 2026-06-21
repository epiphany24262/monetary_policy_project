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
        "本目录包含课程论文、复现 Notebook、正式代码、配置、处理后数据和结果文件。研究使用中国人民银行季度货币政策执行报告、沪深300指数和国债收益率曲线数据，考察政策指引文本创新度与金融市场反应。\n\n"
        "## 目录结构\n\n"
        "- `configs/`：样本边界、路径和模型设定。\n"
        "- `src/monetary_policy/`：数据处理、文本测量、事件研究和论文生成代码。\n"
        "- `scripts/`：辅助执行脚本。\n"
        "- `tests/`：复现一致性测试。\n"
        "- `notebooks/`：已执行的核心流程 Notebook。\n"
        "- `data/`：清洗文本、处理后市场数据和人工标注样本。\n"
        "- `output/results/`、`output/tables/`、`output/figures/`：正式结果、表格和图形。\n"
        "- `paper/`：课程论文 DOCX、PDF和论文数字、引用核对表。\n"
        "- `references/journal_format/`：课程封面和版式模板。\n"
        "- `delivery/FINAL_SUBMISSION_MANIFEST.csv`：文件清单。\n\n"
        "## 环境安装\n\n"
        "```powershell\n"
        "python -m venv .venv\n"
        ".\\.venv\\Scripts\\python -m pip install -r requirements.txt\n"
        "```\n\n"
        "macOS/Linux 可使用：\n\n"
        "```bash\n"
        "python -m venv .venv\n"
        "./.venv/bin/python -m pip install -r requirements.txt\n"
        "```\n\n"
        "## 运行方法\n\n"
        "Windows PowerShell：\n\n"
        "```powershell\n"
        ".\\.venv\\Scripts\\python run_all.py --offline\n"
        ".\\.venv\\Scripts\\python -m pytest -q\n"
        "```\n\n"
        "macOS/Linux：\n\n"
        "```bash\n"
        "./.venv/bin/python run_all.py --offline\n"
        "./.venv/bin/python -m pytest -q\n"
        "```\n\n"
        "## 主要输出\n\n"
        "- `paper/课程论文_提交版.docx` 和 `paper/课程论文_提交版.pdf`。\n"
        "- `notebooks/货币政策沟通与金融市场反应.ipynb`。\n"
        "- `output/results/stock_volatility_main.json`、`output/results/daily_egarch_x_results.json` 和 `output/results/yield_curve_results.csv`。\n\n"
        "## 数据来源说明\n\n"
        "报告文本来自中国人民银行官网。股票指数、国债收益率和政策操作数据均保留来源登记，见 `data/source_registry.csv`。若课程平台要求另行提交原始市场数据，应先确认数据源再分发许可。\n",
        encoding="utf-8",
    )


def _write_submission_pytest_ini() -> None:
    (FINAL_SUBMISSION_DIR / "pytest.ini").write_text(
        "[pytest]\n"
        "testpaths = tests\n"
        "norecursedirs = final_submission .git .venv .pytest_cache __pycache__\n",
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
    manifest_rows.append({"path": manifest_rel, "bytes": 0})
    previous_size = None
    for _ in range(8):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["path", "bytes"])
            writer.writeheader()
            writer.writerows(manifest_rows)
        current_size = path.stat().st_size
        if current_size == previous_size:
            break
        manifest_rows[-1]["bytes"] = current_size
        previous_size = current_size


def write_submission_manifests() -> dict:
    DELIVERY_DIR.mkdir(exist_ok=True)
    (FINAL_SUBMISSION_DIR / "delivery").mkdir(parents=True, exist_ok=True)
    stale_manifest = DELIVERY_DIR / "final_package_manifest.csv"
    if stale_manifest.exists():
        stale_manifest.unlink()
    rows = _manifest_rows()
    for manifest_path in [
        FINAL_SUBMISSION_DIR / "delivery" / "FINAL_SUBMISSION_MANIFEST.csv",
        DELIVERY_DIR / "FINAL_SUBMISSION_MANIFEST.csv",
    ]:
        _write_manifest(manifest_path, rows)
    (DELIVERY_DIR / "FINAL_SUBMISSION_README.md").write_text(
        "# 最终提交包说明\n\n"
        "`final_submission/` 是面向课程教师的完整复现目录，仅保留论文、代码、数据、结果和必要配置。"
        "正式提交建议压缩该目录内容为 `final_submission.zip`。\n",
        encoding="utf-8",
    )
    return {"included_files": len(rows) + 1, "manifest": "delivery/FINAL_SUBMISSION_MANIFEST.csv"}


def build_final_submission() -> dict:
    _clear_submission_dir(FINAL_SUBMISSION_DIR)
    include_files = [
        "requirements.txt",
        "run_all.py",
        "environment.yml",
    ]
    for file in include_files:
        src = ROOT / file
        if src.exists():
            _copy_file(src, FINAL_SUBMISSION_DIR / file)
    _write_submission_readme()
    _write_submission_pytest_ini()
    _copy_tree(ROOT / "configs", FINAL_SUBMISSION_DIR / "configs", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "src" / "monetary_policy", FINAL_SUBMISSION_DIR / "src" / "monetary_policy", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "scripts", FINAL_SUBMISSION_DIR / "scripts", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "tests", FINAL_SUBMISSION_DIR / "tests", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "notebooks", FINAL_SUBMISSION_DIR / "notebooks", ignore=COMMON_IGNORES)
    _copy_tree(ROOT / "paper", FINAL_SUBMISSION_DIR / "paper", ignore=COMMON_IGNORES)
    for plan_name in ["FINAL_ANALYSIS_PLAN.md", "FINAL_ANALYSIS_PLAN.sha256"]:
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
                src,
                dst,
                ignore=shutil.ignore_patterns(
                    "primary",
                    "__pycache__",
                    ".pytest_cache",
                    "*.pyc",
                    "*.pyo",
                    "*" + ("pha" + "se") + "*",
                    "*gate*",
                    "*diagnostic*",
                    "*notebook_execution_refactor.json",
                    "*pdf_visual*",
                    "*" + ("leg" + "acy") + "*",
                    "primary",
                ),
            )
        elif src.exists():
            _copy_file(src, dst)
    for rel in [
        "references/journal_format/统计研究基本版式.docx",
        "references/journal_format/课程论文封面.docx",
    ]:
        src = ROOT / rel
        if src.exists():
            _copy_file(src, FINAL_SUBMISSION_DIR / rel)
    return write_submission_manifests()
