from dataclasses import dataclass
from . import BaseModel


@dataclass
class User(BaseModel):
    id: int = 0
    username: str = ""
    password_hash: str = ""
    role: str = "operator"
    created_at: str = ""

    def to_dict(self):
        return {"id": self.id, "username": self.username, "role": self.role,
                "created_at": self.created_at}
