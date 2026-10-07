"""Run the existing tiny CPU model regression strategy in the final image."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from backend.app.schemas.tabular import TabularConfig
from backend.app.services.tabular.engines import create_engine, engine_versions
from backend.app.services.tabular.profile import model_input, resolve_metadata
from backend.app.services.tabular.split import split_table
from backend.tests.tabular_fixture import clinical_fixture


def main():
    frame = clinical_fixture(100)
    metadata = resolve_metadata(frame, {}, {})
    with TemporaryDirectory() as directory:
        for name in ("gaussian_copula", "ctgan", "tvae"):
            config = (
                TabularConfig()
                if name == "gaussian_copula"
                else TabularConfig(
                    epochs=1,
                    batch_size=20,
                    generator_dim=[32],
                    discriminator_dim=[32],
                    embedding_dim=16,
                )
            )
            training, _, _ = split_table(model_input(frame, metadata), config)
            assert "patient_id" not in training and "clinical_notes" not in training
            adapter = create_engine(name, config, 42)
            adapter.fit(training, metadata)
            first = adapter.sample(15)
            assert len(first) == 15
            path = Path(directory) / f"{name}.pkl"
            adapter.save(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            restored = create_engine(name, config, 42)
            restored.load(path, digest)
            pd.testing.assert_frame_equal(first, restored.sample(15))
            print(
                json.dumps(
                    {"engine": name, "passed": True, "rows": 15, "versions": engine_versions()}
                )
            )


if __name__ == "__main__":
    main()
