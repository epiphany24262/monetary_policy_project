from __future__ import annotations

import ast
from pathlib import Path

import fitz
import pandas as pd


def test_report_section_paths_are_posix_relative():
    for rel in ["data/processed/report_sections.csv", "data/processed/report_sections_repaired.csv"]:
        df = pd.read_csv(rel)
        assert "local_path" in df.columns
        assert not df["local_path"].astype(str).str.contains("\\", regex=False).any()
        assert df["local_path"].astype(str).str.startswith("data/interim/report_sections/").all()


def test_public_build_functions_are_not_duplicated():
    expected = {
        "src/monetary_policy/reporting/notebook_builder.py": {"build_notebook", "execute_notebook"},
        "src/monetary_policy/reporting/journal_paper_builder.py": {"build_journal_paper"},
        "src/monetary_policy/reporting/journal_tables.py": {"write_journal_tables"},
        "src/monetary_policy/reporting/journal_figures.py": {"write_journal_figures"},
    }
    for rel, names in expected.items():
        tree = ast.parse(Path(rel).read_text(encoding="utf-8"))
        defs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        for name in names:
            assert defs.count(name) == 1, f"{name} duplicated in {rel}"
    assert "_run_daily_egarch_x_fast" not in Path("src/monetary_policy/pipeline.py").read_text(encoding="utf-8")


def test_pdf_has_cover_then_abstract_page():
    pdf_path = Path("paper/课程论文_提交版.pdf")
    assert pdf_path.exists()
    doc = fitz.open(str(pdf_path))
    assert len(doc) >= 2
    first = doc[0].get_text("text")
    second = doc[1].get_text("text")
    assert "期末报告" in first or "课程论文" in first or "Python" in first
    assert "中国货币政策报告文本特征" in second
    assert any("内容提要" in doc[i].get_text("text") for i in range(len(doc)))
    doc.close()


def test_research_files_match_final_method_hierarchy():
    plan_path = next(
        path for path in [Path("research/FINAL_ANALYSIS_PLAN.md"), Path("configs/FINAL_ANALYSIS_PLAN.md")] if path.exists()
    )
    synthesis_path = Path("research/research_synthesis.md")
    plan = plan_path.read_text(encoding="utf-8")
    synthesis = synthesis_path.read_text(encoding="utf-8") if synthesis_path.exists() else ""
    combined = plan + "\n" + synthesis
    assert "主检验二" not in combined
    assert "债券为探索性扩展国债收益率曲线" not in combined
    assert "股票市场只作为辅助扩展" not in combined
    assert "核心主检验：政策指引创新度与股票发布后五日实际波动率" in plan
    assert "探索性扩展：未预期政策语调、跨拟合政策语调与国债收益率曲线斜率" in plan
