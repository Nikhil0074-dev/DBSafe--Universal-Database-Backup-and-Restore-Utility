from app.utils.hash_utils import digests_equal, sha256_file, sha256_text


def test_sha256_file(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")
    assert sha256_file(f) == sha256_text("hello")
    assert sha256_file(f) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_digests_equal():
    assert digests_equal("ABC", "abc")
    assert not digests_equal("abc", "abd")
    assert not digests_equal(None, "abc")
