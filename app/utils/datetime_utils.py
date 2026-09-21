from datetime import datetime

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def now():
    return datetime.now()


def now_str():
    return datetime.now().strftime(DATETIME_FORMAT)


def filename_timestamp(moment=None):
    """Timestamp used in backup file names, e.g. 2026-09-20_11-30-45."""
    return (moment or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")


def parse_datetime(value):
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except (TypeError, ValueError):
        return None


def duration_str(seconds):
    seconds = int(round(seconds or 0))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"
