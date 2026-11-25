"""mede os circuitos depois da transpilação."""

from __future__ import annotations

import json
import math
from pathlib import Path

from backend import target_error


def layout_maps(compiled, logical_circuit):
    initial_map, final_map = [], []
    layout = getattr(compiled, "layout", None)
    if layout is None:
        return initial_map, final_map
    initial = getattr(layout, "initial_layout", None)
    if initial is not None:
        for i, q in enumerate(logical_circuit.qubits):
            try:
                initial_map.append({"logical": i, "physical": int(initial[q])})
            except Exception:
                pass
    try:
        final_indices = layout.final_index_layout(filter_ancillas=True)
        final_map = [
            {"logical_or_virtual_index": i, "physical": int(p)}
            for i, p in enumerate(final_indices)
        ]
    except Exception:
        final = getattr(layout, "final_layout", None)
        if final is not None:
            try:
                for q, p in final.get_virtual_bits().items():
                    final_map.append({"virtual": str(q), "physical": int(p)})
            except Exception:
                pass
    return initial_map, final_map


def collect_circuit_metrics(compiled, logical_circuit, backend):
    """coleta métricas em fluxo, sem criar listas com milhões de erros."""
    ops = dict(compiled.count_ops())
    twoq = 0
    used_physical = set()
    n_errors = 0
    log_survival_sum = 0.0
    one_error_sum = one_error_n = 0
    two_error_sum = two_error_n = 0
    read_error_sum = read_error_n = 0

    for item in compiled.data:
        name = item.operation.name
        if name == "barrier":
            continue
        qargs = [compiled.find_bit(q).index for q in item.qubits]
        used_physical.update(qargs)
        if len(qargs) == 2:
            twoq += 1
        err = target_error(backend, name, tuple(qargs))
        if err is not None and 0 <= err < 1:
            n_errors += 1
            log_survival_sum += math.log1p(-err)
            if name == "measure":
                read_error_sum += err
                read_error_n += 1
            elif len(qargs) == 1:
                one_error_sum += err
                one_error_n += 1
            elif len(qargs) == 2:
                two_error_sum += err
                two_error_n += 1

    fidelity_proxy = math.exp(log_survival_sum) if n_errors else None
    # o produto pode sofrer underflow após milhões de instruções. nesse caso,
    # o log continua sendo a métrica comparável; não grave zero como se fosse
    # uma estimativa física exata.
    if fidelity_proxy == 0.0:
        fidelity_proxy = None
    initial_map, final_map = layout_maps(compiled, logical_circuit)
    return {
        "depth": compiled.depth(),
        "total_ops": compiled.size(),
        "two_qubit_ops": twoq,
        "swap_count_after_translation": ops.get("swap", 0),
        "num_qubits_output": compiled.num_qubits,
        "unique_physical_qubits_used": len(used_physical),
        "physical_qubits_used_json": json.dumps(sorted(used_physical)),
        "native_gate_counts_json": json.dumps(ops, ensure_ascii=False, sort_keys=True),
        "initial_layout_json": json.dumps(initial_map, ensure_ascii=False),
        "final_layout_json": json.dumps(final_map, ensure_ascii=False),
        "mean_1q_error_used": one_error_sum / one_error_n if one_error_n else None,
        "mean_2q_error_used": two_error_sum / two_error_n if two_error_n else None,
        "mean_readout_error_used": read_error_sum / read_error_n
        if read_error_n
        else None,
        "n_instruction_errors_in_proxy": n_errors,
        # guarda o log da proxy para evitar underflow numérico em produtos muito pequenos.
        "log_fidelity_proxy_independent_errors": log_survival_sum if n_errors else None,
        "log10_fidelity_proxy_independent_errors": (log_survival_sum / math.log(10))
        if n_errors
        else None,
        "fidelity_proxy_independent_errors": fidelity_proxy,
    }


def write_circuit_preview(compiled, path, max_instructions=80):
    """salva um prefixo legível; evita desenhar milhões de instruções em texto."""
    preview = compiled.copy_empty_like()
    for item in compiled.data[:max_instructions]:
        preview.append(item.operation, item.qubits, item.clbits)
    header = (
        f"PRÉVIA DO CIRCUITO TRANSPILADO: primeiras {min(max_instructions, compiled.size())} "
        f"instruções de {compiled.size()} no total.\n"
        "Este desenho é apenas um prefixo ilustrativo; as métricas completas estão em resultados.csv.\n\n"
    )
    Path(path).write_text(
        header + str(preview.draw(output="text", fold=120)), encoding="utf-8"
    )
    del preview
