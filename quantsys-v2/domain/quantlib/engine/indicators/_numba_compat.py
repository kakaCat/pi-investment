"""Numba compatibility shim for Python 3.14+.

Provides a no-op ``njit`` decorator when numba is not available or
incompatible with the current Python version.
"""
import sys
import types


def _install_numba_shim():
    """Install a no-op numba module if the real one isn't available."""
    if "numba" in sys.modules:
        return

    try:
        import numba  # noqa: F401
        return
    except ImportError:
        pass

    mock = types.ModuleType("numba")
    mock.njit = lambda *a, **kw: (lambda f: f)
    mock.jit = lambda *a, **kw: (lambda f: f)
    mock.vectorize = lambda *a, **kw: (lambda f: f)
    mock.guvectorize = lambda *a, **kw: (lambda f: f)
    sys.modules["numba"] = mock


_install_numba_shim()
