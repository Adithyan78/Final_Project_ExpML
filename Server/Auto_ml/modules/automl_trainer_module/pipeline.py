"""One-call entry point for wiring this stage into the AutoML pipeline."""
from __future__ import annotations

from pathlib import Path

from .config import TrainingConfig
from .data import load_dataset, load_upstream
from .trainer import AutoTrainer, TrainingResult


def run_from_directory(input_dir: str | Path, out_dir: str | Path | None = None,
                       profile_path: str | Path | None = None, config: TrainingConfig | None = None,
                       target_col: str | None = None) -> TrainingResult:
    """Load preprocessing outputs from ``input_dir``, train, and (if out_dir given) save everything."""
    data = load_dataset(input_dir, target_col)
    upstream = load_upstream(input_dir, profile_path)
    result = AutoTrainer(config).run(data, upstream)
    if out_dir:
        result.save(out_dir)
    return result
