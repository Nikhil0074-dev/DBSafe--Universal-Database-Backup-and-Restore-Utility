from dataclasses import asdict, dataclass
from typing import Optional
from . import BaseModel, parse_json_list


@dataclass
class Schedule(BaseModel):
    id: int = 0
    connection_id: int = 0
    name: Optional[str] = None
    frequency: str = "daily"
    schedule_time: str = "02:00"
    day_of_week: int = 0
    day_of_month: int = 1
    cron_expression: Optional[str] = None
    backup_type: str = "full"
    tables: Optional[str] = None
    compression: str = "gzip"
    encryption: int = 0
    verify: int = 1
    destination: Optional[str] = None
    retention_days: int = 30
    keep_daily: int = 0
    keep_weekly: int = 0
    keep_monthly: int = 0
    enabled: int = 1
    last_run_at: Optional[str] = None
    last_status: Optional[str] = None
    created_at: str = ""

    def table_list(self):
        return parse_json_list(self.tables)

    def to_dict(self):
        data = asdict(self)
        data["tables"] = self.table_list()
        for key in ("encryption", "verify", "enabled"):
            data[key] = bool(data[key])
        return data
