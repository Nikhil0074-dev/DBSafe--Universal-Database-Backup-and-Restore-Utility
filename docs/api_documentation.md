# REST API

JSON over HTTP, session cookie authentication. Every `POST/PUT/DELETE` needs the header
`X-CSRF-Token` (get it from `GET /api/auth/csrf`, and use the fresh value returned by login).
Errors: `{"error": "message"}` with a 4xx/5xx status. Lists: `{"items": [...]}` (paged lists add `total`, `page`, `per_page`).
Roles: **A** = administrator only, **any** = any signed-in user.

## Authentication
| Method | Path | Role | Notes |
|---|---|---|---|
| GET | `/api/auth/csrf` | – | returns `csrf_token` |
| POST | `/api/auth/login` | – | `{username, password}`; 5 failures → 429 for 5 min |
| POST | `/api/auth/logout` | – | |
| GET | `/api/auth/me` | any | |
| POST | `/api/auth/change-password` | any | `{current_password, new_password}` |
| GET/POST | `/api/users` | A | POST `{username, password, role}` |
| PUT/DELETE | `/api/users/{id}` | A | PUT `{role?, password?}` |

## Databases
| Method | Path | Role |
|---|---|---|
| GET | `/api/databases`, `/api/databases/{id}` | any |
| POST | `/api/databases` | A — `{name, database_type, host, port, username, password, database_name, extra}` |
| PUT/DELETE | `/api/databases/{id}` | A (empty password on PUT keeps the stored one) |
| POST | `/api/databases/{id}/test` | any → `{ok, message, server, version, ...}` |
| POST | `/api/databases/test` | A — test unsaved details (`connection_id` reuses a stored password) |
| GET | `/api/databases/{id}/tables`, `/info` | any |

`database_type`: `mysql`, `postgresql`, `sqlite` (database_name = file path), `mongodb`.

## Backups
| Method | Path | Role |
|---|---|---|
| GET | `/api/backups?q&status&connection_id&kind&sort=created_at\|size\|database\|status&order&page&per_page` | any |
| POST | `/api/backups` | any — `{connection_id, backup_type: full\|selective, tables[], compression: none\|gzip\|zip, encryption, verify, destination (A only), sync}`; `202` (async) or `201` when `sync: true` |
| GET | `/api/backups/{id or BK-code}` | any |
| DELETE | `/api/backups/{id}` | A |
| POST | `/api/backups/{id}/verify` | any — `{deep}` → `{status: valid\|invalid\|missing, message}` |

## Restore
| Method | Path | Role |
|---|---|---|
| POST | `/api/restore` | any — `{backup_id, connection_id, target_database?, safety_backup, confirm: true, sync}` |
| GET | `/api/restores`, `/api/restores/{id}` | any |

## Schedules, storage, logs
| Method | Path | Role |
|---|---|---|
| GET | `/api/schedules` | any |
| POST/PUT/DELETE | `/api/schedules[/{id}]` | A — `{connection_id, frequency: hourly\|every_6_hours\|daily\|weekly\|monthly\|custom, schedule_time "HH:MM", day_of_week 0-6, day_of_month 1-28, cron_expression, backup options, retention_days, keep_daily, keep_weekly, keep_monthly, enabled}` |
| POST | `/api/schedules/{id}/run` | A |
| GET | `/api/storage`, `/api/dashboard` | any |
| POST | `/api/storage/cleanup` | A |
| GET | `/api/logs?q&status&operation&page&per_page` | A |
