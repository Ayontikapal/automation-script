"""
lock_util.py - Thread-safe and process-safe mutex lock for MS Word COM operations.
Prevents concurrent access to Windows MS Word COM interface and manages hung winword processes.
"""

import os
import sys
import time
import subprocess
import threading
import logging
from pathlib import Path

logger = logging.getLogger("lock_util")

_THREAD_LOCK = threading.Lock()
DEFAULT_LOCK_FILE = Path(__file__).parent / "scratch" / "word_com.lock"
DEFAULT_TIMEOUT_SECONDS = 90


def kill_hung_word_instances() -> bool:
    """
    Forcefully terminates any hanging or orphaned Microsoft Word processes (winword.exe).
    Uses 'taskkill /f /im winword.exe' on Windows.
    """
    if sys.platform != "win32":
        return True

    try:
        cmd = ["taskkill", "/f", "/im", "winword.exe"]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if result.returncode == 0:
            logger.info("Successfully killed hung winword.exe instance(s).")
            return True
        elif "not found" in result.stderr.lower() or "not found" in result.stdout.lower():
            # No process was running
            return True
        else:
            logger.debug(f"taskkill output: {result.stdout.strip()} {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.warning(f"Failed to execute taskkill for winword.exe: {e}")
        return False


def is_process_running(pid: int) -> bool:
    """Checks if a given PID is currently active on the host."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            res = subprocess.run(
                ["tasklist", "/fi", f"PID eq {pid}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            return str(pid) in res.stdout
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


class WordLock:
    """
    A robust inter-process and inter-thread lock context manager.
    Coordinates Word COM conversions and protects against concurrency collisions.
    """

    def __init__(self, lock_path: Path = DEFAULT_LOCK_FILE, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.lock_path = Path(lock_path)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.acquired = False
        self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def acquire(self):
        # 1. Acquire in-process thread lock first
        _THREAD_LOCK.acquire()

        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                # Attempt atomic file creation with O_EXCL
                self._fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_RDWR
                )
                # Write current PID and timestamp into lock file
                lock_info = f"PID:{os.getpid()}\nTIMESTAMP:{time.time()}\n"
                os.write(self._fd, lock_info.encode("utf-8"))
                self.acquired = True
                logger.debug(f"Acquired Word COM lock at {self.lock_path}")
                return True
            except FileExistsError:
                # Lock file already exists. Inspect if it is stale.
                self._check_and_recover_stale_lock()
                time.sleep(0.5)

        _THREAD_LOCK.release()
        raise TimeoutError(
            f"Timed out after {self.timeout}s waiting to acquire Word COM lock at {self.lock_path}."
        )

    def _check_and_recover_stale_lock(self):
        """Checks if the existing lock file belongs to a dead process or timed out."""
        try:
            if not self.lock_path.exists():
                return

            mtime = self.lock_path.stat().st_mtime
            age = time.time() - mtime
            content = ""
            try:
                content = self.lock_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass

            pid = None
            for line in content.splitlines():
                if line.startswith("PID:"):
                    try:
                        pid = int(line.split(":")[1].strip())
                    except ValueError:
                        pass

            # If lock is older than timeout or PID is not running, break stale lock
            is_stale = False
            if age > self.timeout:
                logger.warning(f"Stale lock detected (age: {age:.1f}s > {self.timeout}s). Forcing recovery.")
                is_stale = True
            elif pid and not is_process_running(pid):
                logger.warning(f"Lock holder PID {pid} is no longer running. Forcing recovery.")
                is_stale = True

            if is_stale:
                kill_hung_word_instances()
                try:
                    self.lock_path.unlink(missing_ok=True)
                except Exception as ex:
                    logger.warning(f"Could not remove stale lock file: {ex}")
        except Exception as e:
            logger.debug(f"Error checking stale lock: {e}")

    def release(self):
        if self.acquired:
            try:
                if self._fd is not None:
                    os.close(self._fd)
                    self._fd = None
                if self.lock_path.exists():
                    self.lock_path.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Error releasing lock file {self.lock_path}: {e}")
            finally:
                self.acquired = False
                if _THREAD_LOCK.locked():
                    _THREAD_LOCK.release()
                logger.debug("Released Word COM lock.")
