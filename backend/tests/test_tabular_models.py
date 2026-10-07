import hashlib

import pandas as pd
import pytest

from backend.app.core.errors import AppError
from backend.app.schemas.tabular import TabularConfig
from backend.app.services.tabular.engines import SDVEngine, create_engine
from backend.app.services.tabular.profile import canonical_hash, model_input, resolve_metadata
from backend.app.services.tabular.service import execute
from backend.app.services.tabular.split import split_table
from backend.tests.tabular_fixture import clinical_fixture

pytestmark = pytest.mark.model


@pytest.mark.parametrize("engine", ["gaussian_copula", "ctgan", "tvae"])
def test_real_engine_fit_sample_serialization_and_determinism(
    tmp_path, settings, engine, monkeypatch
):
    frame = clinical_fixture(100)
    path = tmp_path / "source.csv"
    frame.to_csv(path, index=False)
    metadata = resolve_metadata(frame, {}, {})
    config = (
        TabularConfig()
        if engine == "gaussian_copula"
        else TabularConfig(
            epochs=1, batch_size=20, generator_dim=[32], discriminator_dim=[32], embedding_dim=16
        )
    )
    typed = model_input(frame, metadata)
    expected_training, held, split = split_table(typed, config)
    actual_fit = SDVEngine.fit
    observed = []

    def observe_fit(adapter, training, columns):
        observed.append(training.copy())
        return actual_fit(adapter, training, columns)

    monkeypatch.setattr(SDVEngine, "fit", observe_fit)
    columns = [c.model_dump() for c in metadata]
    spec = {
        "engine": engine,
        "source_path": str(path),
        "count": 15,
        "seed": 42,
        "token": "a" * 32,
        "configuration": {
            "tabular": config.model_dump(),
            "columns": columns,
            "metadata_hash": canonical_hash(columns),
            "split": split,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "validation_rules": {},
            "warnings": [],
        },
    }
    result = execute(spec, tmp_path, settings)
    assert len(observed) == 1
    assert list(observed[0].index) == list(expected_training.index)
    assert not set(observed[0].index) & set(held.index)
    assert "patient_id" not in observed[0] and "clinical_notes" not in observed[0]
    assert result["metadata"]["produced_sample_count"] == 15
    assert result["metadata"]["tabular"]["structural_validation"]["passed"]
    output = tmp_path / "generated" / spec["token"]
    generated = pd.read_csv(output / "dataset.csv")
    assert len(generated) == 15 and generated.patient_id.is_unique
    assert "clinical_notes" not in generated and not set(generated.patient_id) & set(
        frame.patient_id
    )
    model = output / "synthesizer.pkl"
    sha = hashlib.sha256(model.read_bytes()).hexdigest()
    adapter = create_engine(engine, config, 42)
    adapter.load(model, sha)
    first, second = adapter.sample(15), adapter.sample(15)
    pd.testing.assert_frame_equal(first, second)
    other = create_engine(engine, config, 43)
    other.load(model, sha)
    assert not first.equals(other.sample(15))
    assert hashlib.sha256((output / "dataset.csv").read_bytes()).hexdigest()
    model.write_bytes(b"tampered")
    with pytest.raises(AppError) as failure:
        adapter.load(model, sha)
    assert failure.value.code == "TABULAR_MODEL_INTEGRITY_FAILED"


@pytest.mark.parametrize("name", ["gaussian_copula", "ctgan", "tvae"])
def test_fresh_cpu_fit_same_seed_reproducible(name):
    frame = clinical_fixture()
    metadata = resolve_metadata(frame, {}, {})
    config = (
        TabularConfig()
        if name == "gaussian_copula"
        else TabularConfig(
            epochs=1, batch_size=20, generator_dim=[32], discriminator_dim=[32], embedding_dim=16
        )
    )
    training, _, _ = split_table(model_input(frame, metadata), config)
    first, second = [create_engine(name, config, 42) for _ in range(2)]
    first.fit(training, metadata)
    second.fit(training, metadata)
    pd.testing.assert_frame_equal(first.sample(20), second.sample(20))
