"""estimativa simples de memória para a simulação numpy local."""
from __future__ import annotations

import os
import platform
import sys


def _available_memory_mb() -> int:
    """retorna uma estimativa da memória disponível no sistema."""
    try:
        page_count = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        available = page_count * page_size / (1024**2)
        return max(256, int(available))
    except (AttributeError, ValueError, OSError):
        return 4096


def memory_budget_mb(requested: int | None = None) -> int:
    """define o orçamento de memória para a simulação numpy local."""
    available = _available_memory_mb()
    default = min(2048, max(256, available // 4))

    if requested is None:
        return default
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 64:
        raise ValueError("max_memory_mb deve ser um inteiro maior ou igual a 64.")
    return min(requested, available)


def hardware_info() -> dict[str, object]:
    """resume informações do ambiente de execução."""
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "available_memory_mb": _available_memory_mb(),
    }


def check_resources(N: int, mode: str, budget_mb: int | None) -> None:
    """verifica o orçamento estimado antes de alocar o estado numpy."""
    if mode != "local":
        return

    num_target_qubits = (N - 1).bit_length()
    state_size_mb = 16 * (1 << (3 * num_target_qubits)) / (1024**2)
    if state_size_mb > budget_mb:
        raise MemoryError(
            f"A simulação NumPy local exige aproximadamente {state_size_mb:.1f} MiB; "
            f"o orçamento configurado é {budget_mb} MiB."
        )
