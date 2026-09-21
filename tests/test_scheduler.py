import pytest

from app.exceptions import ValidationError
from app.models.schedule import Schedule
from app.repositories import backup_repository
from app.services import scheduler_service


def sched(**kw):
    base = dict(id=1, connection_id=1, frequency="daily", schedule_time="02:30")
    base.update(kw)
    return Schedule(**base)


def fields(trigger):
    return {f.name: str(f) for f in trigger.fields}


def test_trigger_building():
    assert fields(scheduler_service.build_trigger(sched()))["hour"] == "2"
    assert fields(scheduler_service.build_trigger(sched()))["minute"] == "30"
    assert fields(scheduler_service.build_trigger(sched(frequency="hourly")))["minute"] == "30"
    assert fields(scheduler_service.build_trigger(sched(frequency="every_6_hours")))["hour"] == "*/6"
    assert fields(scheduler_service.build_trigger(sched(frequency="weekly", day_of_week=2)))["day_of_week"] == "2"
    assert fields(scheduler_service.build_trigger(sched(frequency="monthly", day_of_month=5)))["day"] == "5"
    assert fields(scheduler_service.build_trigger(sched(frequency="custom", cron_expression="0 */4 * * *")))["hour"] == "*/4"
    with pytest.raises(ValidationError):
        scheduler_service.build_trigger(sched(frequency="custom", cron_expression=None))


def test_schedule_crud_api(admin, operator, connection):
    payload = {"connection_id": connection["id"], "frequency": "daily", "schedule_time": "03:15",
               "retention_days": 7, "keep_weekly": 4}
    assert operator.post("/api/schedules", payload).status_code == 403
    r = admin.post("/api/schedules", payload)
    assert r.status_code == 201, r.get_json()
    s = r.get_json()
    assert s["enabled"] and s["connection_name"] == "Shop" and s["keep_weekly"] == 4
    assert operator.get("/api/schedules").status_code == 200

    r = admin.put(f"/api/schedules/{s['id']}", {"enabled": False, "schedule_time": "04:00"})
    assert r.status_code == 200 and r.get_json()["enabled"] is False and r.get_json()["schedule_time"] == "04:00"

    for bad in ({"frequency": "yearly"}, {"schedule_time": "25:00"},
                {"frequency": "custom"}, {"frequency": "custom", "cron_expression": "nonsense"}):
        assert admin.post("/api/schedules", {**payload, **bad}).status_code == 400, bad
    assert admin.post("/api/schedules", {**payload, "connection_id": 999}).status_code == 404

    assert admin.delete(f"/api/schedules/{s['id']}").status_code == 200
    assert admin.delete(f"/api/schedules/{s['id']}").status_code == 404


def test_scheduled_run_creates_backup_and_applies_retention(app, admin, connection):
    s = admin.post("/api/schedules", {"connection_id": connection["id"], "frequency": "daily",
                                      "retention_days": 0, "keep_daily": 1}).get_json()
    with app.app_context():
        for _ in range(3):
            scheduler_service.execute_schedule(s["id"])
        items, total = backup_repository.search(kind="scheduled")
        # keep_daily=1 -> only the newest backup of today survives
        assert total == 1 and items[0].created_by == "scheduler" and items[0].status == "success"
    row = admin.get("/api/schedules").get_json()["items"][0]
    assert row["last_status"] == "success" and row["last_run_at"]


def test_scheduler_registers_jobs(app, admin, connection):
    try:
        scheduler_service.init_scheduler(app)
        s = admin.post("/api/schedules", {"connection_id": connection["id"], "frequency": "hourly"}).get_json()
        assert scheduler_service.next_run_time(s["id"])
        admin.put(f"/api/schedules/{s['id']}", {"enabled": False})
        assert scheduler_service.next_run_time(s["id"]) is None
        admin.delete(f"/api/schedules/{s['id']}")
    finally:
        scheduler_service.shutdown_scheduler()


def test_deleting_connection_removes_schedules_but_keeps_history(admin, connection):
    admin.post("/api/backups", {"connection_id": connection["id"], "sync": True})
    admin.post("/api/schedules", {"connection_id": connection["id"], "frequency": "daily"})
    assert admin.delete(f"/api/databases/{connection['id']}").status_code == 200
    assert admin.get("/api/schedules").get_json()["items"] == []
    assert admin.get("/api/backups").get_json()["total"] == 1
