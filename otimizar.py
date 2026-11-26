"""executa e compara as configurações de transpilação do circuito de shor."""

from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import platform
import statistics
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from backend import (
    bfs_region,
    collect_backend_data,
    find_low_error_region,
    plot_topology,
    write_calibration_files,
)
from graficos import render_comparison_plots, write_report
from metricas import collect_circuit_metrics, write_circuit_preview

N = 77
A = 30
SEED = 42
OUTPUT = Path(__file__).resolve().parent / "resultados"


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "não instalado"


def make_experiments(low_region, center_region):
    return [
        {
            "id": "E0_reference_L1_auto",
            "description": "Referência obrigatória: optimization_level=1, sem initial_layout manual.",
            "optimization_level": 1,
        },
        {
            "id": "E1_L0_auto",
            "description": "Nível de otimização 0, layout automático padrão.",
            "optimization_level": 0,
        },
        {
            "id": "E2_L2_auto",
            "description": "Nível de otimização 2, layout automático padrão.",
            "optimization_level": 2,
        },
        {
            "id": "E3_L3_auto",
            "description": "Nível de otimização 3, layout automático padrão.",
            "optimization_level": 3,
        },
        {
            "id": "E4_sabre_sabre",
            "description": "Layout SABRE e roteamento SABRE, optimization_level=1.",
            "optimization_level": 1,
            "layout_method": "sabre",
            "routing_method": "sabre",
        },
        {
            "id": "E5_dense_basic",
            "description": "Layout DENSE e roteamento BASIC, optimization_level=1.",
            "optimization_level": 1,
            "layout_method": "dense",
            "routing_method": "basic",
        },
        {
            "id": "E6_manual_low_error",
            "description": "Initial layout manual em subgrafo conectado de menor custo de calibração; roteamento SABRE.",
            "optimization_level": 1,
            "initial_layout": low_region,
            "routing_method": "sabre",
        },
        {
            "id": "E7_manual_low_error_reversed",
            "description": "Mesmo conjunto de qubits de E6, ordem lógica-física invertida para isolar o efeito do mapeamento.",
            "optimization_level": 1,
            "initial_layout": list(reversed(low_region)),
            "routing_method": "sabre",
        },
        {
            "id": "E8_manual_center",
            "description": "Initial layout manual em subgrafo conectado iniciado próximo ao centro dos índices físicos; roteamento SABRE.",
            "optimization_level": 1,
            "initial_layout": center_region,
            "routing_method": "sabre",
        },
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--skip-experiment",
        action="append",
        default=[],
        help="ID de experimento a pular, preservando uma linha explícita no CSV; pode ser repetido",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="reaproveita linhas status=ok já gravadas no CSV e continua os experimentos pendentes",
    )
    args = parser.parse_args()

    try:
        from qiskit import transpile
        from qiskit_ibm_runtime.fake_provider import FakeAachen
        from quantum import build_order_finding_circuit
    except ImportError as exc:
        raise SystemExit(
            "Dependência ausente. Execute `python -m pip install -r requirements.txt`. "
            f"Detalhe: {exc}"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    backend = FakeAachen()
    logical_qubits = 3 * (N - 1).bit_length()
    if backend.num_qubits < logical_qubits:
        raise RuntimeError(
            f"FakeAachen tem {backend.num_qubits} qubits; circuito requer {logical_qubits}."
        )

    print(
        f"Backend: {backend.name}; qubits: {backend.num_qubits}; logical circuit qubits: {logical_qubits}"
    )
    print("Construindo circuito lógico do código-base do professor (N=77, a=30)...")
    circuit = build_order_finding_circuit(N, A, synthesis="auto")
    (args.output / "circuito_logico.txt").write_text(
        circuit.draw(output="text", fold=120).__str__(), encoding="utf-8"
    )

    data = collect_backend_data(backend)
    low_region, low_score = find_low_error_region(data, circuit.num_qubits)
    center_region = bfs_region(
        data["graph"], circuit.num_qubits, backend.num_qubits // 2
    )
    write_calibration_files(backend, data, args.output)
    plot_topology(
        data, low_region, center_region, args.output / "topologia_fakeaachen.png"
    )
    (args.output / "regioes_qubits.json").write_text(
        json.dumps(
            {
                "low_error_connected_region": low_region,
                "low_error_region_score": low_score,
                "central_bfs_region": center_region,
                "note": "Regiões calculadas do snapshot local do FakeAachen; seed e algoritmo documentados no código.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    experiment_specs = make_experiments(low_region, center_region)
    rows = []
    columns = None
    csv_path = args.output / "resultados.csv"
    if args.resume and csv_path.exists():
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        print(
            f"Retomada: {len(rows)} registro(s) previamente salvo(s) em {csv_path}",
            flush=True,
        )

    def persist_rows():
        nonlocal columns
        columns = sorted({key for item in rows for key in item})
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
            f.flush()

    def transpile_kwargs(spec):
        kwargs = {
            "backend": backend,
            "optimization_level": spec["optimization_level"],
            "seed_transpiler": args.seed,
            "num_processes": 1,
        }
        for key in ("layout_method", "routing_method", "initial_layout"):
            if key in spec:
                kwargs[key] = spec[key]
        return kwargs

    for spec in experiment_specs:
        previous = next((r for r in rows if r.get("experiment_id") == spec["id"]), None)
        if args.resume and previous and previous.get("status") == "skipped":
            print(
                f"\n[{spec['id']}] Mantido do CSV existente (status=skipped).",
                flush=True,
            )
            continue
        if (
            args.resume
            and previous
            and previous.get("status") == "ok"
            and previous.get("log10_fidelity_proxy_independent_errors")
            not in (None, "")
        ):
            print(
                f"\n[{spec['id']}] Mantido do CSV existente (métrica logarítmica presente).",
                flush=True,
            )
            continue
        if previous:
            rows = [r for r in rows if r.get("experiment_id") != spec["id"]]
        row = {
            "experiment_id": spec["id"],
            "description": spec["description"],
            "N": N,
            "base_a": A,
            "logical_qubits": circuit.num_qubits,
            "optimization_level": spec["optimization_level"],
            "layout_method": spec.get("layout_method", "auto"),
            "routing_method": spec.get("routing_method", "default"),
            "manual_layout": bool("initial_layout" in spec),
            "initial_layout_input_json": json.dumps(
                spec.get("initial_layout"), ensure_ascii=False
            )
            if "initial_layout" in spec
            else "",
            "seed_transpiler": args.seed,
            "status": "not_run",
            "error": "",
        }
        if spec["id"] in set(args.skip_experiment):
            row["status"] = "skipped"
            row["error"] = (
                "Experimento explicitamente pulado por --skip-experiment; execução anterior foi encerrada pelo sistema operacional antes de produzir métricas."
            )
            rows.append(row)
            persist_rows()
            print(
                f"\n[{spec['id']}] PULADO conforme --skip-experiment; registro gravado no CSV."
            )
            continue

        print(f"\n[{spec['id']}] {spec['description']}", flush=True)
        start = time.perf_counter()
        compiled = None
        try:
            print(
                f"[{spec['id']}] etapa 1/3: iniciando transpile (um processo).",
                flush=True,
            )
            compiled = transpile(circuit, **transpile_kwargs(spec))
            elapsed = time.perf_counter() - start
            print(
                f"[{spec['id']}] etapa 2/3: transpile concluída em {elapsed:.2f}s; coletando métricas em fluxo.",
                flush=True,
            )
            metrics = collect_circuit_metrics(compiled, circuit, backend)
            print(
                f"[{spec['id']}] etapa 3/3: métricas coletadas; salvando resultado.",
                flush=True,
            )
            row.update(metrics)
            row["transpile_time_s"] = round(elapsed, 6)
            row["status"] = "ok"

            # guardar somente a referência imediatamente. os demais circuitos
            # são liberados e o recomendado será recompilado uma única vez ao final.
            if spec["id"] == "E0_reference_L1_auto":
                write_circuit_preview(
                    compiled,
                    args.output / "circuito_referencia_transpilado.txt",
                    max_instructions=80,
                )
            if spec["id"] == "E3_L3_auto":
                write_circuit_preview(
                    compiled,
                    args.output / "circuito_E3_transpilado.txt",
                    max_instructions=80,
                )
            print(
                f"depth={row['depth']} ops={row['total_ops']} "
                f"2Q={row['two_qubit_ops']} time={elapsed:.2f}s",
                flush=True,
            )
            compiled = None
            gc.collect()
        except Exception as exc:
            row["transpile_time_s"] = round(time.perf_counter() - start, 6)
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"ERRO: {row['error']}", flush=True)
            compiled = None
            gc.collect()

        rows.append(row)
        persist_rows()  # checkpoint depois de cada experimento

    (args.output / "experiment_configurations.json").write_text(
        json.dumps(experiment_specs, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # seleção multicritério por ranking médio; não escolhe apenas menor profundidade.
    valid = [r for r in rows if r["status"] == "ok"]
    best_id = None
    if valid:
        ranking_keys = ["depth", "two_qubit_ops", "total_ops"]
        rank_maps = {}
        for key in ranking_keys:
            ordered = sorted(valid, key=lambda r: float(r.get(key, math.inf)))
            rank_maps[key] = {r["experiment_id"]: i + 1 for i, r in enumerate(ordered)}
        with_fid = [
            r
            for r in valid
            if r.get("log10_fidelity_proxy_independent_errors") not in (None, "")
        ]
        if with_fid:
            ordered = sorted(
                with_fid,
                key=lambda r: float(r["log10_fidelity_proxy_independent_errors"]),
                reverse=True,
            )
            rank_maps["log10_fidelity_proxy_independent_errors"] = {
                r["experiment_id"]: i + 1 for i, r in enumerate(ordered)
            }
        ranked = []
        for r in valid:
            ranks = [rank_maps[k][r["experiment_id"]] for k in ranking_keys]
            if r["experiment_id"] in rank_maps.get(
                "log10_fidelity_proxy_independent_errors", {}
            ):
                ranks.append(
                    rank_maps["log10_fidelity_proxy_independent_errors"][
                        r["experiment_id"]
                    ]
                )
            ranked.append((statistics.mean(ranks), r))
        _, winner = min(ranked, key=lambda pair: pair[0])
        best_id = winner["experiment_id"]
        best_spec = next(spec for spec in experiment_specs if spec["id"] == best_id)
        print(
            f"\nRecompilando apenas a configuração recomendada: {best_id}", flush=True
        )
        best_circuit = transpile(circuit, **transpile_kwargs(best_spec))
        write_circuit_preview(
            best_circuit, args.output / "circuito_recomendado.txt", max_instructions=80
        )
        (args.output / "configuracao_recomendada.json").write_text(
            json.dumps(
                {
                    "experiment_id": best_id,
                    "selection_method": "ranking médio em profundidade, gates 2Q, operações totais e log10 da proxy de fidelidade quando disponível",
                    "warning": "A seleção é multicritério auxiliar; a decisão final exige interpretação dos resultados e das limitações do proxy. O circuito foi recompilado com os mesmos parâmetros para exportação.",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        # libera o circuito recompilado depois de salvar a prévia.
        del best_circuit
        gc.collect()

    render_comparison_plots(rows, args.output)
    backend_info = {
        "name": backend.name,
        "num_qubits": backend.num_qubits,
        "operation_names": list(backend.operation_names),
        "coupling_edges": len(data["edges"]),
    }
    write_report(rows, backend_info, args.output, N, A, args.seed)
    versions = {
        "python": platform.python_version(),
        "qiskit": package_version("qiskit"),
        "qiskit-aer": package_version("qiskit-aer"),
        "qiskit-ibm-runtime": package_version("qiskit-ibm-runtime"),
        "numpy": package_version("numpy"),
        "matplotlib": package_version("matplotlib"),
        "networkx": package_version("networkx"),
    }
    (args.output / "versions.json").write_text(
        json.dumps(versions, indent=2), encoding="utf-8"
    )
    print(f"\nExperimentos concluídos: {len(valid)}/{len(rows)}")
    print(f"Configuração multicritério indicativa: {best_id or 'nenhuma'}")
    print(f"Resultados em: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
