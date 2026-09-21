# Architecture

```
Browser (Bootstrap + JS)  ->  Flask REST API + pages  ->  Services  ->  Adapters  ->  Databases
                                                     \->  Repositories -> SQLite metadata (dbsafe.db)
```

| Layer | Path | Responsibility |
|---|---|---|
| Pages / API | `app/api/` | HTTP routes, authentication, role checks, CSRF, JSON validation |
| Services | `app/services/` | backup, restore, verification, compression, encryption, scheduler, storage, notifications |
| Adapters | `app/adapters/` | one class per database: connect, list, backup, restore, verify |
| Repositories | `app/repositories/` | all SQL for the metadata database |
| Models | `app/models/` | dataclasses; `to_dict()` never exposes secrets or server paths |
| Utils | `app/utils/` | hashing, files, validation, safe command runner |
| Config | `config/` | environment-driven configuration, logging |

## Backup pipeline
`adapter.create_backup` → raw file → compress (gzip/zip) → encrypt (AES-256-GCM) → SHA-256 → atomic move to
storage → metadata row → deep verification (checksum + decrypt/decompress test).

## Restore pipeline
verify checksum → safety backup of target (if it exists) → decrypt → decompress → `adapter.restore_backup` →
`adapter.verify_restore` (integrity + expected tables) → restore log. A failed safety backup aborts the restore.

## Adding a database
Subclass `DatabaseAdapter` (`app/adapters/base_adapter.py`), implement the abstract methods, register the class in
`app/adapters/__init__.py` and add the type to `DB_TYPES` in `app/utils/validation.py` and the schema CHECK.

## Concurrency
Backup/restore requests return `202` and run in a small thread pool; the UI polls the record. Each repository call
uses its own short SQLite connection (WAL mode).

## Encrypted file format
`DBSAFE01 | scrypt salt(16) | nonce prefix(4) | { len(4) | AES-GCM chunk }*` — 1 MiB chunks, per-chunk nonce, the
final chunk is authenticated as final so truncation is detected. Key = scrypt(passphrase, salt).
