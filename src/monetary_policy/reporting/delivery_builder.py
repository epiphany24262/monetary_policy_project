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
    "phase*.py",
    "test_phase*.py",
    "*phase*",
    "final_package_manifest.csv",
)


def _write_submission_readme() -> None:
    (FINAL_SUBMISSION_DIR / "README.md").write_text(
        "# 货币政策沟通课设最终提交包\n\n"
        "本目录是可独立复现的课程提交包，包含正式代码、配置、处理后数据、人工验证样本、论文、Notebook、图表、结果表和提交清单。\n\n"
        "## 目录\n\n"
        "- `src/monetary_policy/`：正式源码。\n"
        "- `configs/`：样本边界、路径和分析窗口配置。\n"
        "- `data/interim/`：清洗后的央行报告全文和章节文本。\n"
        "- `data/processed/`：正式文本特征、事件面板和市场数据。\n"
        "- `data/validation/`：人工句子标注与填报文件。\n"
        "- `references/journal_format/`：课程封面和《统计研究》版式模板。\n"
        "- `output/`：正式结果、图表、表格和诊断材料。\n"
        "- `paper/`：课程论文 DOCX、PDF、数字审计和引用审计。\n"
        "- `notebooks/`：已执行的复现 Notebook。\n"
        "- `delivery/FINAL_SUBMISSION_MANIFEST.csv`：提交包文件清单。\n\n"
        "## 复现命令\n\n"
        "Windows PowerShell：\n\n"
        "```powershell\n"
        "python -m venv .venv\n"
        ".\\.venv\\Scripts\\python -m pip install -r requirements.txt\n"
        ".\\.venv\\Scripts\\python run_all.py --offline\n"
        ".\\.venv\\Scripts\\python -m pytest -q\n"
        "```\n\n"
        "macOS/Linux：\n\n"
        "```bash\n"
        "python -m venv .venv\n"
        "./.venv/bin/python -m pip install -r requirements.txt\n"
        "./.venv/bin/python run_all.py --offline\n"
        "./.venv/bin/python -m pytest -q\n"
        "```\n\n"
        "默认运行读取已锁定的 EGARCH-X 缓存、学习曲线、跨拟合政策语调和功效分析缓存。"
        "需要重算文本诊断时加 `--recompute-text-diagnostics`；需要重算 EGARCH 条件诊断时加 "
        "`--recompute-egarch-diagnostics`；需要重算正式联合 MLE 时加 `--recompute-heavy`。\n",
        encoding="utf-8",
    )


def _manifest_rows() -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    forbidden_parts = {".codex", "archive", "phases", "prompts"}
    for path in sorted(p for p in FINAL_SUBMISSION_DIR.rglob("*") if p.is_file()):
        rel = path.relative_to(FINAL_SUBMISSION_DIR).as_posix()
        lower_name = Path(rel).name.lower()
        if (
            any(rel.startswith(part) for part in forbidden_parts)
            or "phase" in lower_name
            or lower_name.endswith((".pyc", ".pyo"))
            or "__pycache__" in rel
            or ".pytest_cache" in rel
        ):
            raise RuntimeError(f"Forbidden file in final submission: {rel}")
        rows.append({"path": rel, "bytes": path.stat().st_size})
    return rows


def write_submission_manifests() -> dict:
    DELIVERY_DIR.mkdir(exist_ok=True)
    (FINAL_SUBMISSION_DIR / "delivery").mkdir(parents=True, exist_ok=True)
    stale_manifest = DELIVERY_DIR / "final_package_manifest.csv"
    if stale_manifest.exists():
        stale_manifest.unlink()
    rows = _manifest_rows()
    for manifest_path in [
        FINAL_SUBMISSION_DIR / "final_package_manifest.csv",
        FINAL_SUBMISSION_DIR / "delivery" / "FINAL_SUBMISSION_MANIFEST.csv",
        DELIVERY_DIR / "FINAL_SUBMISSION_MANIFEST.csv",
    ]:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["path", "bytes"])
            writer.writeheader()
            writer.writerows(rows)
    (DELIVERY_DIR / "FINAL_SUBMISSION_README.md").write_text(
        "# 最终提交包说明\n\n"
        "`final_submission/` 是面向课程教师的完整复现目录，排除了内部提示材料、历史归档、缓存文件和受许可限制的原始材料。"
        "正式提交建议压缩该目录内容为 `final_submission.zip`。\n",
        encoding="utf-8",
    )
    return {"included_files": len(rows), "manifest": "final_submission/final_package_manifest.csv"}


def build_final_submission() -> dict:
    _clear_submission_dir(FINAL_SUBMISSION_DIR)
    include_files = [
        "requirements.txt",
        "run_all.py",
        "DATA_LICENSE_AND_REDISTRIBUTION.md",
        "environment.yml",
        "pytest.ini",
    ]
    for file in include_files:
        src = ROOT / file
        if src.exists():
            _copy_file(src, FINAL_SUBMISSION_DIR / file)
    _write_submission_readme()
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
    for rel in [
        "data/interim/report_text",
        "data/interim/report_sections",
        "data/validation",
        "data/processed",
        "data/dictionaries",
        "data/source_registry.csv",
        "references/journal_format",
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
                    "*phase*",
                    "*gate*",
                    "*diagnostic*",
                    "*notebook_execution_refactor.json",
                    "*pdf_visual*",
                ),
            )
        elif src.exists():
            _copy_file(src, dst)
    for rel in [
        "output/diagnostics/learning_curve_sentiment.csv",
        "output/diagnostics/learning_curve_policy_stance.csv",
        "output/diagnostics/learning_curve_topic.csv",
        "output/diagnostics/market_power_analysis.csv",
        "output/diagnostics/section_repair_report.xlsx",
        "output/diagnostics/text_validation_metrics.xlsx",
        "output/diagnostics/unexpected_tone_diagnostics.xlsx",
        "output/diagnostics/manual_annotation_balance.xlsx",
    ]:
        src = ROOT / rel
        if src.exists():
            _copy_file(src, FINAL_SUBMISSION_DIR / rel)
    return write_submission_manifests()
