#!/usr/bin/env python3
"""validação compactada de E0 e E3 com o AerSimulator.

a rotina recompila a instância N=77, a=30 com os mesmos níveis de
otimização usados nos experimentos, remove fios físicos completamente ociosos
(sem remover operações lógicas) e reindexa o modelo de ruído fakeaachen para
os qubits compactados. a simulação mps usa truncamento configurável e, por isso,
quando max_bond_dimension > 0, é uma simulação aproximada, não exata.

uso recomendado no mac:
  python validar_aer.py --config e0 --mode ideal --shots 8
  python validar_aer.py --config e0 --mode noisy --shots 8
  python validar_aer.py --config e3 --mode ideal --shots 8
  python validar_aer.py --config e3 --mode noisy --shots 8

cada execução salva seu JSON e CSV separadamente. o arquivo resultados.csv não é alterado.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import time
from pathlib import Path
from typing import Any

from ruido import remap_backend_noise

N = 77
A = 30
SEED = 42


def load_result_rows(csv_path: Path) -> dict[str, dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Não encontrei {csv_path}")
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        return {r["experiment_id"]: r for r in csv.DictReader(f)}


def count_summary(counts: dict[str, int]) -> dict[str, Any]:
    from classical import recover_order

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
    top = sorted(
        ((str(k), int(v)) for k, v in counts.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )[:20]
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
    """remove no dag os fios físicos ociosos, sem duplicar o quantumcircuit inteiro.

    o índice original de cada fio ativo é tratado como rótulo do qubit físico.
    barreiras são removidas por serem diretivas sem efeito na unidade lógica.
    retorna o dag para que o chamador possa liberar o circuito de 156 fios antes
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

    physical_to_compact = {
        physical: compact_index
        for compact_index, physical in enumerate(active_physical)
    }
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


def make_compiled(backend, config_id: str):
    from qiskit import transpile
    from quantum import build_order_finding_circuit

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
    metadata_summary = {}
    try:
        raw_metadata = result.results[0].metadata or {}
        for key, value in raw_metadata.items():
            if value is None or isinstance(value, (str, int, float, bool)):
                metadata_summary[key] = value
    except Exception:
        metadata_summary = {}
    return {
        "status": "completed",
        "mode": mode,
        "shots_requested": args.shots,
        "elapsed_seconds": round(elapsed, 3),
        "simulator": "AerSimulator(method=matrix_product_state)",
        "mps_max_bond_dimension": args.bond_dimension,
        "mps_truncation_threshold": args.truncation_threshold,
        "approximate_mps": bool(
            args.bond_dimension > 0 or args.truncation_threshold > 1e-16
        ),
        "noise_model": noise_meta,
        "measurement_summary": summary,
        "counts": {str(k): int(v) for k, v in counts.items()},
        "aer_result_metadata_summary": metadata_summary,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", choices=["E0", "E3"], default="E0")
    p.add_argument("--mode", choices=["ideal", "noisy"], default="ideal")
    p.add_argument("--shots", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--bond-dimension",
        type=int,
        default=16,
        help="limite de bond dimension MPS; 16 é uma aproximação deliberada para reduzir recursos",
    )
    p.add_argument("--truncation-threshold", type=float, default=1e-8)
    p.add_argument("--output", type=Path, default=None)
    args = p.parse_args()
    if (
        args.shots < 1
        or args.seed < 0
        or args.bond_dimension < 0
        or not (0 <= args.truncation_threshold < 1)
    ):
        p.error(
            "shots deve ser >=1, seed >=0, bond-dimension >=0 e threshold entre 0 e 1."
        )

    project = Path(__file__).resolve().parent
    output = args.output or project / "resultados" / "validacao_compacta"
    output.mkdir(parents=True, exist_ok=True)

    print(
        "Carregando FakeAachen e montando somente a configuração solicitada...",
        flush=True,
    )
    from qiskit_ibm_runtime.fake_provider import FakeAachen

    backend = FakeAachen()
    logical, compiled = make_compiled(backend, args.config)
    print(
        f"{args.config}: transpilado com {compiled.num_qubits} fios e {compiled.size()} instruções; "
        f"circuito lógico: {logical.num_qubits} qubits.",
        flush=True,
    )

    dag, active_physical, physical_to_compact, compaction_meta = prepare_compact_dag(
        compiled
    )
    # libera o circuito full-width antes de materializar a versão compacta.
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
        f"instruções={compaction_meta['compact_size']}; qubits físicos ativos={active_physical}.",
        flush=True,
    )

    csv_rows = load_result_rows(project / "resultados" / "resultados.csv")
    expected_id = "E0_reference_L1_auto" if args.config == "E0" else "E3_L3_auto"
    recorded_active = json.loads(
        csv_rows[expected_id].get("physical_qubits_used_json") or "[]"
    )
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
        print(
            f"Aviso: não foi possível salvar QPY compacto: {type(exc).__name__}: {exc}",
            flush=True,
        )

    result_payload = {
        "config": args.config,
        "backend": backend.name,
        "N": N,
        "a": A,
        "seed_transpiler": SEED,
        "compaction": compaction_meta,
        "matches_recorded_physical_qubits": (
            not recorded_active or sorted(recorded_active) == active_physical
        ),
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
    json_path.write_text(
        json.dumps(result_payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(
        f"Iniciando Aer ({args.mode}) com shots={args.shots}, bond_dimension={args.bond_dimension}, threshold={args.truncation_threshold}...",
        flush=True,
    )
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
        json_path.write_text(
            json.dumps(result_payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"Interrupção registrada em: {json_path}", flush=True)
        return 130
    except Exception as exc:
        result_payload["aer_runs"][args.mode] = {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "shots_requested": args.shots,
        }
        json_path.write_text(
            json.dumps(result_payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(
            f"Simulação falhou; erro registrado em {json_path}: {type(exc).__name__}: {exc}",
            flush=True,
        )
        return 1

    json_path.write_text(
        json.dumps(result_payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    with counts_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["bitstring", "count"])
        for bitstring, count in sorted(
            run_result["counts"].items(), key=lambda kv: (-kv[1], kv[0])
        ):
            writer.writerow([bitstring, count])
    print(
        f"Concluído: período={run_result['measurement_summary']['recovered_period']}; "
        f"fatores={run_result['measurement_summary']['recovered_factors']}.",
        flush=True,
    )
    print(f"JSON: {json_path}", flush=True)
    print(f"Contagens: {counts_path}", flush=True)
    del compact, logical
    gc.collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
