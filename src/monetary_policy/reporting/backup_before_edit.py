from pathlib import Path
import shutil
from datetime import datetime
ROOT = Path(__file__).resolve().parents[3]
backup_root = ROOT / 'archive' / 'dev_backups' / datetime.now().strftime('backup_%Y%m%d_%H%M%S')
backup_root.mkdir(parents=True, exist_ok=True)

items = [
    ROOT / 'paper' / '课程论文_提交版.docx',
    ROOT / 'paper' / '课程论文_提交版.pdf',
    ROOT / 'src' / 'monetary_policy' / 'reporting'
]
for it in items:
    if it.exists():
        dest = backup_root / it.name
        if it.is_dir():
            shutil.copytree(it, backup_root / it.name)
        else:
            shutil.copy2(it, dest)
        print('backed up', it, '->', dest)
    else:
        print('not found, skipping', it)
print('backup complete at', backup_root)
