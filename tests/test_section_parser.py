from src.monetary_policy.text.section_parser import load_named_sections


def test_section_parser_loads_guidance_and_macro():
    sections = load_named_sections()
    assert {"guidance", "macro"}.issubset(set(sections["section"]))
    assert sections[sections["section"] == "guidance"]["found"].mean() >= 0.9


def test_second_refactor_guidance_repairs_are_present():
    import pandas as pd
    from pathlib import Path

    sections = pd.read_csv("data/processed/report_sections_repaired.csv")
    repaired = sections[(sections["report_id"].isin(["2006Q1", "2006Q4", "2007Q2", "2007Q4"])) & (sections["section"] == "guidance")]
    assert len(repaired) == 4
    assert repaired["found"].astype(bool).all()
    assert (repaired["char_count"] >= 200).all()
    report_path = Path("output/diagnostics/section_repair_report.xlsx")
    if report_path.exists():
        report = pd.read_excel(report_path)
        assert set(report["report_id"]) == {"2006Q1", "2006Q4", "2007Q2", "2007Q4"}
