import shutil
from pathlib import Path

ROOT = Path(r"D:\PyCharm\Quant\monetary_policy_project").resolve()
src_dir = ROOT / "output" / "diagnostics" / "journal_review"
dest_dir = ROOT / "output" / "diagnostics" / "final_journal_repair" / "after"
dest_dir.mkdir(parents=True, exist_ok=True)

(dest_dir / "pages").mkdir(parents=True, exist_ok=True)

# Copy pages
for img in src_dir.glob("page_*.png"):
    shutil.copy2(img, dest_dir / "pages" / img.name)

# Copy contact sheet
if (src_dir / "contact_sheet.png").exists():
    shutil.copy2(src_dir / "contact_sheet.png", dest_dir / "contact_sheet.png")

# Copy inventory
if (src_dir / "page_inventory.csv").exists():
    shutil.copy2(src_dir / "page_inventory.csv", dest_dir / "page_inventory.csv")

print("Done copying visual review files.")
