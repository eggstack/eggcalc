"""Shared lifecycle and registry maintainability (Plan 035).

Covers the extracted ``eggcalc._process`` primitives, the exact lazy
export authority, and the lazy-exact build manifest invariant. Uses fakes
for process/queue behavior so tests stay deterministic (no long sleeps,
no leaked children or semaphores).
"""

from __future__ import annotations

import multiprocessing
import subprocess
import sys
import textwrap

import pytest

from eggcalc._process import (
    SpawnPermit,
    cleanup_child_process,
    close_queue,
    get_process_context,
    try_acquire_spawn_permit,
)


def _sem_available(sem) -> bool:
    """Portable semaphore-availability probe.

    ``multiprocessing.Semaphore.get_value()`` raises ``NotImplementedError``
    on macOS, so tests infer availability from a non-blocking acquire
    instead (balanced by an immediate release).
    """
    if sem.acquire(block=False):
        sem.release()
        return True
    return False


class _FakeQueue:
    def __init__(self, fail_close=False, fail_join=False):
        self.closed = False
        self.joined = False
        self._fail_close = fail_close
        self._fail_join = fail_join

    def close(self):
        self.closed = True
        if self._fail_close:
            raise OSError("close failed")

    def join_thread(self):
        self.joined = True
        if self._fail_join:
            raise OSError("join failed")


class _FakeProc:
    """Fake child process with a scripted is_alive sequence."""

    def __init__(self, alive_script):
        self._alive = list(alive_script)
        self.terminated = 0
        self.killed = 0
        self.joins = []
        self.closed = 0

    def is_alive(self):
        if self._alive:
            return self._alive.pop(0)
        return False

    def terminate(self):
        self.terminated += 1

    def kill(self):
        self.killed += 1

    def join(self, timeout=None):
        self.joins.append(timeout)

    def close(self):
        self.closed += 1


class TestSpawnPermit:
    def test_acquire_release_count(self):
        sem = multiprocessing.BoundedSemaphore(1)
        assert _sem_available(sem)
        permit = try_acquire_spawn_permit(sem, timeout=5)
        assert permit is not None
        assert not _sem_available(sem)
        with permit:
            assert not _sem_available(sem)
        assert _sem_available(sem)

    def test_acquire_timeout_consumes_no_permit(self):
        sem = multiprocessing.BoundedSemaphore(1)
        assert sem.acquire(block=False)
        assert not _sem_available(sem)
        assert try_acquire_spawn_permit(sem, timeout=0.05) is None
        assert not _sem_available(sem)
        sem.release()
        assert _sem_available(sem)

    def test_release_on_exception(self):
        sem = multiprocessing.BoundedSemaphore(1)
        permit = try_acquire_spawn_permit(sem, timeout=5)
        assert permit is not None
        with pytest.raises(RuntimeError, match="boom"):
            with permit:
                raise RuntimeError("boom")
        assert _sem_available(sem)

    def test_idempotent_release(self):
        sem = multiprocessing.BoundedSemaphore(1)
        permit = try_acquire_spawn_permit(sem, timeout=5)
        assert permit is not None
        permit.release()
        assert _sem_available(sem)
        with permit:  # context exit after explicit release must not double-release
            pass
        assert _sem_available(sem)
        permit.release()
        assert _sem_available(sem)

    def test_evaluator_and_mcp_share_permit_type(self):
        from eggcalc.evaluator import _EvalSpawnPermit
        from eggcalc.mcp.tools import _SpawnPermit

        assert _EvalSpawnPermit is SpawnPermit
        assert _SpawnPermit is SpawnPermit


class TestCloseQueue:
    def test_none_is_ok(self):
        close_queue(None)

    def test_close_and_join(self):
        queue = _FakeQueue()
        close_queue(queue)
        assert queue.closed and queue.joined

    def test_errors_ignored(self):
        close_queue(_FakeQueue(fail_close=True, fail_join=True))


class TestCleanupChildProcess:
    def test_none_proc(self):
        assert cleanup_child_process(None, _FakeQueue()) is False

    def test_clean_exit_closes_handle(self):
        proc = _FakeProc([False])
        queue = _FakeQueue()
        assert cleanup_child_process(proc, queue) is False
        assert queue.closed and queue.joined
        assert proc.terminated == 0 and proc.killed == 0
        assert proc.closed == 1

    def test_terminated_child(self):
        # alive -> terminate -> dead (no kill needed)
        proc = _FakeProc([True, False, False])
        assert cleanup_child_process(proc, None) is False
        assert proc.terminated == 1
        assert proc.killed == 0
        assert proc.closed == 1

    def test_killed_child_where_supported(self):
        # alive -> terminate -> still alive -> kill -> dead
        proc = _FakeProc([True, True, False])
        assert cleanup_child_process(proc, None) is False
        assert proc.terminated == 1
        assert proc.killed == 1
        assert proc.closed == 1

    def test_survivor_reported(self):
        proc = _FakeProc([True, True, True])
        assert cleanup_child_process(proc, None) is True
        assert proc.closed == 0  # handle left open for orphan tracking

    def test_queue_errors_do_not_break_cleanup(self):
        proc = _FakeProc([False])
        queue = _FakeQueue(fail_close=True, fail_join=True)
        assert cleanup_child_process(proc, queue) is False
        assert proc.closed == 1

    def test_mcp_wrapper_registers_survivor(self):
        from eggcalc.mcp import tools

        survivor = _FakeProc([True, True, True])
        with tools._orphaned_regex_lock:
            tools._orphaned_regex_processes.clear()
            tools._orphaned_regex_order.clear()
        try:
            tools._cleanup_child_process(survivor, None)
            with tools._orphaned_regex_lock:
                assert survivor in tools._orphaned_regex_processes
        finally:
            with tools._orphaned_regex_lock:
                tools._orphaned_regex_processes.clear()
                tools._orphaned_regex_order.clear()

    def test_eval_timeout_registers_survivor(self):
        import eggcalc.evaluator as ev

        class FakeQueue:
            def get(self, timeout=None):
                from queue import Empty

                raise Empty()

            def close(self):
                pass

            def join_thread(self):
                pass

        class FakeProcess:
            pid = 12345
            exitcode = None

            def __init__(self, **kwargs):
                pass

            def start(self):
                pass

            def is_alive(self):
                return True

            def terminate(self):
                pass

            def kill(self):
                pass

            def join(self, timeout):
                pass

            def close(self):
                pass

        class FakeContext:
            def Queue(self):
                return FakeQueue()

            def Process(self, **kwargs):
                return FakeProcess()

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(ev, "_get_eval_multiprocessing_context", lambda: FakeContext())
        with ev._orphaned_eval_lock:
            ev._orphaned_eval_processes.clear()
            ev._orphaned_eval_order.clear()
        try:
            with pytest.raises(ev.TimeoutError):
                ev.evaluate_with_timeout("1+1", timeout=0.01)
            with ev._orphaned_eval_lock:
                assert len(ev._orphaned_eval_processes) == 1
        finally:
            with ev._orphaned_eval_lock:
                ev._orphaned_eval_processes.clear()
                ev._orphaned_eval_order.clear()
            monkeypatch.undo()


class TestProcessContext:
    def test_default_is_spawn(self):
        ctx = get_process_context()
        assert ctx._name == "spawn"

    def test_prefer_fork_falls_back_on_windows(self, monkeypatch):
        real_get_context = multiprocessing.get_context

        def fake_get_context(name=None):
            if name == "fork":
                raise ValueError("fork unavailable")
            return real_get_context(name)

        monkeypatch.setattr(multiprocessing, "get_context", fake_get_context)
        ctx = get_process_context("fork")
        assert ctx._name == "spawn"

    def test_evaluator_prefers_spawn(self, monkeypatch):
        import eggcalc.evaluator as ev

        seen = {}
        real = get_process_context

        def fake(prefer="spawn"):
            seen["prefer"] = prefer
            return real(prefer)

        monkeypatch.setattr(ev, "get_process_context", fake)
        ev._get_eval_multiprocessing_context()
        assert seen["prefer"] == "spawn"

    def test_package_timeout_path_executes(self):
        from eggcalc.evaluator import evaluate_with_timeout

        assert evaluate_with_timeout("2+2", timeout=10) == 4


class TestExactExportAuthority:
    def test_all_derived_from_lazy_imports(self):
        import eggcalc.exact as exact

        assert exact.__all__ == list(exact._LAZY_IMPORTS)

    def test_no_duplicate_names(self):
        import eggcalc.exact as exact

        assert len(exact.__all__) == len(set(exact.__all__))

    def test_all_exported_names_resolve(self):
        import eggcalc.exact as exact

        for name in exact.__all__:
            assert getattr(exact, name) is not None, name

    def test_parity_additions_present(self):
        import eggcalc.exact as exact

        for name in (
            "ip_inspect",
            "cidr_inspect",
            "codec_convert",
            "radix_convert",
            "datetime_convert",
            "cron_inspect",
        ):
            assert name in exact.__all__, name

    def test_unknown_names_raise(self):
        import eggcalc.exact as exact

        with pytest.raises(AttributeError):
            exact.__getattr__("this_name_does_not_exist_xyz")

    def test_import_exact_loads_no_implementations(self):
        code = textwrap.dedent("""\
            import sys
            import eggcalc.exact
            impls = [m for m in sys.modules
                     if m.startswith("eggcalc.exact.") and m != "eggcalc.exact"]
            assert not impls, impls
        """)
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestLazyManifestCoverage:
    def test_every_lazy_module_in_manifest(self):
        import build_single

        lazy = build_single._lazy_exact_modules()
        assert lazy, "no lazy exact modules parsed"
        names = {spec.name for spec in build_single.MODULE_MANIFEST}
        missing = sorted(mod for mod in lazy if mod not in names)
        assert not missing, f"lazy exact modules absent from manifest: {missing}"

    def test_validator_catches_lazy_omission(self, tmp_path, monkeypatch):
        import build_single

        (tmp_path / "cli.py").write_text("COMMANDS = []\n", encoding="utf-8")
        (tmp_path / "exact").mkdir()
        (tmp_path / "exact" / "__init__.py").write_text(
            '_LAZY_IMPORTS: dict = {"thing": (".missing_mod", "thing")}\n',
            encoding="utf-8",
        )
        (tmp_path / "consumer.py").write_text("value = 1\n", encoding="utf-8")
        monkeypatch.setattr(build_single, "EGGCALC_DIR", str(tmp_path))
        monkeypatch.setattr(build_single, "_literal_cli_targets", lambda: set())

        def fake_spec(name, *depends_on):
            return build_single.ModuleSpec(name, f"{name.replace('.', '/')}.py", "core", depends_on)

        errors = build_single.validate_build_manifest((fake_spec("consumer"),))
        assert any("absent from manifest" in error for error in errors)

    def test_close_semaphore_wrappers_idempotent(self):
        from eggcalc.mcp.tools import _close_spawn_semaphore

        _close_spawn_semaphore()  # must not raise on a healthy semaphore
