"""Unit tests for execution_safety: lock ownership, reclamation, abort scoping."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from execution_safety import Aborted, AbortFlag, DesktopLock, ExecutionBusy


class DesktopLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "lock"

    def test_acquire_release_cycle(self):
        lock = DesktopLock(path=self.path, owner="a")
        lock.acquire()
        self.assertTrue(self.path.exists())
        lock.release()
        self.assertFalse(self.path.exists())

    def test_second_acquire_fails_busy(self):
        a = DesktopLock(path=self.path, owner="a")
        a.acquire()
        try:
            b = DesktopLock(path=self.path, owner="b")
            with self.assertRaises(ExecutionBusy):
                b.acquire(timeout=0.2)
        finally:
            a.release()

    def test_release_does_not_delete_others_lock(self):
        # Simulate: we held the lock, lost the fd, path was unlinked externally,
        # then someone else acquired it. Our release must not remove theirs.
        ours = DesktopLock(path=self.path, owner="ours")
        ours.acquire()
        os.close(ours._fd)
        ours._fd = None
        os.unlink(self.path)
        theirs = DesktopLock(path=self.path, owner="theirs")
        theirs.acquire()
        try:
            ours._ctime = 12345.0
            ours.release()
            self.assertTrue(self.path.exists())
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.assertEqual(payload["owner"], "theirs")
        finally:
            theirs.release()

    def test_reclaim_succeeds_when_holder_dead_and_stale(self):
        # A dead pid + very old mtime means the previous holder is gone.
        self.path.write_text(
            json.dumps({"pid": 99999999, "owner": "dead", "ts": time.time() - 7200}),
            encoding="utf-8",
        )
        old = time.time() - 7200
        os.utime(self.path, (old, old))
        lock = DesktopLock(path=self.path, owner="fresh", stale_after=60, heartbeat=9999)
        lock.acquire(timeout=1)
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.assertEqual(payload["owner"], "fresh")
        finally:
            lock.release()

    def test_reclaim_refuses_when_lock_is_fresh(self):
        # Another live holder: stale check fails because mtime is fresh.
        holder = DesktopLock(path=self.path, owner="holder")
        holder.acquire()
        try:
            waiter = DesktopLock(path=self.path, owner="waiter", stale_after=0, heartbeat=9999)
            with self.assertRaises(ExecutionBusy):
                waiter.acquire(timeout=0.2)
        finally:
            holder.release()


class AbortFlagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_scope_produces_distinct_paths(self):
        a = AbortFlag(scope="111")
        b = AbortFlag(scope="222")
        self.assertNotEqual(a.path, b.path)

    def test_scoped_flags_are_isolated(self):
        a = AbortFlag(path=self.tmp / "a.flag")
        b = AbortFlag(path=self.tmp / "b.flag")
        a.raise_abort()
        with self.assertRaises(Aborted):
            a.check()
        b.check()  # must not raise

    def test_clear_removes_stale_flag(self):
        flag = AbortFlag(path=self.tmp / "x.flag")
        flag.raise_abort()
        flag.clear()
        flag.check()  # must not raise after clear

    def test_malformed_flag_is_treated_as_unset(self):
        path = self.tmp / "broken.flag"
        path.write_text("not json {", encoding="utf-8")
        flag = AbortFlag(path=path)
        flag.check()  # must not raise


if __name__ == "__main__":
    unittest.main()
