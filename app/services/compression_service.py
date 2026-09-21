"""GZIP / ZIP compression of backup files."""
import gzip
import shutil
import zipfile
from pathlib import Path

from ..exceptions import BackupError, RestoreError

BUFFER = 1024 * 1024
EXTENSIONS = {"none": "", "gzip": ".gz", "zip": ".zip"}


def extension(method):
    return EXTENSIONS.get(method, "")


def compress_file(source, destination, method):
    if method == "gzip":
        with open(source, "rb") as fin, gzip.open(destination, "wb", compresslevel=6) as fout:
            shutil.copyfileobj(fin, fout, BUFFER)
    elif method == "zip":
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6,
                             allowZip64=True) as archive:
            archive.write(source, arcname=Path(source).name)
    else:
        raise BackupError(f"Unsupported compression method: {method}")


def decompress_file(source, destination, method):
    try:
        if method == "gzip":
            with gzip.open(source, "rb") as fin, open(destination, "wb") as fout:
                shutil.copyfileobj(fin, fout, BUFFER)
        elif method == "zip":
            with zipfile.ZipFile(source) as archive:
                members = [i for i in archive.infolist() if not i.is_dir()]
                if len(members) != 1:
                    raise RestoreError("The ZIP backup must contain exactly one file")
                with archive.open(members[0]) as fin, open(destination, "wb") as fout:
                    shutil.copyfileobj(fin, fout, BUFFER)
        else:
            raise RestoreError(f"Unsupported compression method: {method}")
    except (OSError, EOFError, zipfile.BadZipFile) as exc:
        raise RestoreError(f"The compressed backup is damaged: {exc}") from exc


def test_integrity(path, method):
    """Read the whole archive to make sure it is not corrupt. Raises RestoreError."""
    try:
        if method == "gzip":
            with gzip.open(path, "rb") as fin:
                while fin.read(BUFFER):
                    pass
        elif method == "zip":
            with zipfile.ZipFile(path) as archive:
                bad = archive.testzip()
                if bad:
                    raise RestoreError(f"Corrupt member in ZIP archive: {bad}")
    except (OSError, EOFError, zipfile.BadZipFile) as exc:
        raise RestoreError(f"The compressed backup is damaged: {exc}") from exc


def compression_ratio(original_size, compressed_size):
    """Percentage of space saved."""
    if not original_size:
        return 0.0
    return round((1 - compressed_size / original_size) * 100, 2)
