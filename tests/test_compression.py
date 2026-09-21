import os

import pytest

from app.exceptions import RestoreError
from app.services import compression_service as comp


@pytest.mark.parametrize("method", ["gzip", "zip"])
def test_roundtrip(tmp_path, method):
    src = tmp_path / "dump.sql"
    src.write_bytes(b"INSERT INTO t VALUES (1);\n" * 5000)
    packed = tmp_path / ("dump" + comp.extension(method))
    out = tmp_path / "out.sql"
    comp.compress_file(src, packed, method)
    assert packed.stat().st_size < src.stat().st_size
    comp.test_integrity(packed, method)
    comp.decompress_file(packed, out, method)
    assert out.read_bytes() == src.read_bytes()


def test_corrupt_gzip_detected(tmp_path):
    src = tmp_path / "d"
    src.write_bytes(os.urandom(50000))
    packed = tmp_path / "d.gz"
    comp.compress_file(src, packed, "gzip")
    data = bytearray(packed.read_bytes())
    data[len(data) // 2] ^= 0xFF
    packed.write_bytes(bytes(data))
    with pytest.raises(RestoreError):
        comp.test_integrity(packed, "gzip")


def test_ratio():
    assert comp.compression_ratio(1000, 250) == 75.0
    assert comp.compression_ratio(0, 0) == 0.0
    assert comp.extension("none") == ""
