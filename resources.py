"""estimativa de memória para a simulação local com NumPy."""

from __future__ import annotations

import os


def _available_memory_mb() -> int:
    try:
        pages = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return max(256, int(pages * page_size / (1024**2)))
    except (AttributeError, ValueError, OSError):
        return 4096


def memory_budget_mb(requested: int | None = None) -> int:
    available = _available_memory_mb()
    default = min(2048, max(256, available // 4))
    if requested is None:
        return default
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 64:
        raise ValueError("max_memory_mb deve ser um inteiro maior ou igual a 64.")
    return min(requested, available)


def check_resources(N: int, mode: str, budget_mb: int | None) -> None:
    if mode != "local":
        return
    qubits = (N - 1).bit_length()
    required = 16 * (1 << (3 * qubits)) / (1024**2)
    if required > budget_mb:
        raise MemoryError(
            f"A simulação local exige aproximadamente {required:.1f} MiB; "
            f"o orçamento é {budget_mb} MiB."
        )
