"""The only SDV boundary. Never load models from uploaded/user-selected files."""

import random
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from ...config import Settings
from ...core.errors import AppError
from ...schemas.tabular import ColumnMetadata, TabularConfig
from ...storage.local import hash_stream

SUPPORTED = {"sdv": "1.25.0", "rdt": "1.18.2", "ctgan": "0.11.1", "copulas": "0.14.1"}


def engine_versions() -> dict:
    try:
        return {name: version(name) for name in SUPPORTED}
    except PackageNotFoundError:
        return {}


def available_engines() -> list[dict[str, str]]:
    if engine_versions() != SUPPORTED:
        return []
    try:
        from sdv.metadata import Metadata  # noqa: F401
        from sdv.single_table import (  # noqa: F401
            CTGANSynthesizer,
            GaussianCopulaSynthesizer,
            TVAESynthesizer,
        )
    except (ImportError, RuntimeError):
        return []
    return [
        {
            "name": name,
            "maturity": "Stable" if name == "gaussian_copula" else "Beta",
            "version": SUPPORTED["sdv"],
        }
        for name in ("gaussian_copula", "ctgan", "tvae")
    ]


def validate_config(engine: str, config: TabularConfig, count: int, settings: Settings):
    if type(count) is not int or count < 1:
        raise AppError("Requested rows must be a positive integer", "TABULAR_CONFIG_INVALID")
    if count > settings.tabular_max_generated_rows:
        raise AppError(
            "Requested rows exceed the tabular generation limit",
            "TABULAR_GENERATION_LIMIT_EXCEEDED",
        )
    if engine not in {"gaussian_copula", "ctgan", "tvae"}:
        raise AppError("Tabular engine is unavailable", "TABULAR_ENGINE_NOT_AVAILABLE", 501)
    if engine != "gaussian_copula" and config.epochs > getattr(settings, f"{engine}_max_epochs"):
        raise AppError(
            "Requested epochs exceed the training limit", "TABULAR_TRAINING_LIMIT_EXCEEDED"
        )
    neural_fields = {
        "epochs",
        "batch_size",
        "embedding_dim",
        "generator_dim",
        "discriminator_dim",
        "cuda",
    }
    if engine == "gaussian_copula" and config.model_fields_set & neural_fields:
        raise AppError(
            "Neural configuration does not apply to Gaussian Copula", "TABULAR_CONFIG_INVALID"
        )
    if engine != "gaussian_copula" and "default_distribution" in config.model_fields_set:
        raise AppError(
            "default_distribution only applies to Gaussian Copula", "TABULAR_CONFIG_INVALID"
        )
    if config.cuda:
        import torch

        if not torch.cuda.is_available():
            raise AppError(
                "CUDA was explicitly requested but is unavailable", "TABULAR_CONFIG_INVALID"
            )


def validate_training_size(
    engine: str, training: pd.DataFrame, metadata: list[ColumnMetadata], settings: Settings
):
    if engine == "gaussian_copula":
        return
    # Conservative upper estimate for CTGAN/TVAE one-hot categorical features and
    # up to 10 mixture components + missingness per continuous feature. Values
    # are never stored; this operational estimate is not a performance guarantee.
    width = sum(
        int(training[c.name].nunique(dropna=False)) + 1
        if c.semantic_type == "categorical"
        else 2
        if c.semantic_type == "boolean"
        else 16
        for c in metadata
        if c.role == "MODELLED"
    )
    if len(training) * width > settings.tabular_max_transformed_cells:
        raise AppError(
            "Estimated neural transformed table exceeds the configured cell limit; exclude high-cardinality columns or revise types",
            "TABULAR_DATASET_TOO_LARGE",
        )


class TabularSynthesizer(Protocol):
    def fit(self, training: pd.DataFrame, metadata: list[ColumnMetadata]) -> None: ...
    def sample(self, count: int) -> pd.DataFrame: ...
    def save(self, path: Path) -> None: ...
    def load(self, path: Path, expected_sha256: str) -> None: ...
    def describe(self) -> dict: ...
    def validate_config(self, count: int, settings: Settings) -> None: ...


class SDVEngine:
    name = ""
    class_name = ""

    def __init__(self, config: TabularConfig, seed: int):
        if engine_versions() != SUPPORTED:
            raise AppError(
                "Install the pinned tabular dependencies", "TABULAR_ENGINE_NOT_AVAILABLE", 501
            )
        self.config, self.seed, self.model = config, seed, None

    def validate_config(self, count: int, settings: Settings):
        validate_config(self.name, self.config, count, settings)

    def parameters(self) -> dict:
        return {}

    def fit(self, training: pd.DataFrame, metadata: list[ColumnMetadata]):
        import torch
        from sdv import single_table
        from sdv.metadata import Metadata

        random.seed(self.seed)
        np.random.seed(self.seed)
        torch.manual_seed(self.seed)
        torch.set_num_threads(1)
        if self.config.cuda:
            torch.cuda.manual_seed_all(self.seed)
        sdv_metadata = Metadata.detect_from_dataframe(
            training, table_name="clinical", infer_keys=None
        )
        for column in metadata:
            if column.role == "MODELLED":
                options = {"sdtype": column.sdv_type}
                if column.semantic_type == "datetime" and column.datetime_format:
                    options["datetime_format"] = column.datetime_format
                sdv_metadata.update_column(column.name, table_name="clinical", **options)
        try:
            sdv_metadata.validate()
            sdv_metadata.validate_data({"clinical": training})
        except (ValueError, TypeError) as error:
            raise AppError(
                "Configured metadata is invalid for training data", "TABULAR_METADATA_INVALID"
            ) from error
        self.model = getattr(single_table, self.class_name)(sdv_metadata, **self.parameters())
        try:
            self.model.fit(training)
        except Exception as error:
            raise AppError("Tabular model training failed", "TABULAR_TRAINING_FAILED") from error

    def sample(self, count: int) -> pd.DataFrame:
        try:
            self.model.reset_sampling()
            # SDV 1.25.0 has no public sampling-seed setter. This one version-guarded
            # bridge is necessary for user seeds; all metadata/model APIs are public.
            self.model._set_random_state(self.seed)
            return self.model.sample(num_rows=count, output_file_path="disable")
        except Exception as error:
            raise AppError("Tabular model sampling failed", "TABULAR_SAMPLING_FAILED") from error

    def save(self, path: Path):
        self.model.save(filepath=str(path))

    def load(self, path: Path, expected_sha256: str):
        """Internal artifact only; caller supplies a trusted registry checksum."""
        from sdv.utils import load_synthesizer

        with path.open("rb") as source:
            if hash_stream(source).sha256 != expected_sha256:
                raise AppError(
                    "Trusted model integrity check failed", "TABULAR_MODEL_INTEGRITY_FAILED"
                )
        model = load_synthesizer(filepath=str(path))
        if type(model).__name__ != self.class_name:
            raise AppError("Trusted model engine is incompatible", "TABULAR_MODEL_INTEGRITY_FAILED")
        self.model = model

    def describe(self) -> dict:
        return {
            "engine": self.name,
            "engine_version": SUPPORTED["sdv"],
            "library_versions": engine_versions(),
            "engine_parameters": self.parameters(),
            "device": "cuda" if self.config.cuda and self.name != "gaussian_copula" else "cpu",
            "reproducibility": "same-runtime deterministic CPU; neural/GPU best-effort across runtimes",
        }


class GaussianCopulaEngine(SDVEngine):
    name, class_name = "gaussian_copula", "GaussianCopulaSynthesizer"

    def parameters(self):
        return {"default_distribution": self.config.default_distribution}


class CTGANEngine(SDVEngine):
    name, class_name = "ctgan", "CTGANSynthesizer"

    def parameters(self):
        return {
            "epochs": self.config.epochs,
            "batch_size": self.config.batch_size,
            "embedding_dim": self.config.embedding_dim,
            "generator_dim": tuple(self.config.generator_dim),
            "discriminator_dim": tuple(self.config.discriminator_dim),
            "cuda": self.config.cuda,
            "verbose": False,
        }


class TVAEEngine(SDVEngine):
    name, class_name = "tvae", "TVAESynthesizer"

    def parameters(self):
        return {
            "epochs": self.config.epochs,
            "batch_size": self.config.batch_size,
            "embedding_dim": self.config.embedding_dim,
            "compress_dims": tuple(self.config.discriminator_dim),
            "decompress_dims": tuple(self.config.generator_dim),
            "cuda": self.config.cuda,
            "verbose": False,
        }


def create_engine(name: str, config: TabularConfig, seed: int) -> TabularSynthesizer:
    adapters = {"gaussian_copula": GaussianCopulaEngine, "ctgan": CTGANEngine, "tvae": TVAEEngine}
    if name not in adapters:
        raise AppError("Tabular engine is unavailable", "TABULAR_ENGINE_NOT_AVAILABLE", 501)
    return adapters[name](config, seed)
