"""Verificação simples de recursos para a implementação didática de Shor."""
from __future__ import annotations
import os, platform, sys


def _available_memory_mb() -> int:
    try:
        pages = os.sysconf('SC_AVPHYS_PAGES')
        page_size = os.sysconf('SC_PAGE_SIZE')
        return max(256, int(pages * page_size / (1024**2)))
    except (AttributeError, ValueError, OSError):
        return 4096


def memory_budget_mb(requested=None) -> int:
    available = _available_memory_mb()
    default = min(2048, max(256, available // 4))
    if requested is None:
        return default
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 64:
        raise ValueError('max_memory_mb deve ser inteiro >= 64.')
    return min(requested, available)


def hardware_info() -> dict:
    return {
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'processor': platform.processor(),
        'cpu_count': os.cpu_count(),
        'available_memory_mb': _available_memory_mb(),
    }


def check_resources(N: int, mode: str, budget_mb: int) -> None:
    n = (N - 1).bit_length()
    # O simulador NumPy mantém 2**(3n) amplitudes complex128.
    state_mb = (16 * (1 << (3 * n))) / (1024**2)
    if mode == 'local' and state_mb > budget_mb:
        raise MemoryError(
            f'A simulação local exige aproximadamente {state_mb:.1f} MiB '
            f'e o orçamento é {budget_mb} MiB.'
        )
