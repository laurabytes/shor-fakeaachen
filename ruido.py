"""modelo de ruído aproximado derivado do snapshot fakeaachen."""

from __future__ import annotations

import math


def remap_backend_noise(backend, physical_to_compact):
    """constrói um modelo de ruído simplificado a partir do snapshot fakeaachen.

    a implementação evita noisemodel.from_backend(), que nesta combinação de
    backend/versão inclui custom noise passes que não podem ser reindexados
    automaticamente após a compactação. em vez disso, usa:
      * erro médio de cada porta nativa (depolarizing_error por instrução/qargs);
      * erro médio de leitura de cada qubit (readouterror simétrico).

    é um modelo aproximado derivado das propriedades do fakeaachen. não inclui
    relaxação t1/t2, crosstalk, drift, leakage nem os custom noise passes originais.
    isso é explicitado no json e no relatório.
    """
    from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

    props = backend.properties()
    if props is None:
        raise RuntimeError(
            "FakeAachen não disponibilizou BackendProperties para construir o modelo de ruído."
        )

    basis = ["id", "rz", "sx", "x", "cz"]
    target = NoiseModel(basis_gates=basis)
    gate_error_table = {}

    # lê os erros calibrados por operação e conjunto de qubits físicos.
    for gate_record in getattr(props, "gates", []):
        instruction = str(getattr(gate_record, "gate", ""))
        physical_tuple = tuple(int(q) for q in getattr(gate_record, "qubits", []))
        if instruction not in basis or not physical_tuple:
            continue
        if not all(q in physical_to_compact for q in physical_tuple):
            continue
        try:
            probability = props.gate_error(instruction, list(physical_tuple))
        except Exception:
            probability = None
        if probability is None:
            # fallback para a lista de parâmetros do registro de calibração.
            for parameter in getattr(gate_record, "parameters", []):
                if getattr(parameter, "name", None) == "gate_error":
                    probability = getattr(parameter, "value", None)
                    break
        if probability is None:
            continue
        probability = float(probability)
        if not math.isfinite(probability):
            continue
        probability = min(max(probability, 0.0), 1.0)
        key = (instruction, physical_tuple)
        gate_error_table[key] = probability

    copied_gate_errors = 0
    for (instruction, physical_tuple), probability in gate_error_table.items():
        if probability <= 0:
            continue
        compact_tuple = [physical_to_compact[q] for q in physical_tuple]
        error = depolarizing_error(probability, len(compact_tuple))
        target.add_quantum_error(error, [instruction], compact_tuple, warnings=False)
        copied_gate_errors += 1

        # cz é simétrica. se o snapshot só listar uma orientação da aresta,
        # aplica a mesma taxa também à orientação inversa no circuito compacto.
        if instruction == "cz" and len(physical_tuple) == 2:
            reverse_key = (instruction, tuple(reversed(physical_tuple)))
            if reverse_key not in gate_error_table:
                reverse_compact = [
                    physical_to_compact[physical_tuple[1]],
                    physical_to_compact[physical_tuple[0]],
                ]
                target.add_quantum_error(
                    error, [instruction], reverse_compact, warnings=False
                )
                copied_gate_errors += 1

    # modelo simétrico de leitura por qubit, parametrizado pelo erro médio do snapshot.
    copied_readout_errors = 0
    readout_table = {}
    for physical in physical_to_compact:
        try:
            probability = props.readout_error(int(physical))
        except Exception:
            probability = None
        if probability is None:
            continue
        probability = float(probability)
        if not math.isfinite(probability):
            continue
        probability = min(max(probability, 0.0), 0.5)
        readout_table[int(physical)] = probability
        if probability > 0:
            readout = ReadoutError(
                [[1.0 - probability, probability], [probability, 1.0 - probability]]
            )
            target.add_readout_error(
                readout, [physical_to_compact[int(physical)]], warnings=False
            )
            copied_readout_errors += 1

    if copied_gate_errors == 0:
        raise RuntimeError(
            "Nenhuma taxa de erro de porta nativa foi encontrada para os qubits ativos."
        )
    if copied_readout_errors == 0:
        raise RuntimeError(
            "Nenhuma taxa de erro de leitura foi encontrada para os qubits ativos."
        )

    return target, {
        "source_noise_model": "modelo simplificado construído diretamente de BackendProperties do FakeAachen",
        "gate_error_model": "canal depolarizante por instrução nativa e conjunto de qubits físicos, com taxa gate_error do snapshot",
        "readout_error_model": "ReadoutError simétrico por qubit, parametrizado por props.readout_error(qubit)",
        "remapped_gate_error_entries": copied_gate_errors,
        "remapped_readout_error_entries": copied_readout_errors,
        "basis_gates": list(target.basis_gates),
        "noise_instructions": sorted(target.noise_instructions),
        "noise_qubits": sorted(target.noise_qubits),
        "readout_error_values_by_physical_qubit": {
            str(k): v for k, v in readout_table.items()
        },
        "limitations": [
            "não inclui relaxação T1/T2",
            "não inclui crosstalk, drift ou leakage",
            "readout modelado simetricamente a partir do erro médio",
            "não reproduz custom noise passes gerados internamente por NoiseModel.from_backend",
        ],
        "note": "Taxas do snapshot foram remapeadas de índices físicos para índices compactos; modelo simplificado e explicitamente aproximado.",
    }
