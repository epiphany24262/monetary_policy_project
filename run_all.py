from __future__ import annotations

import argparse
import json

from src.monetary_policy.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the monetary policy communication refactor pipeline.")
    parser.add_argument("--refresh-data", action="store_true", help="Accepted for compatibility; existing raw data are preserved.")
    parser.add_argument("--offline", action="store_true", help="Run from fixed local data.")
    parser.add_argument("--skip-notebook", action="store_true", help="Build outputs without executing the notebook.")
    parser.add_argument("--recompute-heavy", action="store_true", help="Recompute locked full-joint daily EGARCH-X MLE instead of reading the locked result.")
    parser.add_argument("--recompute-diagnostics", action="store_true", help="Recompute EGARCH-X D1/D0+D1 conditional diagnostics and permutation while reusing the locked full-joint MLE.")
    parser.add_argument("--recompute-egarch-diagnostics", action="store_true", help="Alias for --recompute-diagnostics.")
    parser.add_argument("--recompute-text-diagnostics", action="store_true", help="Recompute learning curves, cross-fitted policy tone, and market power analysis instead of reading caches.")
    args = parser.parse_args()

    summary = run_pipeline(
        execute_nb=not args.skip_notebook,
        recompute_heavy=args.recompute_heavy,
        recompute_diagnostics=args.recompute_diagnostics or args.recompute_egarch_diagnostics,
        recompute_text_diagnostics=args.recompute_text_diagnostics,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
