"""
Shared subprocess lifecycle primitives.

Single authority for the low-level mechanics used by both the evaluator
timeout path (``eggcalc/evaluator.py``) and the MCP spawned-tool path
(``eggcalc/mcp/tools.py``):

- idempotent semaphore permit (RAII guard);
- non-raising acquire helper;
- queue close/join helper;
- terminate -> bounded join -> kill -> bounded join -> close helper;
- semaphore close helper for interpreter shutdown;
- multiprocessing context selection helper.

Policy stays with the callers: maximum spawn counts, acquire timeouts,
regex/evaluator timeouts, orphan caps, error envelopes, and exception
types are owned by ``evaluator.py`` and ``mcp/tools.py``. This module
returns cleanup status (survived or not) so each subsystem can preserve
its own orphan accounting.

Standard library only. Safe on Windows (no ``resource`` dependency, no
``fork`` requirement).
"""

from __future__ import annotations

import multiprocessing
from typing import Any

__all__ = [
    "SpawnPermit",
    "try_acquire_spawn_permit",
    "close_queue",
    "cleanup_child_process",
    "close_semaphore",
    "get_process_context",
]


class SpawnPermit:
    """RAII permit for an acquired spawn slot.

    The underlying semaphore count is released when the permit exits
    (including on exception or early return) or when ``release()`` is
    called explicitly. Release is idempotent: explicit release followed
    by context exit, destructor fallback, or double release never
    releases twice.
    """

    def __init__(self, sem: Any) -> None:
        self._sem = sem
        self._released = False

    def __enter__(self) -> SpawnPermit:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.release()

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            self._sem.release()
        except Exception:
            pass

    def __del__(self) -> None:  # pragma: no cover - interpreter shutdown path
        try:
            self.release()
        except Exception:
            pass


def try_acquire_spawn_permit(sem: Any, timeout: float) -> SpawnPermit | None:
    """Try to acquire a spawn slot, returning a permit or None on timeout.

    Returns None without consuming a slot when the acquire times out.
    On success the returned permit owns release via context exit,
    explicit ``release()``, or destructor fallback.
    """
    try:
        acquired = sem.acquire(timeout=timeout)
    except Exception:
        return None
    if not acquired:
        return None
    return SpawnPermit(sem)


def close_queue(queue: Any | None) -> None:
    """Close/join queue resources, ignoring cleanup errors."""
    if queue is None:
        return
    try:
        queue.close()
    except Exception:
        pass
    try:
        queue.join_thread()
    except Exception:
        pass


def cleanup_child_process(
    proc: Any | None,
    queue: Any | None = None,
    terminate_timeout: float = 2.0,
    kill_timeout: float = 1.0,
) -> bool:
    """Terminate and clean up a child process and its queue.

    Preserves the defensive sequence: close/join queue, terminate a live
    child, bounded join, kill if still alive and supported, bounded join,
    close the handle only when safe.

    Returns True when the process survived terminate+kill (the caller
    owns orphan registration); False otherwise (including proc None).
    """
    close_queue(queue)
    if proc is None:
        return False
    try:
        alive = proc.is_alive()
    except Exception:
        alive = False
    if alive:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.join(timeout=terminate_timeout)
        except Exception:
            pass
    try:
        alive = proc.is_alive()
    except Exception:
        alive = False
    if alive:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.join(timeout=kill_timeout)
        except Exception:
            pass
    try:
        alive = proc.is_alive()
    except Exception:
        alive = False
    if alive:
        return True
    try:
        proc.close()
    except Exception:
        pass
    return False


def close_semaphore(sem: Any | None) -> None:
    """Release the underlying semaphore on interpreter shutdown.

    Prevents 'leaked semaphore objects' warnings where the
    resource_tracker flags unclosed multiprocessing semaphores.
    Idempotent and safe to call on a healthy semaphore. Best-effort:
    on interpreters where the primitive exposes no ``close()``
    (e.g. CPython 3.14 ``_SemLock``) this is a documented no-op.
    """
    if sem is None:
        return
    for attr in ("_semaphore", "_semlock"):
        try:
            inner = getattr(sem, attr, None)
        except Exception:
            inner = None
        if inner is None:
            continue
        close = getattr(inner, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
            return
    close = getattr(sem, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass


def get_process_context(prefer: str = "spawn") -> Any:
    """Return a multiprocessing context, preferring ``prefer``.

    Falls back to the other start method when the preferred one is
    unavailable (e.g. ``fork`` on Windows raises ValueError and falls
    back to ``spawn``). Callers choose the preference to preserve their
    own policy: evaluator timeout workers always prefer ``spawn``;
    MCP tools prefer ``fork`` only for the single-file non-``__main__``
    case and ``spawn`` otherwise.
    """
    try:
        return multiprocessing.get_context(prefer)
    except ValueError:
        fallback = "fork" if prefer == "spawn" else "spawn"
        try:
            return multiprocessing.get_context(fallback)
        except ValueError:
            return multiprocessing.get_context()
