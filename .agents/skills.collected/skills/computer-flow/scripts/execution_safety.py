"""Execution safety primitives: single-desktop lock and cooperative ESC abort.

These are plain Windows mechanisms; no AI is involved at runtime.
"""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class ExecutionBusy(RuntimeError):
    """Another automation session currently owns the desktop."""


class Aborted(RuntimeError):
    """User pressed ESC to cancel the current workflow."""


def _lock_path():
    return Path(tempfile.gettempdir()) / "computer-flow-desktop.lock"


def _read_lock_payload(path):
    """(payload, ctime) of the current lock file, or (None, None) if unreadable."""
    try:
        stat = path.stat()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload, stat.st_ctime
    except (OSError, json.JSONDecodeError):
        return None, None


class DesktopLock:
    """Exclusive access to the shared mouse/keyboard across processes.

    Uses O_EXCL so two scripts cannot both drive the desktop. A holder refreshes
    the lock's mtime while alive, and reclamation additionally requires the
    recorded process to be gone; otherwise a long run would be mistaken for a
    crashed one and a second session would drive the same desktop.

    Reclaim and release both re-read the lock and compare its payload + ctime
    against what this instance saw, so a racing unlink/recreate cannot make us
    delete somebody else's fresh lock.
    """

    def __init__(self, owner=None, stale_after=900, heartbeat=60, path=None):
        self.path = path or _lock_path()
        self.owner = owner or f"{os.getpid()}"
        self.stale_after = stale_after
        self.heartbeat = heartbeat
        self._fd = None
        self._stop = threading.Event()
        self._beat = None
        self._ctime = None

    def acquire(self, timeout=0.0):
        deadline = time.monotonic() + timeout
        while True:
            try:
                self._fd = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                payload = {"pid": os.getpid(), "owner": self.owner, "ts": time.time()}
                os.write(self._fd, json.dumps(payload).encode())
                self._ctime = os.fstat(self._fd).st_ctime
                self._start_heartbeat()
                return self
            except FileExistsError:
                if self._reclaim_if_dead():
                    continue
                if time.monotonic() >= deadline:
                    raise ExecutionBusy(f"desktop lock is held by another session: {self.path}")
                time.sleep(0.1)

    def _start_heartbeat(self):
        def _beat():
            while not self._stop.wait(self.heartbeat):
                try:
                    os.utime(self.path)
                except OSError:
                    return

        self._beat = threading.Thread(target=_beat, name="computer-flow-lock-heartbeat", daemon=True)
        self._beat.start()

    def _holder_is_dead(self, payload):
        """Decide liveness from a payload we already read, so the decision and
        the unlink are based on the same observation."""
        if payload is None:
            return True
        pid = payload.get("pid")
        if not isinstance(pid, int):
            return True
        if pid == os.getpid():
            return True
        try:
            import psutil

            return not psutil.pid_exists(pid)
        except ImportError:
            try:
                os.kill(pid, 0)
                return False
            except OSError:
                return True

    def _reclaim_if_dead(self):
        """Reclaim a lock whose holder is gone, or one that has gone stale.

        Two separate conditions justify reclaiming:
          * the recorded pid no longer exists — the holder crashed; waiting for
            `stale_after` would strand every future run behind a dead process
          * the lock has not been refreshed for `stale_after` seconds — the pid
            may have been recycled, so this is a slower, weaker signal

        The unlink is guarded by the exact (pid, ts, ctime) observed during the
        check; if another process already recreated the lock, the comparison
        fails and we leave the new lock alone.
        """
        payload, ctime = _read_lock_payload(self.path)
        if payload is None or ctime is None:
            return False
        try:
            age = time.time() - self.path.stat().st_mtime
        except OSError:
            return False

        holder_dead = self._holder_is_dead(payload)
        if not holder_dead and age <= self.stale_after:
            return False
        # Re-read right before unlink: a concurrent recreate must not be removed.
        fresh_payload, fresh_ctime = _read_lock_payload(self.path)
        if fresh_payload != payload or fresh_ctime != ctime:
            return False
        try:
            self.path.unlink()
            return True
        except OSError:
            return False

    def release(self):
        self._stop.set()
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            payload, ctime = _read_lock_payload(self.path)
            mine = (
                payload is not None
                and payload.get("pid") == os.getpid()
                and ctime is not None
                and self._ctime is not None
                and ctime == self._ctime
            )
            if mine:
                self.path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # The lock file could not be removed; leave a hint rather than failing silently.
            try:
                self.path.write_text(
                    json.dumps({"pid": os.getpid(), "owner": self.owner, "released": True, "ts": time.time()}),
                    encoding="utf-8",
                )
            except OSError:
                pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


class AbortFlag:
    """Shared flag checked between actions; set by ESC listener or parent process.

    The flag records the process that raised it, so a stale file left by a
    crashed run cannot abort an unrelated later run. When `scope` is given the
    flag lives in a per-scope file (e.g. per window handle), so two concurrent
    automation sessions do not abort each other.
    """

    def __init__(self, path=None, scope=None):
        if path is None:
            name = "computer-flow-abort.flag" if not scope else f"computer-flow-abort-{scope}.flag"
            path = Path(tempfile.gettempdir()) / name
        self.path = path
        self._event = threading.Event()
        self.owner_pid = os.getpid()

    def raise_abort(self):
        self.path.write_text(json.dumps({"pid": self.owner_pid, "ts": time.time()}), encoding="utf-8")
        self._event.set()

    def is_set(self):
        if self._event.is_set():
            return True
        if not self.path.exists():
            return False
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        pid = payload.get("pid")
        if not isinstance(pid, int):
            return False
        if pid == self.owner_pid:
            return True
        # A live external process asked for the abort; a dead one left a stale file.
        try:
            import psutil

            return psutil.pid_exists(pid)
        except ImportError:
            return False

    def clear(self):
        self._event.clear()
        try:
            self.path.unlink()
        except OSError:
            pass

    def check(self):
        if self.is_set():
            raise Aborted(f"workflow aborted by user (flag: {self.path})")


def listen_for_escape(flag, hotkey_vk=0x1B, poll=0.2):
    """Background thread that sets the abort flag when ESC is pressed.

    This runs independently of the action loop, so ESC works even while the
    script is waiting on OCR or a slow window operation.
    """
    import ctypes

    user32 = ctypes.windll.user32

    def _watch():
        pressed = False
        while not flag.is_set():
            try:
                down = bool(user32.GetAsyncKeyState(hotkey_vk) & 0x8000)
            except Exception:
                break
            if down and not pressed:
                flag.raise_abort()
                pressed = True
            elif not down:
                pressed = False
            time.sleep(poll)

    thread = threading.Thread(target=_watch, name="computer-flow-escape", daemon=True)
    thread.start()
    return thread
