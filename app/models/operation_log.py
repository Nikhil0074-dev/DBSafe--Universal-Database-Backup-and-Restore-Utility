from dataclasses import dataclass
from typing import Optional
from . import BaseModel


@dataclass
class OperationLog(BaseModel):
    id: int = 0
    user_id: Optional[int] = None
    username: Optional[str] = None
    operation: str = ""
    database_name: Optional[str] = None
    status: str = ""
    message: Optional[str] = None
    timestamp: str = ""
