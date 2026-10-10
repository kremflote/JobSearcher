"""Run lock (`DATA_DIR/run.lock`, ARCHITECTURE §10.1): stops CLI, scheduler and "Kjør nå"
from collecting at the same time.

The lock file is created exclusively and holds the owner's PID and start time. A lock whose
process is gone, or which is older than `STALE_AFTER`, is taken over.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

from jobsearcher.config import env

log = logging.getLogger(__name__)

STALE_AFTER_S = 2 * 60 * 60


class RunLockedError(RuntimeError):
    """Another run holds the lock."""


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            # Access denied means the process exists (owned by someone else).
            return ctypes.get_last_error() == 5
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # POSIX only: signal 0 checks existence
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class RunLock:
    """Context manager: `with RunLock(): ...`. Raises `RunLockedError` if held."""

    def __init__(self, path: Path | None = None, stale_after_s: float = STALE_AFTER_S) -> None:
        self.path = path or env().lock_path
        self.stale_after_s = stale_after_s
        self._held = False

    def _is_stale(self) -> bool:
        try:
            info = json.loads(self.path.read_text(encoding="utf-8"))
            pid, started = int(info["pid"]), float(info["started"])
        except (OSError, ValueError, KeyError, TypeError):
            # Unreadable: stale only if the file itself is old (it may be mid-write).
            try:
                return time.time() - self.path.stat().st_mtime > 60
            except OSError:
                return True
        if time.time() - started > self.stale_after_s:
            return True
        return not pid_alive(pid)

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._is_stale():
                    log.warning("removing stale run lock", extra={"data": {"path": str(self.path)}})
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                raise RunLockedError(f"En kjøring pågår allerede ({self.path}).") from None
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"pid": os.getpid(), "started": time.time()}, f)
            self._held = True
            return
        raise RunLockedError(f"Kunne ikke ta låsen {self.path}.")

    def release(self) -> None:
        if self._held:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            self._held = False

    def __enter__(self) -> RunLock:
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
