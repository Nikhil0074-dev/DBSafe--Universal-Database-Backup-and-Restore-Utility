from dataclasses import asdict, dataclass
from typing import Optional

from ..utils.file_utils import human_size
from . import BaseModel, parse_json_list


@dataclass
class Backup(BaseModel):
    id: int = 0
    backup_id: str = ""
    connection_id: Optional[int] = None
    connection_name: Optional[str] = None
    database_type: Optional[str] = None
    database_name: Optional[str] = None
    backup_type: str = "full"
    kind: str = "manual"
    tables: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    original_size: int = 0
    compressed_size: int = 0
    stored_size: int = 0
    compression_type: str = "none"
    compression_enabled: int = 0
    encryption_enabled: int = 0
    checksum: Optional[str] = None
    status: str = "running"
    verification_status: str = "not_verified"
    last_verified_at: Optional[str] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str = ""

    def table_list(self):
        return parse_json_list(self.tables)

    def compression_ratio(self):
        """Percentage of space saved by compression (0 when not compressed)."""
        if not self.compression_enabled or not self.original_size:
            return 0.0
        return round((1 - self.compressed_size / self.original_size) * 100, 2)

    def to_dict(self):
        data = asdict(self)
        data.pop("file_path", None)  # do not leak server paths
        data["tables"] = self.table_list()
        data["compression_enabled"] = bool(self.compression_enabled)
        data["encryption_enabled"] = bool(self.encryption_enabled)
        data["compression_ratio"] = self.compression_ratio()
        data["original_size_human"] = human_size(self.original_size)
        data["compressed_size_human"] = human_size(self.compressed_size)
        data["stored_size_human"] = human_size(self.stored_size)
        return data
