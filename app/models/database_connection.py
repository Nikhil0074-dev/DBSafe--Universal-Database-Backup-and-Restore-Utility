import json
from dataclasses import dataclass
from typing import Optional
from . import BaseModel


@dataclass
class DatabaseConnection(BaseModel):
    id: int = 0
    name: str = ""
    database_type: str = ""
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    database_name: str = ""
    credential_reference: Optional[str] = None
    extra: Optional[str] = None
    created_at: str = ""

    def extra_dict(self):
        try:
            value = json.loads(self.extra) if self.extra else {}
        except ValueError:
            value = {}
        return value if isinstance(value, dict) else {}

    def to_dict(self):
        """Never includes the (encrypted) password."""
        return {
            "id": self.id, "name": self.name, "database_type": self.database_type,
            "host": self.host, "port": self.port, "username": self.username,
            "database_name": self.database_name, "extra": self.extra_dict(),
            "has_password": bool(self.credential_reference), "created_at": self.created_at,
        }
