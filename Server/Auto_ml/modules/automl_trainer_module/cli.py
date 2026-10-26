"""Command line interface:  python -m automl_trainer --input-dir output --profile dataset_profile.json"""
from __future__ import annotations

import argparse
import logging
import sys

from .config import TrainingConfig
from .pipeline import run_from_directory


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="automl_trainer", description="Model selection + training")
    ap.add_argument("--input-dir", required=True, help="preprocessing output folder")
    ap.add_argument("--profile", help="dataset_profile.json from the Dataset Analyzer")
    ap.add_argument("--out-dir", default="model_output")
    ap.add_argument("--config", help="YAML/JSON TrainingConfig file (CLI flags override it)")
    ap.add_argument("--target-col", help="target column inside the processed CSVs (if no y_*.csv)")
    ap.add_argument("--task", choices=["auto", "classification", "regression"])
    ap.add_argument("--metric", help="primary metric (default accuracy / r2)")
    ap.add_argument("--cv-splits", type=int)
    ap.add_argument("--max-candidates", type=int)
    ap.add_argument("--no-tune", action="store_true")
    ap.add_argument("--no-ensemble", action="store_true")
    ap.add_argument("--tune-top-n", type=int)
    ap.add_argument("--tune-iter", type=int)
    ap.add_argument("--time-budget", type=float, help="soft time budget in seconds")
    ap.add_argument("--refit-on-all", action="store_true")
    ap.add_argument("--exclude", nargs="*")
    ap.add_argument("--rules", help="custom selection rules YAML")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--n-jobs", type=int)
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg = TrainingConfig.from_file(a.config) if a.config else TrainingConfig()
    overrides = {
        "task": a.task, "primary_metric": a.metric, "cv_splits": a.cv_splits,
        "max_candidates": a.max_candidates, "tune_top_n": a.tune_top_n, "tune_iterations": a.tune_iter,
        "time_budget_s": a.time_budget, "random_state": a.seed, "n_jobs": a.n_jobs, "rules_path": a.rules,
        "exclude": tuple(a.exclude) if a.exclude is not None else None,
    }
    flags = {"tune": False if a.no_tune else None, "ensemble": False if a.no_ensemble else None,
             "refit_on_all": True if a.refit_on_all else None}
    cfg = TrainingConfig.from_dict({**cfg.to_dict(), **{k: v for k, v in {**overrides, **flags}.items() if v is not None}})

    try:
        res = run_from_directory(a.input_dir, a.out_dir, a.profile, cfg, a.target_col)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    s = res.summary
    print(f"Task: {s['task']} | metric: {s['primary_metric']} | screened {s['models_screened']} -> "
          f"finalists {s['models_finalists']} -> tuned {s['models_tuned']} | {s['total_time_s']}s")
    print(f"Best model: {s['best_model']} | CV {s['best_cv_score']} (+/-{s['best_cv_std']}) "
          f"| baseline {s['baseline_cv_score']}")
    print(f"Test metrics: {s['best_test_metrics']}")
    for w in s["warnings"]:
        print("WARNING:", w)
    print(f"Artifacts saved to {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
