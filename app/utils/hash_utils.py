import hashlib
import hmac

CHUNK_SIZE = 1024 * 1024


def sha256_file(path, chunk_size=CHUNK_SIZE):
    """Return the hex SHA-256 digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digests_equal(first, second):
    """Constant-time comparison of two hex digests."""
    if not first or not second:
        return False
    return hmac.compare_digest(str(first).lower(), str(second).lower())
