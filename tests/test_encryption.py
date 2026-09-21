import os

import pytest

from app.exceptions import EncryptionError
from app.services import encryption_service as enc

KEY = "a-long-enough-passphrase"


def roundtrip(tmp_path, payload, key=KEY):
    src, mid, out = tmp_path / "s", tmp_path / "m", tmp_path / "o"
    src.write_bytes(payload)
    enc.encrypt_file(src, mid, key)
    enc.decrypt_file(mid, out, key)
    return mid, out.read_bytes()


def test_roundtrip_small_empty_and_multichunk(tmp_path):
    for payload in (b"", b"x", os.urandom(1000), os.urandom(enc.CHUNK_SIZE * 2 + 17),
                    os.urandom(enc.CHUNK_SIZE)):
        _, result = roundtrip(tmp_path, payload)
        assert result == payload


def test_ciphertext_is_not_plaintext_and_differs_each_time(tmp_path):
    src = tmp_path / "s"
    src.write_bytes(b"secret data" * 10)
    enc.encrypt_file(src, tmp_path / "a", KEY)
    enc.encrypt_file(src, tmp_path / "b", KEY)
    assert b"secret data" not in (tmp_path / "a").read_bytes()
    assert (tmp_path / "a").read_bytes() != (tmp_path / "b").read_bytes()


def test_wrong_key(tmp_path):
    mid, _ = roundtrip(tmp_path, b"data")
    with pytest.raises(EncryptionError, match="wrong encryption key"):
        enc.decrypt_file(mid, tmp_path / "x", "another-passphrase-1")


def test_tampering_and_truncation_detected(tmp_path):
    payload = os.urandom(enc.CHUNK_SIZE * 2 + 5)
    mid, _ = roundtrip(tmp_path, payload)
    data = bytearray(mid.read_bytes())
    tampered = tmp_path / "t"
    data[100] ^= 1
    tampered.write_bytes(bytes(data))
    with pytest.raises(EncryptionError):
        enc.decrypt_file(tampered, tmp_path / "x", KEY)

    original = mid.read_bytes()
    # cut exactly after the first chunk -> final-flag check must fail
    first_len = int.from_bytes(original[28:32], "big")
    truncated = tmp_path / "trunc"
    truncated.write_bytes(original[:32 + first_len])
    with pytest.raises(EncryptionError):
        enc.decrypt_file(truncated, tmp_path / "x", KEY)
    truncated.write_bytes(original[:-10])
    with pytest.raises(EncryptionError):
        enc.decrypt_file(truncated, tmp_path / "x", KEY)


def test_not_an_encrypted_file(tmp_path):
    f = tmp_path / "plain"
    f.write_bytes(b"this is not encrypted at all, sorry")
    with pytest.raises(EncryptionError, match="not a DBSafe"):
        enc.decrypt_file(f, tmp_path / "x", KEY)


def test_short_key_rejected(tmp_path):
    f = tmp_path / "p"
    f.write_bytes(b"x")
    with pytest.raises(EncryptionError):
        enc.encrypt_file(f, tmp_path / "e", "short")


def test_secret_roundtrip(app):
    with app.app_context():
        token = enc.encrypt_secret("p@ss w0rd")
        assert "p@ss" not in token
        assert enc.decrypt_secret(token) == "p@ss w0rd"
