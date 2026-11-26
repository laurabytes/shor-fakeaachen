"""Execução local de circuitos Qiskit no Aer e em snapshots IBM.

Os snapshots do FakeProvider são arquivos distribuídos com o Runtime: não
exigem conta, rede ou jobs IBM. ``max_memory_mb`` limita a memória do estado
quântico no Aer, não a memória total do processo ou da transpilação.
"""

from __future__ import annotations

from operator import index


def _positive_integer(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} deve ser um inteiro positivo.")
    try:
        value = index(value)
    except TypeError as exc:
        raise ValueError(f"{name} deve ser um inteiro positivo.") from exc
    if value < 1:
        raise ValueError(f"{name} deve ser um inteiro positivo.")
    return value


def _validate_options(shots, seed, max_memory_mb):
    shots = _positive_integer(shots, "shots")
    max_memory_mb = _positive_integer(max_memory_mb, "max_memory_mb")
    if seed is not None:
        if isinstance(seed, bool):
            raise ValueError("seed deve ser um inteiro não negativo.")
        try:
            seed = index(seed)
        except TypeError as exc:
            raise ValueError("seed deve ser um inteiro não negativo.") from exc
        if seed < 0:
            raise ValueError("seed deve ser um inteiro não negativo.")
    return shots, seed, max_memory_mb


def _active_qubit_count(circuit):
    # Transpilar para um snapshot de 127 qubits aloca ancillas ociosas.
    # Aer remove essas ancillas com enable_truncation sem perder o mapeamento
    # dos erros físicos. Não remapeamos manualmente os índices do circuito.
    return len({
        qubit
        for instruction in circuit.data
        if instruction.operation.name != "barrier"
        for qubit in instruction.qubits
    })


def _check_memory(circuit, max_memory_mb):
    active = _active_qubit_count(circuit)
    required_bytes = 16 * (1 << active)
    if required_bytes > max_memory_mb * (1 << 20):
        required_mb = (required_bytes + (1 << 20) - 1) // (1 << 20)
        raise ValueError(
            f"O estado de {active} qubits ativos exige pelo menos {required_mb} MiB; "
            f"o limite de memória do Aer é {max_memory_mb} MiB. "
            "Reduza N ou aumente --max-memory-mb."
        )
    return active


def prepare_for_backend(circuit, backend, seed=None):
    """Transpila o circuito para as portas e conexões do backend fornecido."""
    from qiskit import transpile

    if circuit.num_qubits > backend.num_qubits:
        raise ValueError(
            f"O backend {backend.name} tem {backend.num_qubits} qubits; "
            f"o circuito exige {circuit.num_qubits}."
        )
    return transpile(circuit, backend, optimization_level=1, seed_transpiler=seed)


def _simulator_options(max_memory_mb):
    return dict(
        method="statevector",
        device="CPU",
        enable_truncation=True,
        max_memory_mb=max_memory_mb,
        # Ruído é amostrado por trajetória. Evitar matrizes densidade e vários
        # estados simultâneos mantém o uso de memória limitado por tentativa.
        max_parallel_shots=1,
        max_parallel_experiments=1,
        max_parallel_threads=2,
    )


def _execute(simulator, compiled, *, shots, seed, max_memory_mb, progress):
    active = _check_memory(compiled, max_memory_mb)
    if progress:
        progress(
            f"Circuito transpilado: {active} qubits ativos, "
            f"profundidade {compiled.depth()}, {compiled.size()} operações."
        )
    result = simulator.run(compiled, shots=shots, seed_simulator=seed).result()
    if not result.success:
        raise RuntimeError(f"Falha na simulação Aer: {result.status}")
    return dict(result.get_counts(0))


def run_aer(circuit, *, shots, seed=None, max_memory_mb=1024, progress=None):
    """Executa o circuito real no AerSimulator ideal, em CPU."""
    shots, seed, max_memory_mb = _validate_options(shots, seed, max_memory_mb)
    _check_memory(circuit, max_memory_mb)
    from qiskit_aer import AerSimulator

    simulator = AerSimulator(**_simulator_options(max_memory_mb))
    if progress:
        progress("Backend local: AerSimulator, CPU, statevector ideal.")
    compiled = prepare_for_backend(circuit, simulator, seed)
    return _execute(
        simulator, compiled, shots=shots, seed=seed,
        max_memory_mb=max_memory_mb, progress=progress,
    )


def _fake_backend(num_qubits, backend_name=None):
    from qiskit_ibm_runtime import fake_provider

    if backend_name:
        # Aceita nomes exibidos pelo backend (fake_sherbrooke) e nomes das
        # classes documentadas (FakeSherbrooke, FakeMelbourneV2).
        candidates = [
            backend_class
            for class_name, backend_class in vars(fake_provider).items()
            if isinstance(backend_class, type)
            and (
                class_name == backend_name
                or getattr(backend_class, "backend_name", None) == backend_name
            )
        ]
        if not candidates:
            raise ValueError(
                f"Backend fake desconhecido: {backend_name}. "
                "Use, por exemplo, fake_melbourne ou FakeSherbrooke."
            )
        backend = candidates[0]()
    else:
        # Um snapshot pequeno reduz ancillas de roteamento e custo por shot.
        for class_name in (
            "FakeMelbourneV2", "FakeGuadalupeV2", "FakeAlmadenV2",
            "FakeAlgiers", "FakeCambridgeV2", "FakeBrooklynV2",
            "FakeSherbrooke", "FakeTorino", "FakeFez",
        ):
            backend_class = getattr(fake_provider, class_name, None)
            if backend_class is not None:
                candidate = backend_class()
                if candidate.num_qubits >= num_qubits:
                    backend = candidate
                    break
        else:
            raise ValueError(f"Nenhum snapshot fake disponível com {num_qubits} qubits.")
    if backend.num_qubits < num_qubits:
        raise ValueError(
            f"O backend {backend.name} tem {backend.num_qubits} qubits; "
            f"o circuito exige {num_qubits}."
        )
    return backend


def run_fake(
    circuit, *, shots, seed=None, backend_name=None, noise=True,
    max_memory_mb=1024, progress=None,
):
    """Executa localmente portas, conexões e, por padrão, ruído de snapshot IBM.

    ``noise=False`` conserva a transpilação para o dispositivo, mas remove
    os erros para permitir comparações ideais e testes determinísticos.
    """
    shots, seed, max_memory_mb = _validate_options(shots, seed, max_memory_mb)
    if not isinstance(noise, bool):
        raise ValueError("noise deve ser um booleano.")
    _check_memory(circuit, max_memory_mb)
    from qiskit_aer import AerSimulator

    backend = _fake_backend(circuit.num_qubits, backend_name)
    options = _simulator_options(max_memory_mb)
    if not noise:
        # None remove o ruído conservando todas as portas do snapshot.
        # Um NoiseModel vazio pode restringir indevidamente as basis_gates.
        options["noise_model"] = None
    simulator = AerSimulator.from_backend(backend, **options)
    if progress:
        mode = "com ruído do snapshot" if noise else "ideal, sem ruído"
        progress(f"Backend fake local: {backend.name}, CPU, {mode}.")
    compiled = prepare_for_backend(circuit, backend, seed)
    return _execute(
        simulator, compiled, shots=shots, seed=seed,
        max_memory_mb=max_memory_mb, progress=progress,
    )