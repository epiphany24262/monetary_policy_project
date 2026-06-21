import sys
from pathlib import Path
import fitz
from PIL import Image, ImageDraw, ImageFont
import os

ROOT = Path(__file__).resolve().parents[3]
OUT_BASE = ROOT / 'output' / 'diagnostics' / 'statistical_research_rebuild' / 'before'
CUR_OUT = OUT_BASE / 'current'
REF_OUT = OUT_BASE / 'reference'

os.makedirs(CUR_OUT, exist_ok=True)
os.makedirs(REF_OUT, exist_ok=True)

# Paths
current_pdf = ROOT / 'paper' / '课程论文_提交版.pdf'
ref_docx = ROOT / 'references' / 'journal_format' / '统计研究基本版式.docx'
ref_pdf_alt = ROOT / 'references' / 'journal_format' / 'SNA全球化核算框架及其应用_杨仲山.pdf'

TEMP_DIR = ROOT / 'output' / 'diagnostics' / 'statistical_research_rebuild' / 'temp'
os.makedirs(TEMP_DIR, exist_ok=True)

# helper: convert docx to pdf using docx2pdf if available

def convert_docx_to_pdf(docx_path, out_pdf):
    try:
        from docx2pdf import convert
        convert(str(docx_path), str(out_pdf))
        return True
    except Exception as e:
        print('docx2pdf conversion failed:', e)
        return False


def render_pdf_to_pngs(pdf_path, out_dir, dpi=180):
    doc = fitz.open(pdf_path)
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=mat, alpha=False)
        out_file = out_dir / f'page_{i:03d}.png'
        pix.save(str(out_file))
        pages.append(out_file)
    return pages


def make_contact_sheet(png_paths, out_file, per_row=3, thumb_max_height=1200, label_font=None):
    imgs = [Image.open(p) for p in png_paths]
    # resize images to same height keeping aspect
    heights = [im.height for im in imgs]
    target_h = min(max(200, int(sum(heights)/len(heights)/2)), thumb_max_height)
    thumbs = [im.copy() for im in imgs]
    resized = []
    for im in thumbs:
        w = int(im.width * (target_h / im.height))
        resized.append(im.resize((w, target_h), Image.LANCZOS))
    rows = []
    row_imgs = []
    for i, im in enumerate(resized):
        row_imgs.append(im)
        if len(row_imgs) == per_row or i == len(resized)-1:
            # combine row
            total_w = sum(im.width for im in row_imgs)
            max_h = max(im.height for im in row_imgs)
            row_canvas = Image.new('RGB', (total_w, max_h+40), (255,255,255))
            x = 0
            for j, rim in enumerate(row_imgs):
                row_canvas.paste(rim, (x,0))
                # label
                draw = ImageDraw.Draw(row_canvas)
                label = f'page {i - len(row_imgs) + j + 2}' if False else ''
                x += rim.width
            rows.append(row_canvas)
            row_imgs = []
    # stack rows
    total_h = sum(r.height for r in rows)
    max_w = max(r.width for r in rows)
    sheet = Image.new('RGB', (max_w, total_h), (255,255,255))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(out_file)
    return out_file


def main():
    # render current PDF
    if not current_pdf.exists():
        print('Current PDF not found:', current_pdf)
    else:
        cur_pages = render_pdf_to_pngs(current_pdf, CUR_OUT, dpi=180)
        print('Rendered current pages:', len(cur_pages))

    # prepare reference: prefer converting docx to pdf
    ref_pdf = TEMP_DIR / 'stat_research_ref.pdf'
    converted = False
    if ref_docx.exists():
        converted = convert_docx_to_pdf(ref_docx, ref_pdf)
    if not converted and ref_pdf_alt.exists():
        ref_pdf = ref_pdf_alt
    if not ref_pdf.exists():
        print('Reference PDF not available for rendering.')
    else:
        ref_pages = render_pdf_to_pngs(ref_pdf, REF_OUT, dpi=180)
        print('Rendered reference pages:', len(ref_pages))

    # create simple contact sheets (all pages in folder combined)
    # current
    cur_pngs = sorted(CUR_OUT.glob('page_*.png'))
    ref_pngs = sorted(REF_OUT.glob('page_*.png'))
    from math import ceil
    def create_contact(pngs, out_path):
        if not pngs:
            return None
        per_row = 3
        # create thumbnails limiting height
        imgs = [Image.open(p) for p in pngs]
        # compute uniform height to make rows consistent
        target_h = 800
        resized = [im.resize((int(im.width * (target_h / im.height)), target_h), Image.LANCZOS) for im in imgs]
        # add labels beneath each image with page number
        labeled = []
        font = None
        try:
            font = ImageFont.truetype('simsun.ttc', 24)
        except Exception:
            font = ImageFont.load_default()
        for idx, im in enumerate(resized, start=1):
            w, h = im.size
            canvas = Image.new('RGB', (w, h+40), (255,255,255))
            canvas.paste(im, (0,0))
            draw = ImageDraw.Draw(canvas)
            text = f'页 {idx}'
            try:
                if hasattr(draw, 'textbbox'):
                    bbox = draw.textbbox((0,0), text, font=font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]
                else:
                    tw, th = font.getsize(text)
            except Exception:
                tw, th = (len(text) * 6, 12)
            draw.text(((w-tw)/2, h+6), text, fill=(0,0,0), font=font)
            labeled.append(canvas)
        rows = []
        for i in range(0, len(labeled), per_row):
            row_imgs = labeled[i:i+per_row]
            total_w = sum(im.width for im in row_imgs)
            h = max(im.height for im in row_imgs)
            row_canvas = Image.new('RGB', (total_w, h), (255,255,255))
            x = 0
            for im in row_imgs:
                row_canvas.paste(im, (x,0))
                x += im.width
            rows.append(row_canvas)
        max_w = max(r.width for r in rows) if rows else 0
        total_h = sum(r.height for r in rows)
        sheet = Image.new('RGB', (max_w, total_h), (255,255,255))
        y = 0
        for r in rows:
            sheet.paste(r, (0,y))
            y += r.height
        sheet.save(out_path)
        return out_path

    cur_contact = create_contact(cur_pngs, CUR_OUT / 'current_contact_sheet.png') if cur_pngs else None
    ref_contact = create_contact(ref_pngs, REF_OUT / 'reference_contact_sheet.png') if ref_pngs else None
    print('Contact sheets:', cur_contact, ref_contact)

    # generate a basic markdown report
    report = ROOT / 'output' / 'diagnostics' / 'statistical_research_rebuild' / 'layout_gap_report.md'
    lines = []
    lines.append('# 版式差距初步审计')
    lines.append('来源文件：')
    lines.append(f'- 参考样文(docx): {ref_docx}')
    lines.append(f'- 参考样文(pdf备选): {ref_pdf_alt}')
    lines.append(f'- 当前论文(pdf): {current_pdf}')
    lines.append('')
    if cur_pngs:
        lines.append(f'当前论文页数: {len(cur_pngs)}')
    else:
        lines.append('当前论文未渲染为PNG')
    if ref_pngs:
        lines.append(f'参考样文页数: {len(ref_pngs)}')
    else:
        lines.append('参考样文未渲染为PNG')
    lines.append('')
    lines.append('请人工审阅 output/diagnostics/statistical_research_rebuild/before/ 下的逐页PNG 和 联系表，指出具体版式差异（页码）。')
    report.write_text('\n'.join(lines), encoding='utf-8')
    print('Wrote report to', report)

if __name__ == '__main__':
    main()
