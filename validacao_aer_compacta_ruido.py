#!/usr/bin/env python3
"""Validação Aer compactada para E0/E3 do estudo Shor/FakeAachen.

A rotina recompila a instância original N=77, a=30 com os mesmos níveis de
otimização usados nos experimentos, remove fios físicos completamente ociosos
(sem remover operações lógicas) e reindexa o modelo de ruído FakeAachen para
os qubits compactados. A simulação MPS usa truncamento configurável e, por isso,
quando max_bond_dimension > 0, é uma simulação aproximada, não exata.

Uso recomendado no Mac:
  python validacao_aer_compacta.py --config E0 --mode ideal --shots 8
  python validacao_aer_compacta.py --config E0 --mode noisy --shots 8
  python validacao_aer_compacta.py --config E3 --mode ideal --shots 8
  python validacao_aer_compacta.py --config E3 --mode noisy --shots 8

Cada execução salva seu JSON/CSV separadamente. Não altera resultados.csv.
"""
from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

N = 77
A = 30
SEED = 42


def load_result_rows(csv_path: Path) -> dict[str, dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Não encontrei {csv_path}")
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        return {r["experiment_id"]: r for r in csv.DictReader(f)}


def count_summary(counts: dict[str, int]) -> dict[str, Any]:
    from shor_classical import recover_order
    total = sum(int(v) for v in counts.values())
    period = recover_order(counts, N, A, 2 * (N - 1).bit_length())
    period_valid = bool(period and pow(A, period, N) == 1)
    factors = None
    x = None
    if period_valid and period % 2 == 0:
        x = pow(A, period // 2, N)
        if x not in (1, N - 1):
            from math import gcd
            f1, f2 = sorted((gcd(x - 1, N), gcd(x + 1, N)))
            if 1 < f1 < N and 1 < f2 < N and f1 * f2 == N:
                factors = [f1, f2]
    top = sorted(((str(k), int(v)) for k, v in counts.items()), key=lambda kv: kv[1], reverse=True)[:20]
    return {
        "shots": total,
        "distinct_outcomes": len(counts),
        "top_20_counts": dict(top),
        "recovered_period": int(period) if period else None,
        "period_valid": period_valid,
        "x": int(x) if x is not None else None,
        "recovered_factors": factors,
        "factorization_success_in_postprocessing": factors is not None,
    }


def prepare_compact_dag(circuit):
    """Remove no DAG os fios físicos ociosos, sem duplicar o QuantumCircuit inteiro.

    O índice original de cada fio ativo é tratado como rótulo do qubit físico.
    Barreiras são removidas por serem diretivas sem efeito na unidade lógica.
    Retorna o DAG para que o chamador possa liberar o circuito de 156 fios antes
    de materializar o circuito compacto.
    """
    from qiskit.converters import circuit_to_dag

    original_depth = circuit.depth()
    original_size = circuit.size()
    original_width = circuit.num_qubits

    dag = circuit_to_dag(circuit, copy_operations=False)
    dag.remove_all_ops_named("barrier")

    active_physical = set()
    for node in dag.topological_op_nodes():
        for q in node.qargs:
            active_physical.add(circuit.find_bit(q).index)
    active_physical = sorted(active_physical)
    if not active_physical:
        raise RuntimeError("Não foram encontrados qubits ativos no circuito compilado.")

    active_set = set(active_physical)
    idle_qubits = [q for index, q in enumerate(dag.qubits) if index not in active_set]
    if idle_qubits:
        dag.remove_qubits(*idle_qubits)

    physical_to_compact = {physical: compact_index for compact_index, physical in enumerate(active_physical)}
    meta = {
        "original_width": original_width,
        "compact_width": len(active_physical),
        "original_depth": original_depth,
        "original_size": original_size,
        "active_physical_qubits": active_physical,
        "idle_physical_qubits_removed": original_width - len(active_physical),
        "barriers_removed": True,
    }
    return dag, active_physical, physical_to_compact, meta


def remap_backend_noise(backend, physical_to_compact):
    """Constrói um modelo de ruído simplificado a partir do snapshot FakeAachen.

    A implementação evita NoiseModel.from_backend(), que nesta combinação de
    backend/versão inclui custom noise passes que não podem ser reindexados
    automaticamente após a compactação. Em vez disso, usa:
      * erro médio de cada porta nativa (depolarizing_error por instrução/qargs);
      * erro médio de leitura de cada qubit (ReadoutError simétrico).

    É um modelo aproximado derivado das propriedades do FakeAachen. Não inclui
    relaxação T1/T2, crosstalk, drift, leakage nem os custom noise passes originais.
    Isso é explicitado no JSON e no relatório.
    """
    from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

    props = backend.properties()
    if props is None:
        raise RuntimeError("FakeAachen não disponibilizou BackendProperties para construir o modelo de ruído.")

    basis = ["id", "rz", "sx", "x", "cz"]
    target = NoiseModel(basis_gates=basis)
    gate_error_table = {}

    # Lê os erros calibrados por operação e conjunto de qubits físicos.
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
            # Fallback para a lista de parâmetros do registro de calibração.
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

        # CZ é simétrica. Se o snapshot só listar uma orientação da aresta,
        # aplica a mesma taxa também à orientação inversa no circuito compacto.
        if instruction == "cz" and len(physical_tuple) == 2:
            reverse_key = (instruction, tuple(reversed(physical_tuple)))
            if reverse_key not in gate_error_table:
                reverse_compact = [physical_to_compact[physical_tuple[1]], physical_to_compact[physical_tuple[0]]]
                target.add_quantum_error(error, [instruction], reverse_compact, warnings=False)
                copied_gate_errors += 1

    # Modelo simétrico de leitura por qubit, parametrizado pelo erro médio do snapshot.
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
            readout = ReadoutError([[1.0 - probability, probability],
                                    [probability, 1.0 - probability]])
            target.add_readout_error(readout, [physical_to_compact[int(physical)]], warnings=False)
            copied_readout_errors += 1

    if copied_gate_errors == 0:
        raise RuntimeError("Nenhuma taxa de erro de porta nativa foi encontrada para os qubits ativos.")
    if copied_readout_errors == 0:
        raise RuntimeError("Nenhuma taxa de erro de leitura foi encontrada para os qubits ativos.")

    return target, {
        "source_noise_model": "modelo simplificado construído diretamente de BackendProperties do FakeAachen",
        "gate_error_model": "canal depolarizante por instrução nativa e conjunto de qubits físicos, com taxa gate_error do snapshot",
        "readout_error_model": "ReadoutError simétrico por qubit, parametrizado por props.readout_error(qubit)",
        "remapped_gate_error_entries": copied_gate_errors,
        "remapped_readout_error_entries": copied_readout_errors,
        "basis_gates": list(target.basis_gates),
        "noise_instructions": sorted(target.noise_instructions),
        "noise_qubits": sorted(target.noise_qubits),
        "readout_error_values_by_physical_qubit": {str(k): v for k, v in readout_table.items()},
        "limitations": [
            "não inclui relaxação T1/T2",
            "não inclui crosstalk, drift ou leakage",
            "readout modelado simetricamente a partir do erro médio",
            "não reproduz custom noise passes gerados internamente por NoiseModel.from_backend",
        ],
        "note": "Taxas do snapshot foram remapeadas de índices físicos para índices compactos; modelo simplificado e explicitamente aproximado.",
    }


def make_compiled(backend, config_id: str):
    from qiskit import transpile
    from shor_quantum import build_order_finding_circuit

    logical = build_order_finding_circuit(N, A, synthesis="auto")
    level = 1 if config_id == "E0" else 3
    compiled = transpile(
        logical,
        backend=backend,
        optimization_level=level,
        seed_transpiler=SEED,
        num_processes=1,
    )
    return logical, compiled


def run_aer(compact, mode: str, backend, physical_to_compact, args):
    from qiskit_aer import AerSimulator

    options = {
        "method": "matrix_product_state",
        "max_parallel_threads": 1,
        "max_parallel_shots": 1,
        "matrix_product_state_max_bond_dimension": args.bond_dimension,
        "matrix_product_state_truncation_threshold": args.truncation_threshold,
        "mps_sample_measure_algorithm": "mps_apply_measure",
        "mps_log_data": True,
    }
    noise_meta = None
    if mode == "ideal":
        simulator = AerSimulator(**options)
    else:
        noise_model, noise_meta = remap_backend_noise(backend, physical_to_compact)
        simulator = AerSimulator(noise_model=noise_model, **options)

    start = time.perf_counter()
    job = simulator.run(compact, shots=args.shots, seed_simulator=args.seed)
    result = job.result()
    elapsed = time.perf_counter() - start
    counts = result.get_counts(compact)
    if isinstance(counts, list):
        counts = counts[0]
    summary = count_summary(counts)
    metadata = {}
    try:
        metadata = result.results[0].metadata or {}
    except Exception:
        pass
    return {
        "status": "completed",
        "mode": mode,
        "shots_requested": args.shots,
        "elapsed_seconds": round(elapsed, 3),
        "simulator": "AerSimulator(method=matrix_product_state)",
        "mps_max_bond_dimension": args.bond_dimension,
        "mps_truncation_threshold": args.truncation_threshold,
        "approximate_mps": bool(args.bond_dimension > 0 or args.truncation_threshold > 1e-16),
        "noise_model": noise_meta,
        "measurement_summary": summary,
        "counts": {str(k): int(v) for k, v in counts.items()},
        "aer_result_metadata": metadata,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", choices=["E0", "E3"], default="E0")
    p.add_argument("--mode", choices=["ideal", "noisy"], default="ideal")
    p.add_argument("--shots", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--bond-dimension", type=int, default=16,
                   help="limite de bond dimension MPS; 16 é uma aproximação deliberada para reduzir recursos")
    p.add_argument("--truncation-threshold", type=float, default=1e-8)
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()
    if args.shots < 1 or args.seed < 0 or args.bond_dimension < 0 or not (0 <= args.truncation_threshold < 1):
        p.error("shots deve ser >=1, seed >=0, bond-dimension >=0 e threshold entre 0 e 1.")

    project = Path(__file__).resolve().parent
    output = args.output or project / "resultados_fakeaachen" / "validacao_compacta"
    output.mkdir(parents=True, exist_ok=True)

    print("Carregando FakeAachen e montando somente a configuração solicitada...", flush=True)
    from qiskit_ibm_runtime.fake_provider import FakeAachen
    backend = FakeAachen()
    logical, compiled = make_compiled(backend, args.config)
    print(
        f"{args.config}: transpilado com {compiled.num_qubits} fios e {compiled.size()} instruções; "
        f"circuito lógico: {logical.num_qubits} qubits.", flush=True
    )

    dag, active_physical, physical_to_compact, compaction_meta = prepare_compact_dag(compiled)
    # Libera o circuito full-width antes de materializar a versão compacta.
    del compiled
    gc.collect()
    from qiskit.converters import dag_to_circuit
    compact = dag_to_circuit(dag, copy_operations=False)
    del dag
    gc.collect()
    compaction_meta["compact_depth"] = compact.depth()
    compaction_meta["compact_size"] = compact.size()
    if compact.num_qubits != len(active_physical):
        raise RuntimeError(
            f"Compactação inconsistente: {compact.num_qubits} fios no circuito compacto, "
            f"mas {len(active_physical)} qubits ativos detectados."
        )
    print(
        f"Compactação: {compaction_meta['original_width']} -> {compaction_meta['compact_width']} qubits; "
        f"instruções={compaction_meta['compact_size']}; qubits físicos ativos={active_physical}.", flush=True
    )

    csv_rows = load_result_rows(project / "resultados_fakeaachen" / "resultados.csv")
    expected_id = "E0_reference_L1_auto" if args.config == "E0" else "E3_L3_auto"
    recorded_active = json.loads(csv_rows[expected_id].get("physical_qubits_used_json") or "[]")
    if recorded_active and sorted(recorded_active) != active_physical:
        raise RuntimeError(
            "Os qubits físicos ativos desta recompilação não coincidem com o CSV. "
            f"CSV={sorted(recorded_active)}; recompilado={active_physical}. "
            "Não continuarei com a comparação de ruído para evitar mapear calibrações erradas."
        )

    output_qpy = output / f"{args.config}_compactado.qpy"
    try:
        from qiskit import qpy
        with output_qpy.open("wb") as f:
            qpy.dump(compact, f)
        print(f"Circuito compacto salvo: {output_qpy}", flush=True)
    except Exception as exc:
        print(f"Aviso: não foi possível salvar QPY compacto: {type(exc).__name__}: {exc}", flush=True)

    result_payload = {
        "config": args.config,
        "backend": backend.name,
        "N": N,
        "a": A,
        "seed_transpiler": SEED,
        "compaction": compaction_meta,
        "matches_recorded_physical_qubits": (not recorded_active or sorted(recorded_active) == active_physical),
        "method_note": (
            "Circuito transpilado preservado, exceto remoção de barreiras e fios físicos sem instruções. "
            "A simulação MPS usa truncamento configurável; resultados devem ser rotulados como aproximados. "
            "No modo noisy usa-se modelo simplificado derivado de gate_error e readout_error do snapshot, "
            "sem T1/T2 ou custom noise passes."
        ),
        "aer_runs": {},
    }
    stem = f"{args.config}_{args.mode}_mps_bond{args.bond_dimension}_shots{args.shots}"
    json_path = output / f"{stem}.json"
    counts_path = output / f"{stem}_counts.csv"
    result_payload["aer_runs"][args.mode] = {
        "status": "running",
        "shots_requested": args.shots,
        "mps_max_bond_dimension": args.bond_dimension,
        "mps_truncation_threshold": args.truncation_threshold,
    }
    json_path.write_text(json.dumps(result_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Iniciando Aer ({args.mode}) com shots={args.shots}, bond_dimension={args.bond_dimension}, threshold={args.truncation_threshold}...", flush=True)
    try:
        run_result = run_aer(compact, args.mode, backend, physical_to_compact, args)
        result_payload["aer_runs"][args.mode] = run_result
    except KeyboardInterrupt:
        result_payload["aer_runs"][args.mode] = {
            "status": "interrupted_by_user",
            "details": "Simulação interrompida manualmente antes da conclusão; nenhuma contagem foi produzida.",
            "shots_requested": args.shots,
            "mps_max_bond_dimension": args.bond_dimension,
            "mps_truncation_threshold": args.truncation_threshold,
        }
        json_path.write_text(json.dumps(result_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"Interrupção registrada em: {json_path}", flush=True)
        return 130
    except Exception as exc:
        result_payload["aer_runs"][args.mode] = {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "shots_requested": args.shots,
        }
        json_path.write_text(json.dumps(result_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"Simulação falhou; erro registrado em {json_path}: {type(exc).__name__}: {exc}", flush=True)
        return 1

    json_path.write_text(json.dumps(result_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    with counts_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["bitstring", "count"])
        for bitstring, count in sorted(run_result["counts"].items(), key=lambda kv: (-kv[1], kv[0])):
            writer.writerow([bitstring, count])
    print(f"Concluído: período={run_result['measurement_summary']['recovered_period']}; "
          f"fatores={run_result['measurement_summary']['recovered_factors']}.", flush=True)
    print(f"JSON: {json_path}", flush=True)
    print(f"Contagens: {counts_path}", flush=True)
    del compact, logical
    gc.collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
