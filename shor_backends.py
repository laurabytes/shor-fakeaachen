"""Adaptadores para os executores usados pelo código-fonte de referência."""

import backends


def run_aer(circuit, shots=1024, seed=None, max_memory_mb=None, progress=None):
    return backends.run_aer(circuit, shots=shots, seed=seed, progress=progress)


def run_fake(
    circuit,
    shots=1024,
    seed=None,
    backend_name=None,
    noise=True,
    max_memory_mb=None,
    progress=None,
):
    return backends.run_fake(
        circuit,
        shots=shots,
        seed=seed,
        backend_name=backend_name,
        noise=noise,
        progress=progress,
    )
