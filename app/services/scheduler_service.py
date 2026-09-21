"""Automated backups with APScheduler."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..exceptions import ValidationError
from ..repositories import log_repository, schedule_repository
from ..utils.datetime_utils import now_str
from . import backup_service, storage_service

log = logging.getLogger("dbsafe")

_scheduler = None
_app = None
STORAGE_JOB_ID = "dbsafe_storage_check"


def _job_id(schedule_id):
    return f"schedule_{schedule_id}"


def build_trigger(schedule):
    """Translate a schedule row into an APScheduler cron trigger."""
    hour, minute = (int(part) for part in schedule.schedule_time.split(":"))
    frequency = schedule.frequency
    if frequency == "hourly":
        return CronTrigger(minute=minute)
    if frequency == "every_6_hours":
        return CronTrigger(hour="*/6", minute=minute)
    if frequency == "daily":
        return CronTrigger(hour=hour, minute=minute)
    if frequency == "weekly":
        return CronTrigger(day_of_week=schedule.day_of_week, hour=hour, minute=minute)
    if frequency == "monthly":
        return CronTrigger(day=schedule.day_of_month, hour=hour, minute=minute)
    if frequency == "custom" and schedule.cron_expression:
        return CronTrigger.from_crontab(schedule.cron_expression)
    raise ValidationError(f"Cannot build a trigger for frequency '{frequency}'")


def init_scheduler(app):
    """Start the background scheduler and load all enabled schedules."""
    global _scheduler, _app
    if _scheduler is not None:
        return _scheduler
    _app = app
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.start()
    with app.app_context():
        for schedule in schedule_repository.list_enabled():
            try:
                register_schedule(schedule)
            except Exception:
                log.exception("Could not register schedule %s", schedule.id)
    _scheduler.add_job(_storage_check, "interval", hours=1, id=STORAGE_JOB_ID,
                       replace_existing=True, coalesce=True)
    log.info("Scheduler started")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def register_schedule(schedule):
    """(Re)register a schedule's job. No-op when the scheduler is not running."""
    if _scheduler is None:
        return
    unregister_schedule(schedule.id)
    if not schedule.enabled:
        return
    _scheduler.add_job(
        run_schedule, trigger=build_trigger(schedule), args=[schedule.id], id=_job_id(schedule.id),
        replace_existing=True, max_instances=1, coalesce=True, misfire_grace_time=3600)


def unregister_schedule(schedule_id):
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job(_job_id(schedule_id))
    except Exception:  # job did not exist
        pass


def next_run_time(schedule_id):
    if _scheduler is None:
        return None
    job = _scheduler.get_job(_job_id(schedule_id))
    if job is None or job.next_run_time is None:
        return None
    return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")


def _storage_check():
    with _app.app_context():
        try:
            storage_service.check_storage_and_notify()
        except Exception:
            log.exception("Storage check failed")


def run_schedule(schedule_id):
    """Execute one scheduled backup (called by APScheduler, or by 'run now')."""
    if _app is not None:
        with _app.app_context():
            return execute_schedule(schedule_id)
    return execute_schedule(schedule_id)  # already inside an app context (tests)


def execute_schedule(schedule_id):
    schedule = schedule_repository.get(schedule_id)
    if schedule is None:
        return None
    options = backup_service.BackupOptions(
        backup_type=schedule.backup_type, tables=schedule.table_list(),
        compression=schedule.compression, encryption=bool(schedule.encryption),
        verify=bool(schedule.verify), destination=schedule.destination, kind="scheduled", user=None)
    try:
        pending = backup_service.prepare_backup(schedule.connection_id, options)
        backup = backup_service.execute_backup(pending.id, options)
        status = backup.status
    except Exception as exc:
        log.exception("Scheduled backup for schedule %s failed", schedule_id)
        log_repository.add("scheduled_backup", "failed", str(exc), None, None)
        backup, status = None, "failed"
    schedule_repository.update(schedule_id, last_run_at=now_str(), last_status=status)
    try:
        storage_service.apply_retention(schedule)
    except Exception:
        log.exception("Retention failed for schedule %s", schedule_id)
    return backup
