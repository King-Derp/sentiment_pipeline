"""Project-level pytest configuration and shared fixtures."""

# Try to rely on the real ``pytest-mock`` plugin first. If it is not installed we provide a
# **minimal** fallback implementation that fulfils the limited needs of our test-suite (mostly
# ``mocker.patch`` for attribute patching and monkeypatch delegation). This avoids adding a hard
# third-party dependency while still unblocking tests.

from types import SimpleNamespace
from unittest import mock
import importlib

try:
    import pytest_mock  # noqa: F401 – we only need to know import succeeds
except ImportError:  # pragma: no cover – fallback only used in minimal envs

    import pytest

    class _FallbackMocker:
        """Lightweight substitute for the `pytest-mock` MockerFixture."""

        def __init__(self, _monkeypatch: "pytest.MonkeyPatch") -> None:
            self._monkeypatch = _monkeypatch

        # Basic attribute/target patching similar to pytest-mock's API.
        def patch(self, target: str, *args, **kwargs):
            """Light subset of ``pytest_mock.MockerFixture.patch``.

            This resolves *target* by importing the first module part and then traversing
            attributes until the final attribute, which is replaced with *new_value* (or a
            fresh ``MagicMock`` if none provided).
            """

            new_value = args[0] if args else mock.MagicMock()

            parts = target.split(".")
            # Import the longest valid module path prefix.
            for i in range(len(parts), 0, -1):
                module_path = ".".join(parts[:i])
                try:
                    obj = importlib.import_module(module_path)
                    attr_chain = parts[i:]
                    break
                except ModuleNotFoundError:
                    continue
            else:  # pragma: no cover
                raise ModuleNotFoundError(f"Cannot import any part of target '{target}'")

            # Traverse remaining attribute chain to reach parent object.
            for attr in attr_chain[:-1]:
                obj = getattr(obj, attr)

            attr_name = attr_chain[-1] if attr_chain else parts[-1]
            self._monkeypatch.setattr(obj, attr_name, new_value, raising=True)
            return new_value

        # Expose `setattr` to mirror real fixture
        def setattr(self, *args, **kwargs):  # noqa: D401
            return self._monkeypatch.setattr(*args, **kwargs)

        # Helpers for introspection in tests (call_count etc.)
        def __getattr__(self, item):  # pragma: no cover – passthrough to unittest.mock
            return getattr(mock, item)

    @pytest.fixture
    def mocker(monkeypatch):  # noqa: D401 – fixture name intentional
        """Project-scoped *mocker* fixture fallback if *pytest-mock* is absent."""

        return _FallbackMocker(monkeypatch)
