import os
import re
import shutil
from pathlib import Path

_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_filename(name, default="backup"):
    """Reduce *name* to characters that are safe in a file name."""
    cleaned = _UNSAFE.sub("_", str(name or "")).strip("._")
    return cleaned[:80] or default


def ensure_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def human_size(num_bytes):
    value = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def is_within(path, roots):
    """True if *path* (after resolving symlinks and ``..``) lies inside one of *roots*."""
    try:
        target = Path(path).resolve()
    except (OSError, RuntimeError):
        return False
    for root in roots:
        try:
            target.relative_to(Path(root).resolve())
            return True
        except (ValueError, OSError, RuntimeError):
            continue
    return False


def unique_path(path):
    """Return *path*, or a numbered variant if it already exists."""
    path = Path(path)
    if not path.exists():
        return path
    base, dot, rest = path.name.partition(".")
    for index in range(1, 10000):
        candidate = path.with_name(f"{base}_{index}{dot}{rest}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not find a free file name for {path}")


def remove_quietly(path):
    try:
        Path(path).unlink()
    except (FileNotFoundError, OSError):
        pass


def directory_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


def disk_usage(path):
    """shutil.disk_usage on the nearest existing ancestor of *path*."""
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(str(probe))
