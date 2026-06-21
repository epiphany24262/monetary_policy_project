from __future__ import annotations
import pytest
import xml.etree.ElementTree as ET
from pathlib import Path
import re

PAPER_DOCX = Path("paper/课程论文_提交版.docx")

@pytest.fixture
def docx_xml() -> bytes:
    if not PAPER_DOCX.exists():
        pytest.skip("DOCX not yet built")
    import zipfile
    with zipfile.ZipFile(PAPER_DOCX, "r") as zf:
        return zf.read("word/document.xml")

def get_tables(docx_xml):
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    root = ET.fromstring(docx_xml)
    return root.findall('.//w:tbl', ns), ns

def is_formal_table(table, ns):
    # A formal data table or panel has headers like 数据类别, 方法, 样本, 规格, 被解释变量, 聚合方式
    # Or panel headers like "Panel"
    for row in table.findall('.//w:tr', ns):
        for cell in row.findall('.//w:tc', ns):
            text = "".join(t.text for t in cell.findall('.//w:t', ns) if t.text)
            if any(k in text for k in ["数据类别", "方法", "样本", "规格", "被解释变量", "聚合方式"]):
                return True
    return False

def test_formal_tables_horizontal_rules(docx_xml):
    tables, ns = get_tables(docx_xml)
    formal_tables = [t for t in tables if is_formal_table(t, ns)]
    
    # We expect 7 formal table objects (Table 1, Table 2 Panel A, 2B, 3, 4, Table 5 Panel A, 5B)
    assert len(formal_tables) == 7, f"Expected 7 formal data tables, got {len(formal_tables)}"
    
    # Check top rules for Table 1, 2A, 3, 4, 5A
    # They should have top rule sz=8 on their first row
    for i in [0, 1, 3, 4, 5]:
        tbl = formal_tables[i]
        first_row = tbl.findall('.//w:tr', ns)[0]
        first_cell = first_row.find('.//w:tc', ns)
        top_border = first_cell.find('.//w:tcBorders/w:top', ns)
        assert top_border is not None and top_border.get(f"{{{ns['w']}}}sz") == "8", f"Table {i} missing formal top rule."

    # Check top rules for Table 2B, 5B are ABSENT
    for i in [2, 6]:
        tbl = formal_tables[i]
        first_row = tbl.findall('.//w:tr', ns)[0]
        first_cell = first_row.find('.//w:tc', ns)
        top_border = first_cell.find('.//w:tcBorders/w:top', ns)
        assert top_border is None or top_border.get(f"{{{ns['w']}}}val") in ["none", "nil"], f"Table {i} (Panel B) has incorrect top rule."

    # Check bottom rules for Table 1, 2B, 3, 4, 5B
    for i in [0, 2, 3, 4, 6]:
        tbl = formal_tables[i]
        last_row = tbl.findall('.//w:tr', ns)[-1]
        first_cell = last_row.find('.//w:tc', ns)
        bottom_border = first_cell.find('.//w:tcBorders/w:bottom', ns)
        assert bottom_border is not None and bottom_border.get(f"{{{ns['w']}}}sz") == "8", f"Table {i} missing formal bottom rule."

    # Check transition rules for Table 2A, 5A
    for i in [1, 5]:
        tbl = formal_tables[i]
        last_row = tbl.findall('.//w:tr', ns)[-1]
        first_cell = last_row.find('.//w:tc', ns)
        bottom_border = first_cell.find('.//w:tcBorders/w:bottom', ns)
        assert bottom_border is not None and bottom_border.get(f"{{{ns['w']}}}sz") == "4", f"Table {i} (Panel A) missing thin transition bottom rule."

def test_no_unintended_vertical_rules(docx_xml):
    tables, ns = get_tables(docx_xml)
    formal_tables = [t for t in tables if is_formal_table(t, ns)]
    
    for i, tbl in enumerate(formal_tables):
        tblBorders = tbl.find('.//w:tblBorders', ns)
        if tblBorders is not None:
            left = tblBorders.find('w:left', ns)
            right = tblBorders.find('w:right', ns)
            insideV = tblBorders.find('w:insideV', ns)
            assert left is None or left.get(f"{{{ns['w']}}}val") in ["none", "nil"]
            assert right is None or right.get(f"{{{ns['w']}}}val") in ["none", "nil"]
            assert insideV is None or insideV.get(f"{{{ns['w']}}}val") in ["none", "nil"]

def test_table_grid_structure(docx_xml):
    tables, ns = get_tables(docx_xml)
    formal_tables = [t for t in tables if is_formal_table(t, ns)]
    
    for i, tbl in enumerate(formal_tables):
        tblPr = tbl.find('.//w:tblPr', ns)
        tblW = tblPr.find('w:tblW', ns)
        assert tblW is not None
        assert tblW.get(f"{{{ns['w']}}}type") == "dxa", f"Table {i} tblW type is not dxa"
        assert tblW.get(f"{{{ns['w']}}}w") == "8504", f"Table {i} width is not exactly 8504 twips"
        
        tblLayout = tblPr.find('w:tblLayout', ns)
        assert tblLayout is not None
        assert tblLayout.get(f"{{{ns['w']}}}type") == "fixed", f"Table {i} layout is not fixed"
        
        tblGrid = tbl.find('.//w:tblGrid', ns)
        assert tblGrid is not None
        gridCols = tblGrid.findall('w:gridCol', ns)
        assert len(gridCols) > 0, f"Table {i} has no gridCol"
        
        col_widths = [int(col.get(f"{{{ns['w']}}}w")) for col in gridCols]
        assert sum(col_widths) == 8504, f"Table {i} gridCols sum {sum(col_widths)} != 8504"
        
        # Check every row tcW
        for r_idx, row in enumerate(tbl.findall('.//w:tr', ns)):
            cells = row.findall('.//w:tc', ns)
            row_tcWs = []
            for c in cells:
                tcW = c.find('.//w:tcPr/w:tcW', ns)
                assert tcW is not None, f"Table {i} row {r_idx} missing tcW"
                row_tcWs.append(int(tcW.get(f"{{{ns['w']}}}w")))
            assert sum(row_tcWs) == 8504, f"Table {i} row {r_idx} tcWs sum {sum(row_tcWs)} != 8504"
            assert row_tcWs == col_widths, f"Table {i} row {r_idx} tcWs do not match gridCols"

def test_table_numeric_alignment(docx_xml):
    """Correction 5: numeric cells use RIGHT alignment, sample sizes CENTER.
    No decimal tab stops or leading tab runs are permitted."""
    tables, ns = get_tables(docx_xml)
    formal_tables = [t for t in tables if is_formal_table(t, ns)]
    
    for tbl in formal_tables:
        rows = tbl.findall('.//w:tr', ns)
        if len(rows) > 1:
            header = rows[0]
            data = rows[1:]
            header_cells = header.findall('.//w:tc', ns)
            
            for j, hc in enumerate(header_cells):
                htext = "".join(t.text for t in hc.findall('.//w:t', ns) if t.text)
                for drow in data:
                    dcells = drow.findall('.//w:tc', ns)
                    if j < len(dcells):
                        dtext = "".join(t.text for t in dcells[j].findall('.//w:t', ns) if t.text).strip()
                        
                        # No decimal tabs anywhere in formal table data cells
                        tab = dcells[j].find('.//w:p/w:pPr/w:tabs/w:tab', ns)
                        if tab is not None:
                            assert tab.get(f"{{{ns['w']}}}val") != "decimal", \
                                f"Decimal tab found in cell '{dtext}' — Correction 5 forbids decimal tabs"
                        
                        if "样本量" in htext:
                            jc = dcells[j].find('.//w:p/w:pPr/w:jc', ns)
                            assert jc is not None and jc.get(f"{{{ns['w']}}}val") == "center", \
                                f"Sample size column cell '{dtext}' must be center-aligned"
                        elif re.search(r'\d', dtext) and '.' in dtext:
                            jc = dcells[j].find('.//w:p/w:pPr/w:jc', ns)
                            jc_val = jc.get(f"{{{ns['w']}}}val") if jc is not None else "None"
                            assert jc is not None and jc_val in ["right", "end"], \
                                f"Numeric cell '{dtext}' must be right-aligned, got '{jc_val}'"

