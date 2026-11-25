"""execução dos circuitos nos simuladores aer e fakeaachen."""

from __future__ import annotations


def fake_backend(num_qubits: int, backend_name: str | None = None):
    """carrega o snapshot fakeaachen e confere a capacidade."""
    from qiskit_ibm_runtime.fake_provider import FakeAachen

    accepted = {"fakeaachen", "fake_aachen", "ibm_aachen", "aachen"}
    if backend_name and backend_name.lower() not in accepted:
        raise ValueError("O projeto utiliza exclusivamente o backend FakeAachen.")
    backend = FakeAachen()
    if backend.num_qubits < num_qubits:
        raise ValueError(
            f"FakeAachen possui {backend.num_qubits} qubits; "
            f"o circuito requer {num_qubits}."
        )
    return backend


def prepare_for_backend(circuit, backend, seed: int | None = None):
    """transpila o circuito para as portas e a conectividade do backend."""
    from qiskit import transpile

    return transpile(
        circuit, backend=backend, optimization_level=1, seed_transpiler=seed
    )


def run_aer(circuit, shots: int = 1024, seed: int | None = None, progress=None):
    """executa o circuito no aersimulator ideal."""
    from qiskit import transpile
    from qiskit_aer import AerSimulator

    simulator = AerSimulator()
    compiled = transpile(circuit, simulator, optimization_level=1, seed_transpiler=seed)
    if progress:
        progress(f"Aer: profundidade {compiled.depth()}, {compiled.size()} operações.")
    result = simulator.run(compiled, shots=shots, seed_simulator=seed).result()
    return result.get_counts(compiled)


def run_fake(
    circuit,
    shots: int = 1024,
    seed: int | None = None,
    backend_name: str | None = None,
    noise: bool = True,
    progress=None,
):
    """executa no aer com topologia fakeaachen e ruído opcional."""
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel

    backend = fake_backend(circuit.num_qubits, backend_name)
    compiled = prepare_for_backend(circuit, backend, seed)
    simulator = (
        AerSimulator.from_backend(backend)
        if noise
        else AerSimulator.from_backend(backend, noise_model=NoiseModel())
    )
    if progress:
        progress(
            f"FakeAachen: profundidade {compiled.depth()}, "
            f"{compiled.size()} operações; ruído={noise}."
        )
    result = simulator.run(
        compiled, shots=shots, seed_simulator=seed
    ).result()
    return result.get_counts(compiled)
