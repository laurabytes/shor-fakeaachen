"""Orçamento de memória local, consultável antes de construir/simular circuitos."""

from __future__ import annotations

import os
import platform


def hardware_info() -> dict:
    """Consulta recursos sem rede; funciona também sem psutil instalado."""
    info = {
        "system": platform.system(), "architecture": platform.machine(),
        "cpu_count": os.cpu_count() or 1,
        "total_memory_mb": None, "available_memory_mb": None,
    }
    try:
        import psutil
        memory = psutil.virtual_memory()
        info.update(total_memory_mb=memory.total // 2**20,
                    available_memory_mb=memory.available // 2**20)
    except (ImportError, OSError, RuntimeError):
        pass
    return info


def memory_budget_mb(requested: int | None = None) -> int:
    """Padrão: até 2 GiB e um quarto da RAM disponível; fallback de 512 MiB."""
    if requested is not None:
        if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
            raise ValueError("max_memory_mb deve ser um inteiro positivo.")
        return requested
    available = hardware_info()["available_memory_mb"]
    return min(2048, max(1, available // 4)) if available else 512


def estimate_resources(N: int, mode: str = "aer") -> dict:
    """Estimativa conservadora de estado + temporários, sem alocar amplitudes.

    Para fake, o roteamento pode ativar qubits adicionais: o runner verifica
    novamente a estimativa depois da transpilação. IBM não simula estado local.
    """
    n = (N - 1).bit_length()
    state_bytes = 16 * (1 << (3 * n))
    # NumPy usa estado, FFT, cópias de permutação e probabilidades temporárias.
    copies = 4 if mode == "local" else 2
    peak_bytes = copies * state_bytes
    return {
        "target_qubits": n, "counting_qubits": 2 * n, "total_qubits": 3 * n,
        "state_mb": state_bytes / 2**20,
        "estimated_peak_mb": (peak_bytes + 2**20 - 1) // 2**20,
    }


def check_resources(N: int, mode: str, max_memory_mb: int) -> dict:
    resources = estimate_resources(N, mode)
    if mode != "ibm" and resources["estimated_peak_mb"] > max_memory_mb:
        raise ValueError(
            f"A simulação de N={N} precisa de aproximadamente "
            f"{resources['estimated_peak_mb']} MiB para estado e temporários "
            f"({resources['total_qubits']} qubits), acima do orçamento de "
            f"{max_memory_mb} MiB. Use N menor ou --max-memory-mb com um "
            "valor compatível com a RAM disponível."
        )
    return resources