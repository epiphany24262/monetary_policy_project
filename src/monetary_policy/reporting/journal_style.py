from __future__ import annotations

from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


PAGE_STYLE = {
    "width_cm": 21.0,
    "height_cm": 29.7,
    "top_cm": 2.3,
    "bottom_cm": 2.2,
    "left_cm": 2.5,
    "right_cm": 2.5,
}

FONT_STYLE = {
    "body_cn": "宋体",
    "body_en": "Times New Roman",
    "title_cn": "方正小标宋简体",
    "heading_cn": "黑体",
    "subheading_cn": "黑体",
    "reference_cn": "仿宋",
}

PARAGRAPH_STYLE = {
    "body_size_pt": 10.5,
    "body_line_pt": 18,
    "abstract_size_pt": 9.5,
    "abstract_line_pt": 15,
    "english_abstract_line_pt": 14,
    "first_line_chars": 2,
}

HEADING_STYLE = {
    "level1_size_pt": 14,
    "level1_before_pt": 12,
    "level1_after_pt": 6,
    "level2_size_pt": 12,
    "level2_before_pt": 9,
    "level2_after_pt": 3,
}

TABLE_STYLE = {
    "caption_size_pt": 9,
    "body_size_pt": 9,
    "note_size_pt": 7.5,
    "top_border_sz": "8",
    "mid_border_sz": "4",
    "bottom_border_sz": "8",
}

FIGURE_STYLE = {
    "width_cm": 11.5,
    "height_cm": 4.5,
    "double_panel_width_cm": 12.0,
    "double_panel_height_cm": 6.2,
    "dpi": 300,
    "axis_font_pt": 8,
    "legend_font_pt": 7.5,
    "colors": ["#000000", "#4D4D4D", "#8C8C8C", "#BFBFBF"],
}

CAPTION_STYLE = {
    "size_pt": 9,
    "line_pt": 13,
}

HEADER_FOOTER_STYLE = {
    "header_text": "罗允绩：中国货币政策报告文本特征与金融市场反应",
    "header_size_pt": 9,
    "footer_size_pt": 9,
    "border_sz": "4",
}

REFERENCE_STYLE = {
    "title_size_pt": 12,
    "body_size_pt": 7.5,
    "line_pt": 13,
    "hanging_chars": 2,
}


def cm(value: float):
    return Cm(value)


def pt(value: float):
    return Pt(value)


def set_run_font(run, cn_font: str | None = None, size_pt: float | None = None, bold: bool = False, italic: bool = False) -> None:
    cn = cn_font or FONT_STYLE["body_cn"]
    run.font.name = FONT_STYLE["body_en"]
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    r_fonts.set(qn("w:eastAsia"), cn)
    r_fonts.set(qn("w:ascii"), FONT_STYLE["body_en"])
    r_fonts.set(qn("w:hAnsi"), FONT_STYLE["body_en"])
    if size_pt is not None:
        run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic


def set_paragraph_format(
    paragraph,
    *,
    alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
    line_pt: float | None = None,
    first_line_chars: float | None = None,
    before_pt: float = 0,
    after_pt: float = 0,
) -> None:
    paragraph.alignment = alignment
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before_pt)
    fmt.space_after = Pt(after_pt)
    if line_pt is not None:
        fmt.line_spacing = Pt(line_pt)
    if first_line_chars is not None:
        fmt.first_line_indent = Pt(PARAGRAPH_STYLE["body_size_pt"] * first_line_chars)


def configure_section(section) -> None:
    section.page_width = Cm(PAGE_STYLE["width_cm"])
    section.page_height = Cm(PAGE_STYLE["height_cm"])
    section.top_margin = Cm(PAGE_STYLE["top_cm"])
    section.bottom_margin = Cm(PAGE_STYLE["bottom_cm"])
    section.left_margin = Cm(PAGE_STYLE["left_cm"])
    section.right_margin = Cm(PAGE_STYLE["right_cm"])


def add_body_section(doc):
    section = doc.add_section(WD_SECTION_START.NEW_PAGE)
    configure_section(section)
    section.different_first_page_header_footer = True
    section.odd_and_even_pages_header_footer = False
    _restart_page_numbering(section, 1)
    _clear_header_footer(section.first_page_header)
    _clear_header_footer(section.first_page_footer)
    _add_footer_page_field(section.first_page_footer)
    _add_running_header(section.header)
    _add_footer_page_field(section.footer)
    return section


def _clear_header_footer(part) -> None:
    for paragraph in part.paragraphs:
        paragraph.clear()


def _restart_page_numbering(section, start: int) -> None:
    sect_pr = section._sectPr
    existing = sect_pr.find(qn("w:pgNumType"))
    if existing is not None:
        sect_pr.remove(existing)
    pg_num = OxmlElement("w:pgNumType")
    pg_num.set(qn("w:start"), str(start))
    sect_pr.append(pg_num)


def _add_running_header(header) -> None:
    header.is_linked_to_previous = False
    paragraph = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    paragraph.clear()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(HEADER_FOOTER_STYLE["header_text"])
    set_run_font(run, FONT_STYLE["body_cn"], HEADER_FOOTER_STYLE["header_size_pt"])
    p_pr = paragraph._element.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), HEADER_FOOTER_STYLE["border_sz"])
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def _add_footer_page_field(footer) -> None:
    footer.is_linked_to_previous = False
    paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    paragraph.clear()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("— ")
    set_run_font(run, FONT_STYLE["body_en"], HEADER_FOOTER_STYLE["footer_size_pt"])
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    run._element.append(begin)
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    run._element.append(instr)
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._element.append(end)
    tail = paragraph.add_run(" —")
    set_run_font(tail, FONT_STYLE["body_en"], HEADER_FOOTER_STYLE["footer_size_pt"])


def set_cell_text(cell, text: str, *, bold: bool = False, align=WD_ALIGN_PARAGRAPH.CENTER, size_pt: float | None = None) -> None:
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    paragraph = cell.paragraphs[0]
    paragraph.clear()
    paragraph.alignment = align
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = Pt(12)
    run = paragraph.add_run(str(text))
    set_run_font(run, FONT_STYLE["body_cn"], size_pt or TABLE_STYLE["body_size_pt"], bold=bold)


def set_table_width(table, widths_cm: list[float] | None = None) -> None:
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    if not widths_cm:
        return
    for row in table.rows:
        for idx, cell in enumerate(row.cells[: len(widths_cm)]):
            cell.width = Cm(widths_cm[idx])


def mark_row_no_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def clear_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is not None:
        tbl_pr.remove(borders)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tbl_pr.append(borders)


def set_cell_border(cell, edge: str, sz: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = tc_pr.first_child_found_in("w:tcBorders")
    if tc_borders is None:
        tc_borders = OxmlElement("w:tcBorders")
        tc_pr.append(tc_borders)
    element = tc_borders.find(qn(f"w:{edge}"))
    if element is None:
        element = OxmlElement(f"w:{edge}")
        tc_borders.append(element)
    element.set(qn("w:val"), "single")
    element.set(qn("w:sz"), sz)
    element.set(qn("w:space"), "0")
    element.set(qn("w:color"), "000000")


def merge_row_cells(row):
    merged = row.cells[0]
    for cell in row.cells[1:]:
        merged = merged.merge(cell)
    return row.cells[0]
