"""Orchestrator: selection -> successive-halving screen -> tune -> ensemble -> confirm -> test."""
from __future__ import annotations

import logging
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.preprocessing import LabelEncoder

from . import evaluation as ev
from .config import TrainingConfig
from .context import build_context
from .data import DatasetBundle, UpstreamArtifacts, infer_task
from .ensemble import build_ensemble, pick_members
from .registry import specs_for
from .search import Budget, prune, screen, subsample, tune
from .selector import select_candidates

log = logging.getLogger("automl_trainer")
ENSEMBLE_NAME = "SoftVotingEnsemble"


@dataclass
class TrainingResult:
    summary: dict
    selection: dict
    leaderboard: list
    baseline: dict | None
    tuning: dict
    eliminated: list
    test_details: dict
    bundle: dict
    fitted: dict = field(default_factory=dict)  # name -> fitted model (leaderboard models)

    @property
    def best_model(self):
        return self.bundle["model"]

    def save(self, out_dir):
        from .artifacts import save_run
        return save_run(self, out_dir)


class AutoTrainer:
    def __init__(self, config: TrainingConfig | None = None):
        self.cfg = config or TrainingConfig()

    def run(self, data: DatasetBundle, upstream: UpstreamArtifacts | None = None) -> TrainingResult:
        cfg, upstream = self.cfg, upstream or UpstreamArtifacts()
        budget, warns, failures = Budget(cfg.time_budget_s), [], {}

        # ---- 0. task, labels, context, shortlist ------------------------------------
        task = infer_task(data.y_train, upstream.profile, cfg.task)
        le, y_tr, y_te = None, data.y_train.to_numpy(), data.y_test.to_numpy()
        if task == "classification":
            le = LabelEncoder().fit(pd.concat([data.y_train, data.y_test]))
            y_tr, y_te = le.transform(data.y_train), le.transform(data.y_test)
        X, y = data.X_train, pd.Series(y_tr)

        ctx = build_context(upstream, X, y, task)
        selection = select_candidates(ctx, cfg)
        specs = specs_for(task)
        scorers = ev.scorers_for(task, ctx["n_classes"])
        primary = cfg.primary_metric or ev.default_primary(task)
        if primary not in scorers:
            raise ValueError(f"primary_metric {primary!r} invalid for {task}; choose from {list(scorers)}")
        secondary = ev.secondary_metric(task, primary)
        if ctx["imbalanced"] and primary == "accuracy":
            warns.append("Class imbalance detected: accuracy can be misleading. Consider "
                         "primary_metric='balanced_accuracy', 'f1' or 'roc_auc'.")
        shortlist = selection["shortlist"]
        if not shortlist:
            raise RuntimeError(f"No eligible models. Excluded: {selection['excluded']}")
        log.info("task=%s metric=%s rows=%d features=%d shortlist=%s", task, primary,
                 ctx["n_rows"], ctx["n_features"], shortlist)

        # ---- 1. rung 0: cheap screen (subsampled when the data is large) ------------
        cv_full = ev.make_splitter(task, y, cfg.cv_splits, cfg.cv_repeats, cfg.random_state)
        Xs, ys, sub = subsample(task, X, y, cfg.screening_max_rows, cfg.random_state)
        cv0 = (ev.make_splitter(task, ys, cfg.screening_folds, 1, cfg.random_state) if sub else cv_full)
        scores, fails = screen(["DummyBaseline"] + shortlist, specs, ctx, cfg, Xs, ys, cv0, scorers, budget, "rung0")
        failures.update(fails)
        baseline0 = scores.pop("DummyBaseline", None)
        if not scores:
            raise RuntimeError(f"All candidate models failed: {failures}")
        kept, dropped = prune(scores, baseline0, cfg, primary, secondary)
        eliminated = [{"algorithm": n, "stage": "rung0", "reason": r,
                       f"screen_{primary}": round(scores[n][f"cv_{primary}_mean"], 4)} for n, r in dropped.items()]
        rung_log = [{"rung": 0, "rows": len(Xs), "folds": cv0.get_n_splits(),
                     "evaluated": list(scores), "kept": kept}]

        # ---- 2. rung 1: full-data screen of the survivors (only if rung 0 subsampled)
        if sub:
            scores, fails = screen(["DummyBaseline"] + kept, specs, ctx, cfg, X, y, cv_full, scorers, budget, "rung1")
            failures.update(fails)
            baseline1 = scores.pop("DummyBaseline", None)
            kept, dropped = prune(scores, baseline1, cfg, primary, secondary)
            eliminated += [{"algorithm": n, "stage": "rung1", "reason": r,
                            f"screen_{primary}": round(scores[n][f"cv_{primary}_mean"], 4)} for n, r in dropped.items()]
            rung_log.append({"rung": 1, "rows": len(X), "folds": cv_full.get_n_splits(), "evaluated": list(scores), "kept": kept})
        contenders = sorted(kept, key=lambda n: ev.rank_key(scores[n], primary, secondary))
        screen_primary = {n: round(scores[n][f"cv_{primary}_mean"], 4) for n in scores}

        # ---- 3. tune the top-N ------------------------------------------------------------
        tuned_params: dict[str, dict] = {}
        tuning_log: dict[str, dict] = {}
        if cfg.tune:
            for n in contenders[: cfg.tune_top_n]:
                if not specs[n].space:
                    continue
                if budget.exceeded():
                    tuning_log[n] = {"status": "skipped: time budget exhausted"}
                    continue
                try:
                    res = tune(specs[n], ctx, cfg, X, y, cv_full, scorers[primary])
                    tuned_params[n] = res["best_params"]
                    tuning_log[n] = {"status": "ok", **res}
                except Exception as exc:
                    tuning_log[n] = {"status": f"failed: {type(exc).__name__}: {exc}"}
                    log.error("tuning %s failed: %s", n, exc)

        # ---- 4. confirm on FRESH splits (tuned vs default) -------------------------------------
        cv_b = ev.make_splitter(task, y, cfg.cv_splits, cfg.cv_repeats, cfg.random_state + 1)
        final: dict[str, dict] = {}
        estimators: dict[str, Any] = {}
        base_b = None
        try:
            base_b = ev.cv_evaluate(specs["DummyBaseline"].factory(ctx, cfg.random_state), X, y, cv_b, scorers, cfg.n_jobs)
        except Exception as exc:
            failures["DummyBaseline"] = f"{type(exc).__name__}: {exc}"
        for n in contenders:
            try:
                est = specs[n].factory(ctx, cfg.random_state)
                chosen, params, is_tuned = ev.cv_evaluate(est, X, y, cv_b, scorers, cfg.n_jobs), {}, False
                if n in tuned_params:
                    t_est = specs[n].factory(ctx, cfg.random_state).set_params(**tuned_params[n])
                    t_res = ev.cv_evaluate(t_est, X, y, cv_b, scorers, cfg.n_jobs)
                    tuning_log[n]["default_confirm_score"] = round(chosen[f"cv_{primary}_mean"], 4)
                    tuning_log[n]["tuned_confirm_score"] = round(t_res[f"cv_{primary}_mean"], 4)
                    is_tuned = ev.is_better(t_res[f"cv_{primary}_mean"], chosen[f"cv_{primary}_mean"], primary)
                    tuning_log[n]["accepted"] = is_tuned
                    if is_tuned:
                        est, chosen, params = t_est, t_res, tuned_params[n]
                final[n] = {"algorithm": n, "family": specs[n].family, "tuned": is_tuned, "params": params,
                            f"screen_{primary}": screen_primary[n], **chosen}
                estimators[n] = est
            except Exception as exc:
                failures[n] = f"{type(exc).__name__}: {exc}"
                log.error("confirm %s failed: %s", n, failures[n])
        singles = sorted(final.values(), key=lambda r: ev.rank_key(r, primary, secondary))
        if not singles:
            raise RuntimeError(f"No model survived confirmation: {failures}")

        # ---- 5. optional ensemble of the strongest, most diverse models -------------------
        ens_rec = None
        if cfg.ensemble and len(singles) >= 2 and not budget.exceeded():
            members = pick_members([r["algorithm"] for r in singles], specs, estimators, task, cfg.ensemble_top_k)
            if len(members) >= 2:
                try:
                    ens = build_ensemble(task, members, estimators)
                    res = ev.cv_evaluate(ens, X, y, cv_b, scorers, cfg.n_jobs)
                    ens_rec = {"algorithm": ENSEMBLE_NAME, "family": "ensemble", "tuned": False,
                               "params": {}, "members": members, **res}
                    estimators[ENSEMBLE_NAME] = ens
                except Exception as exc:
                    failures[ENSEMBLE_NAME] = f"{type(exc).__name__}: {exc}"

        # ---- 6. select the winner (the ensemble must clear a margin to displace a single model)
        best_single = singles[0]
        ens_wins = bool(ens_rec) and ev.is_better(ens_rec[f"cv_{primary}_mean"], best_single[f"cv_{primary}_mean"],
                                                  primary, margin=cfg.ensemble_min_gain)
        if ens_rec:
            ens_rec["selected_over_single"] = ens_wins
        board = sorted(singles + ([ens_rec] if ens_rec else []), key=lambda r: ev.rank_key(r, primary, secondary))
        winner = ens_rec if ens_wins else best_single
        board.remove(winner)
        board.insert(0, winner)
        for i, r in enumerate(board, 1):
            r["rank"] = i
            r["selection_score"] = selection["scores"].get(r["algorithm"], {}).get("score")
            r["overfit_gap"] = round(ev.overfit_gap(r, primary), 4)
            r["overfit_warning"] = r["overfit_gap"] > cfg.overfit_gap_warn

        # ---- 7. fit on the training split, evaluate ONCE on the held-out test set ---------
        fitted: dict[str, Any] = {}
        for r in board:
            n = r["algorithm"]
            try:
                model = clone(estimators[n])
                t0 = time.perf_counter()
                model.fit(X, y_tr)
                r["train_time_s"] = round(time.perf_counter() - t0, 4)
                t0 = time.perf_counter()
                r["test"] = ev.test_metrics(model, data.X_test, y_te, task)
                r["inference_time_s"] = round(time.perf_counter() - t0, 4)
                fitted[n] = model
            except Exception as exc:
                r["test_error"] = f"{type(exc).__name__}: {exc}"
        best = next((r for r in board if r["algorithm"] in fitted), None)
        if best is None:
            raise RuntimeError("No model could be fitted on the full training split.")
        best_name, best_model = best["algorithm"], fitted[best["algorithm"]]

        # ---- 8. diagnostics ---------------------------------------------------------------
        if base_b and not ev.is_better(best[f"cv_{primary}_mean"], base_b[f"cv_{primary}_mean"], primary):
            warns.append("No model beats the dummy baseline: the features carry little signal.")
        if best["overfit_warning"]:
            warns.append(f"{best_name}: train-vs-CV gap of {best['overfit_gap']:.3f} (possible overfitting).")
        gap = abs(best["test"][primary] - best[f"cv_{primary}_mean"])
        if gap > 0.05:
            warns.append(f"Test {primary} differs from CV by {gap:.3f}; the test split may be small or unrepresentative.")
        others = [r for r in board[1:] if "test" in r]
        if others and abs(best[f"cv_{primary}_mean"] - others[0][f"cv_{primary}_mean"]) < best[f"cv_{primary}_std"]:
            warns.append(f"{best_name} and {others[0]['algorithm']} are within one CV standard deviation; "
                         "their ranking is not statistically meaningful.")
        details = {}
        if task == "classification":
            details = ev.classification_details(best_model, data.X_test, y_te, [c.item() if hasattr(c, "item") else c for c in le.classes_])

        deploy = best_model
        if cfg.refit_on_all:
            deploy = clone(estimators[best_name])
            deploy.fit(pd.concat([data.X_train, data.X_test]), np.concatenate([y_tr, y_te]))

        env = {"python": platform.python_version(), "sklearn": sklearn.__version__,
               "numpy": np.__version__, "pandas": pd.__version__}
        created = datetime.now(timezone.utc).isoformat()
        summary = {
            "task": task, "primary_metric": primary, "secondary_metric": secondary,
            "best_model": best_name, "best_params": best["params"], "best_tuned": best["tuned"],
            "best_members": best.get("members"),
            "best_cv_score": round(best[f"cv_{primary}_mean"], 4),
            "best_cv_std": round(best[f"cv_{primary}_std"], 4),
            "best_test_metrics": {k: (round(v, 4) if v is not None else None) for k, v in best["test"].items()},
            "baseline_cv_score": None if not base_b else round(base_b[f"cv_{primary}_mean"], 4),
            "n_train": int(len(X)), "n_test": int(len(data.X_test)), "n_features": ctx["n_features"],
            "models_screened": len(rung_log[0]["evaluated"]), "models_finalists": len(final),
            "models_tuned": sum(1 for t in tuning_log.values() if t.get("status") == "ok"),
            "rungs": rung_log, "refit_on_train_and_test": bool(cfg.refit_on_all),
            "warnings": warns, "failures": failures,
            "total_time_s": round(budget.elapsed(), 2), "created_at": created,
            "environment": env, "config": cfg.to_dict(),
        }
        bundle = {
            "model": deploy, "algorithm": best_name, "task": task, "features": list(X.columns),
            "label_encoder_classes": None if le is None else le.classes_.tolist(),
            "params": best["params"], "metrics": summary["best_test_metrics"],
            "primary_metric": primary, "cv_score": summary["best_cv_score"],
            "refit_on_train_and_test": bool(cfg.refit_on_all), "environment": env, "created_at": created,
        }
        return TrainingResult(summary, selection, board, base_b, tuning_log, eliminated, details, bundle, fitted)
