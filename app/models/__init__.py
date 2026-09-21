"""Plain data models. Repositories return these; ``to_dict`` gives API-safe output."""
import json
from dataclasses import asdict, fields


class BaseModel:
    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in dict(row).items() if k in names})

    def to_dict(self):
        return asdict(self)


def parse_json_list(text):
    if not text:
        return []
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []
