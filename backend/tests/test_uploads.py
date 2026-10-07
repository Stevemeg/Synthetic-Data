from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from backend.app.core.errors import AppError
from backend.app.utils.uploads import saved_csv


def test_sanitized_filename_and_cleanup(tmp_path):
    upload = FileStorage(
        BytesIO(b"1,2,label"), filename="../../patient.csv", content_type="text/csv"
    )
    with saved_csv(upload, tmp_path, 100) as path:
        assert path.name == "patient.csv"
        assert path.parent.parent == tmp_path
        assert path.read_bytes() == b"1,2,label"
    assert not list(tmp_path.iterdir())


def test_file_size_bound_and_cleanup(tmp_path):
    upload = FileStorage(BytesIO(b"x" * 101), filename="source.csv", content_type="text/csv")
    with pytest.raises(AppError) as caught:
        with saved_csv(upload, tmp_path, 100):
            pytest.fail("Oversized upload was accepted")
    assert caught.value.status == 413
    assert not list(tmp_path.iterdir())


def test_cleanup_on_consumer_failure(tmp_path):
    upload = FileStorage(BytesIO(b"1,2,3"), filename="source.csv", content_type="text/csv")
    with pytest.raises(RuntimeError):
        with saved_csv(upload, tmp_path, 100):
            raise RuntimeError("consumer failed")
    assert not list(tmp_path.iterdir())
