import json
from dataclasses import asdict, dataclass
from typing import Optional
from . import BaseModel


@dataclass
class Restore(BaseModel):
    id: int = 0
    backup_id: Optional[int] = None
    backup_code: Optional[str] = None
    connection_id: Optional[int] = None
    connection_name: Optional[str] = None
    target_database: str = ""
    status: str = "running"
    safety_backup_code: Optional[str] = None
    verification_result: Optional[str] = None
    started_at: str = ""
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    initiated_by: Optional[str] = None

    def to_dict(self):
        data = asdict(self)
        try:
            data["verification_result"] = json.loads(self.verification_result) if self.verification_result else None
        except ValueError:
            data["verification_result"] = None
        return data
