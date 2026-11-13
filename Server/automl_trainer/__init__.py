"""automl_trainer: model selection + training for tabular ML (classical models only)."""
from .artifacts import load_bundle, predict, save_run
from .config import TrainingConfig
from .data import DatasetBundle, UpstreamArtifacts, load_dataset, load_upstream
from .pipeline import run_from_directory
from .trainer import AutoTrainer, TrainingResult

__all__ = ["AutoTrainer", "TrainingConfig", "TrainingResult", "DatasetBundle", "UpstreamArtifacts",
           "load_dataset", "load_upstream", "run_from_directory", "load_bundle", "predict", "save_run"]
__version__ = "1.0.0"
