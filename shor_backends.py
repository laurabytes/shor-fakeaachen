"""Executores Aer/FakeProvider. O backend de referência da entrega é FakeAachen."""
from __future__ import annotations


def _fake_backend(num_qubits: int, backend_name: str | None = None):
    from qiskit_ibm_runtime.fake_provider import FakeAachen
    accepted = {'fakeaachen', 'fake_aachen', 'ibm_aachen', 'aachen'}
    if backend_name and backend_name.lower() not in accepted:
        raise ValueError('Esta avaliação está configurada exclusivamente para FakeAachen.')
    backend = FakeAachen()
    if backend.num_qubits < num_qubits:
        raise ValueError(f'FakeAachen possui {backend.num_qubits} qubits; circuito requer {num_qubits}.')
    return backend


def prepare_for_backend(circuit, backend, seed=None):
    from qiskit import transpile
    return transpile(circuit, backend=backend, optimization_level=1, seed_transpiler=seed)


def run_aer(circuit, shots=1024, seed=None, max_memory_mb=None, progress=None):
    from qiskit import transpile
    from qiskit_aer import AerSimulator
    simulator = AerSimulator()
    compiled = transpile(circuit, simulator, optimization_level=1, seed_transpiler=seed)
    if progress:
        progress(f'Aer: profundidade {compiled.depth()}, {compiled.size()} operações.')
    result = simulator.run(compiled, shots=shots, seed_simulator=seed).result()
    return result.get_counts(compiled)


def run_fake(circuit, shots=1024, seed=None, backend_name='FakeAachen', noise=True,
             max_memory_mb=None, progress=None):
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel
    backend = _fake_backend(circuit.num_qubits, backend_name)
    compiled = prepare_for_backend(circuit, backend, seed)
    if noise:
        simulator = AerSimulator.from_backend(backend)
    else:
        simulator = AerSimulator.from_backend(backend, noise_model=NoiseModel())
    if progress:
        progress(f'FakeAachen: profundidade {compiled.depth()}, {compiled.size()} operações; '
                 f'ruído={noise}.')
    result = simulator.run(compiled, shots=shots, seed_simulator=seed).result()
    return result.get_counts(compiled)
