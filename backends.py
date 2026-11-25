"""executores aer e fakeprovider usados pela demonstração de shor."""

from __future__ import annotations


def _fake_backend(num_qubits: int, backend_name: str | None = None):
    """retorna o snapshot fakeaachen e valida o nome solicitado."""
    from qiskit_ibm_runtime.fake_provider import FakeAachen

    accepted_names = {"fakeaachen", "fake_aachen", "ibm_aachen", "aachen"}
    if backend_name and backend_name.lower() not in accepted_names:
        raise ValueError(
            "Esta avaliação está configurada exclusivamente para FakeAachen."
        )

    backend = FakeAachen()
    if backend.num_qubits < num_qubits:
        raise ValueError(
            f"FakeAachen possui {backend.num_qubits} qubits; "
            f"o circuito requer {num_qubits}."
        )
    return backend


def prepare_for_backend(circuit, backend, seed: int | None = None):
    """transpila o circuito para o conjunto de portas e a topologia do backend."""
    from qiskit import transpile

    return transpile(
        circuit,
        backend=backend,
        optimization_level=1,
        seed_transpiler=seed,
    )


def run_aer(circuit, shots: int = 1024, seed: int | None = None, progress=None):
    """executa o circuito em aersimulator ideal, sem limitar memória do processo."""
    from qiskit import transpile
    from qiskit_aer import AerSimulator

    simulator = AerSimulator()
    compiled = transpile(
        circuit,
        simulator,
        optimization_level=1,
        seed_transpiler=seed,
    )
    if progress:
        progress(f"Aer: profundidade {compiled.depth()}, {compiled.size()} operações.")

    result = simulator.run(
        compiled,
        shots=shots,
        seed_simulator=seed,
    ).result()
    return result.get_counts(compiled)


def run_fake(
    circuit,
    shots: int = 1024,
    seed: int | None = None,
    backend_name: str = "FakeAachen",
    noise: bool = True,
    progress=None,
):
    """executa no aer usando topologia e, opcionalmente, ruído do fakeaachen."""
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel

    backend = _fake_backend(circuit.num_qubits, backend_name)
    compiled = prepare_for_backend(circuit, backend, seed)

    if noise:
        simulator = AerSimulator.from_backend(backend)
    else:
        simulator = AerSimulator.from_backend(
            backend,
            noise_model=NoiseModel(),
        )

    if progress:
        progress(
            f"FakeAachen: profundidade {compiled.depth()}, "
            f"{compiled.size()} operações; ruído={noise}."
        )

    result = simulator.run(
        compiled,
        shots=shots,
        seed_simulator=seed,
    ).result()
    return result.get_counts(compiled)


def _silence_ibm_warnings() -> None:
    """reduz avisos informativos do runtime sem esconder exceções."""
    import logging

    names = (
        "qiskit_ibm_runtime",
        "qiskit_ibm_runtime.qiskit_runtime_service",
        "qiskit_runtime_service",
        "qiskit_runtime_service._discover_account",
        "qiskit_runtime_service.__init__",
        "qiskit_runtime_service.backends",
    )
    for name in names:
        logging.getLogger(name).setLevel(logging.ERROR)

    for name in tuple(logging.root.manager.loggerDict):
        if "qiskit_runtime_service" in name or name.startswith("qiskit_ibm_runtime"):
            logging.getLogger(name).setLevel(logging.ERROR)


def get_ibm_backend(
    num_qubits: int,
    backend_name: str | None = None,
    instance: str | None = None,
):
    """conecta ao runtime e seleciona um backend com capacidade suficiente."""
    import os
    from pathlib import Path

    from dotenv import load_dotenv
    from qiskit_ibm_runtime import QiskitRuntimeService

    _silence_ibm_warnings()
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    token = os.getenv("IBM_QUANTUM_TOKEN")
    if not token:
        raise ValueError("Defina IBM_QUANTUM_TOKEN no ambiente ou no .env da pasta.")

    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=token,
        instance=instance or os.getenv("IBM_QUANTUM_INSTANCE") or "auto",
    )
    backend = (
        service.backend(backend_name)
        if backend_name
        else service.least_busy(
            operational=True,
            simulator=False,
            min_num_qubits=num_qubits,
        )
    )
    if backend.num_qubits < num_qubits:
        raise ValueError(
            f"O backend possui {backend.num_qubits} qubits; "
            f"o circuito requer {num_qubits}."
        )
    return backend


def run_ibm(circuit, shots: int, backend, seed: int | None = None, progress=None):
    """transpila e executa o circuito no sampler do runtime IBM."""
    from qiskit import transpile
    from qiskit_ibm_runtime import SamplerV2

    compiled = transpile(
        circuit,
        backend=backend,
        optimization_level=1,
        seed_transpiler=seed,
    )
    if progress:
        progress(
            f"Circuito transpilado: profundidade {compiled.depth()}, "
            f"{compiled.size()} operações."
        )

    job = SamplerV2(mode=backend).run([compiled], shots=shots)
    if progress:
        progress(f"Job IBM: {job.job_id()}")
    return job.result()[0].data.c.get_counts()
