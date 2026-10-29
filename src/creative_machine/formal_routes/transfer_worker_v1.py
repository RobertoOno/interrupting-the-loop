"""Lifetime local worker ownership with a permanent no-restart claim.

Use one canonical registry across cooperating copies. This is not a distributed
lease, PID-liveness heuristic, financial reservation or scientific admission.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

from .transfer_design_v1 import encoded, sha

VERSION = "p3_transfer_worker_v1"


class WorkerOwnershipError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise WorkerOwnershipError(message)


class WorkerClaim:
    """Single-use context. Exiting unlocks/closes but never removes the claim.

    No stale-claim takeover, expiration, completion-based reuse or fork transfer.
    After any ambiguous creation/write, preserve the file and stop. Call
    assert_owned immediately before each admission and external request.
    """
    def __init__(self, registry: Path, run_id: str, execution_plan_sha256: str):
        require(isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", run_id), "invalid run identity")
        require(isinstance(execution_plan_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", execution_plan_sha256), "plan hash required")
        self.registry = Path(registry)
        self.run_id = run_id
        self.plan_sha256 = execution_plan_sha256
        self.name = run_id + ".claim.json"
        self._parent = self._fd = None
        self._attempted = False
        self._pid = None
        self._bytes = None

    def __enter__(self):
        require(not self._attempted, "worker claim object cannot be reused")
        self._attempted = True
        try:
            # Registry's parent is supplied by the trusted host, never by a
            # model or archived path. Do not recursively create arbitrary trees.
            self.registry.mkdir(exist_ok=True)
            self._parent = os.open(self.registry, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            self._parent_identity = self._identity(os.fstat(self._parent))
            self._fd = os.open(self.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                               0o600, dir_fd=self._parent)
            os.set_inheritable(self._fd, False)
            os.set_inheritable(self._parent, False)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._pid = os.getpid()
            self._receipt = {"version": VERSION, "run_id": self.run_id,
                "execution_plan_sha256": self.plan_sha256, "pid": self._pid,
                "owner_nonce": uuid4().hex, "claimed_at": datetime.now(timezone.utc).isoformat(),
                "restart_permitted": False, "inference_admitted": False}
            self._bytes = encoded(self._receipt)
            offset = 0
            while offset < len(self._bytes):
                written = os.write(self._fd, self._bytes[offset:])
                require(written > 0, "short worker claim write")
                offset += written
            os.fsync(self._fd)
            os.fsync(self._parent)
            self._file_identity = self._identity(os.fstat(self._fd))
            self.assert_owned()
            return self
        except Exception:
            self.close()
            raise

    @staticmethod
    def _identity(info):
        return info.st_dev, info.st_ino

    def assert_owned(self):
        require(self._fd is not None and self._parent is not None and self._pid == os.getpid(),
                "worker ownership closed, absent or inherited across fork")
        parent = os.stat(self.registry, follow_symlinks=False)
        require(stat.S_ISDIR(parent.st_mode) and self._identity(parent) == self._parent_identity
                == self._identity(os.fstat(self._parent)), "worker registry replaced")
        info = os.stat(self.name, dir_fd=self._parent, follow_symlinks=False)
        opened = os.fstat(self._fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == opened.st_nlink == 1
                and self._identity(info) == self._file_identity == self._identity(opened), "worker claim replaced or linked")
        require(info.st_size == opened.st_size == len(self._bytes), "worker claim size changed")
        require(os.pread(self._fd, len(self._bytes) + 1, 0) == self._bytes, "worker claim bytes changed")
        after = os.fstat(self._fd)
        require(all(getattr(opened, k) == getattr(after, k) for k in
                    ("st_dev", "st_ino", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")), "worker claim changed while checking")
        return deepcopy(self._receipt)

    @property
    def sha256(self):
        self.assert_owned()
        return sha(self._bytes)

    def close(self):
        # A fork child must not unlock the parent's shared flock description.
        # Closing its inherited descriptor is safe; it cannot become the owner.
        fd, parent = self._fd, self._parent
        self._fd = self._parent = None
        try:
            if fd is not None:
                try:
                    if self._pid == os.getpid():
                        fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
        finally:
            if parent is not None:
                os.close(parent)

    def __exit__(self, *exc):
        self.close()
        return False
