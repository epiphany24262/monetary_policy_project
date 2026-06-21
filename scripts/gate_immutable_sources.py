import hashlib
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def get_immutable_sources() -> list[Path]:
    sources = []
    
    # 1. output/results containing formal JSONs/CSVs
    results_dir = PROJECT_ROOT / "output" / "results"
    if results_dir.exists():
        for p in results_dir.glob("*.json"):
            sources.append((p, "Formal JSON result containing coefficients/diagnostics"))
        for p in results_dir.glob("*.csv"):
            sources.append((p, "Formal regression/numerical result CSV"))
            
    # 2. output/tables but exclude journal_table and table_*.csv since they are presentation
    # Wait, the prompt says "exclude generated presentation tables and figures expected to change during formatting."
    # So we should exclude everything in output/tables that starts with journal_table or table_
    # Let's just include specific known sources if any, or exclude presentation.
    # Actually, the formal learning curve numerical source might be in output/tables
    tables_dir = PROJECT_ROOT / "output" / "tables"
    if tables_dir.exists():
        for p in tables_dir.glob("*.csv"):
            if p.name.startswith("journal_table"): continue
            if "table" in p.name: continue
            sources.append((p, "Formal numerical CSV used for plotting/figures"))
            
        for p in tables_dir.glob("*.xlsx"):
            if "journal" in p.name: continue
            sources.append((p, "Formal XLSX result file"))
            
    # 3. data/processed and data/validation
    # parquet, csv, manual annotations
    for data_sub in ["processed", "validation", "interim"]:
        sub_dir = PROJECT_ROOT / "data" / data_sub
        if sub_dir.exists():
            for p in sub_dir.rglob("*"):
                if p.is_file() and p.suffix in [".csv", ".parquet", ".xlsx", ".json"]:
                    if "annotated" in p.name:
                        reason = "Filled manual-annotation file"
                    elif "event" in p.name:
                        reason = "Processed event panels"
                    elif "curve" in p.name or "eval" in p.name:
                        reason = "Formal text-model evaluation / learning curve"
                    else:
                        reason = f"Formal data source in data/{data_sub}"
                    sources.append((p, reason))
                    
    return sources

def main():
    sources = get_immutable_sources()
    
    records = []
    for p, reason in sources:
        rel_path = p.relative_to(PROJECT_ROOT).as_posix()
        records.append({
            "relative_path": rel_path,
            "sha256": compute_sha256(p),
            "bytes": p.stat().st_size,
            "reason_for_freezing": reason
        })
        
    records.sort(key=lambda x: x["relative_path"])
    
    out_dir = PROJECT_ROOT / "output" / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "immutable_statistical_sources_before.json"
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        
    print(f"Saved {len(records)} immutable sources to {out_file.relative_to(PROJECT_ROOT)}")

if __name__ == "__main__":
    main()
