import fitz
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
current_pdf = ROOT / 'paper' / '课程论文_提交版.pdf'
current_docx = ROOT / 'paper' / '课程论文_提交版.docx'
report = ROOT / 'output' / 'diagnostics' / 'statistical_research_rebuild' / 'layout_gap_report.md'

forbidden_terms = [
    'full_joint_mle','True','D0','D1','D0_D1','wild_residual_bootstrap_hc3','method','model','dependent','target','beta','se_hc3','p_value','tone_aggregation','interaction_coef','post_2019_total_effect'
]

lines = []
lines.append('# 版式差距详细审计')
lines.append('')

if current_pdf.exists():
    doc = fitz.open(str(current_pdf))
    lines.append(f'当前 PDF 页数: {doc.page_count}')
    lines.append('')
    pages_with_forbidden = {}
    pages_textlen = {}
    pages_image_info = {}
    for i in range(doc.page_count):
        page = doc.load_page(i)
        text = page.get_text()
        pages_textlen[i+1] = len(text)
        for term in forbidden_terms:
            if term in text:
                pages_with_forbidden.setdefault(term, []).append(i+1)
        images = page.get_images(full=True)
        pages_image_info[i+1] = len(images)
        # check image bbox near edges: get image objects positions
        # approximate by checking text bbox extent
        rects = page.get_text('blocks')
        # no heavy image bbox detection here
    lines.append('## 工程化字段出现')
    lines.append('')
    if pages_with_forbidden:
        for term, pgs in pages_with_forbidden.items():
            lines.append(f'- `{term}` 出现在页: {pgs}')
    else:
        lines.append('- 未检测到指定工程化字段的直接出现')
    lines.append('')
    # image summary
    lines.append('## 每页图片数量概览')
    for p, cnt in pages_image_info.items():
        if cnt>0:
            lines.append(f'- 页 {p}: 图像对象数 {cnt}')
    lines.append('')
    # blank page detection
    blank_pages = [p for p, l in pages_textlen.items() if l < 50 and pages_image_info.get(p,0)==0]
    if blank_pages:
        lines.append('## 可疑空白页')
        lines.append(f'- 可疑空白页: {blank_pages}')
    else:
        lines.append('## 无明显空白页')
    lines.append('')
else:
    lines.append('当前 PDF 未找到，无法分析 PDF 内容')

# analyze docx for w:lineRule or exact spacing
if current_docx.exists():
    lines.append('## DOCX 内部检查')
    try:
        with zipfile.ZipFile(current_docx) as z:
            names = z.namelist()
            if 'word/document.xml' in names:
                docxml = z.read('word/document.xml').decode('utf-8', errors='ignore')
                if 'lineRule' in docxml or 'w:lineRule' in docxml:
                    lines.append('- 检测到行间距规则标签（可能存在固定行距）')
                    # find occurrences
                    idx = docxml.find('lineRule')
                    context = docxml[max(0, idx-100):idx+200]
                    lines.append('  - context snippet:')
                    lines.append('    ```xml')
                    lines.append('    '+context.replace('\n',''))
                    lines.append('    ```')
                else:
                    lines.append('- 未检测到 `w:lineRule` 标签')
            else:
                lines.append('- DOCX 内缺少 word/document.xml')
    except Exception as e:
        lines.append(f'- 打开 DOCX 失败: {e}')
else:
    lines.append('DOCX 文件未找到')

# write append to report
report.write_text('\n'.join(lines), encoding='utf-8')
print('wrote', report)
