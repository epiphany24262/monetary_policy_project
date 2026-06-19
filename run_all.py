from __future__ import annotations

import argparse
import json

from src.monetary_policy.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the monetary policy communication refactor pipeline.")
    parser.add_argument("--refresh-data", action="store_true", help="Accepted for compatibility; existing raw data are preserved.")
    parser.add_argument("--offline", action="store_true", help="Run from fixed local data.")
    parser.add_argument("--skip-notebook", action="store_true", help="Build outputs without executing the notebook.")
    args = parser.parse_args()

    summary = run_pipeline(execute_nb=not args.skip_notebook)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
