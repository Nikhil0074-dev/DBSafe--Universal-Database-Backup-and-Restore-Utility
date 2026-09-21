"""Safe wrapper around subprocess for the external backup tools."""
import logging
import os
import shutil
import subprocess

from ..exceptions import CommandError

log = logging.getLogger("dbsafe.command")


def find_executable(name, configured=None):
    """Locate an executable, honouring an explicitly configured path first."""
    if configured:
        if os.path.isfile(configured):
            return configured
        raise CommandError(f"Configured path for '{name}' does not exist: {configured}")
    found = shutil.which(name)
    if not found:
        raise CommandError(
            f"'{name}' was not found. Install the database client tools or set the "
            f"path in your .env file."
        )
    return found


def _redact(text, secrets):
    for secret in secrets:
        if secret:
            text = text.replace(str(secret), "********")
    return text


def run_command(args, env=None, stdin_path=None, timeout=None, secrets=()):
    """Run *args* without a shell. Returns stdout text; raises CommandError on failure.

    Passwords must never be passed in *args*; use option files or environment
    variables instead. Anything in *secrets* is masked in error messages.
    """
    full_env = os.environ.copy()
    if env:
        full_env.update({k: str(v) for k, v in env.items()})
    display = " ".join(_redact(str(a), secrets) for a in args)
    log.debug("Running command: %s", display)

    stdin_handle = None
    try:
        if stdin_path:
            stdin_handle = open(stdin_path, "rb")
        proc = subprocess.run(
            [str(a) for a in args],
            env=full_env,
            stdin=stdin_handle,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except FileNotFoundError:
        raise CommandError(f"Executable not found: {args[0]}") from None
    except subprocess.TimeoutExpired:
        raise CommandError(f"Command timed out after {timeout} seconds") from None
    except OSError as exc:
        raise CommandError(f"Could not run command: {exc}") from exc
    finally:
        if stdin_handle:
            stdin_handle.close()

    stderr = _redact(proc.stderr.decode("utf-8", "replace").strip(), secrets)
    if proc.returncode != 0:
        tail = stderr[-1500:] if stderr else "no error output"
        raise CommandError(f"{os.path.basename(str(args[0]))} failed (exit code {proc.returncode}): {tail}")
    return proc.stdout.decode("utf-8", "replace")
