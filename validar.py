#!/usr/bin/env python3
"""validação reduzida do circuito lógico e dos resultados salvos.

executa a simulação ideal do circuito lógico de busca de ordem usando a
implementação numpy do projeto, recupera e verifica o período/fatores e
consolida as métricas já medidas dos circuitos transpilados e0 e e3.

esta rotina não inicia novas simulações Aer. ela reproduz a
simulação lógica ideal numpy e audita as contagens mps já salvas para e3,
mantendo explícitas as limitações da aproximação.
"""

from __future__ import annotations

import argparse
import csv
import json
from math import gcd
from pathlib import Path

N = 77
A = 30
DEFAULT_SHOTS = 1024
DEFAULT_SEED = 42
EXPECTED_PERIOD = 30
REQUIRED_IDS = ("E0_reference_L1_auto", "E3_L3_auto")


def load_experiment_rows(csv_path: Path) -> dict[str, dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV não encontrado: {csv_path}")
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    indexed = {r.get("experiment_id", ""): r for r in rows}
    missing = [key for key in REQUIRED_IDS if key not in indexed]
    if missing:
        raise ValueError(f"Experimentos ausentes em {csv_path}: {missing}")
    for key in REQUIRED_IDS:
        if indexed[key].get("status") != "ok":
            raise ValueError(f"{key} não está com status=ok no CSV.")
    return indexed


def parse_json_field(row: dict[str, str], key: str, default):
    raw = row.get(key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def validate_period_and_factors(period: int | None) -> dict:
    if period is None:
        return {
            "recovered_period": None,
            "period_valid": False,
            "factorization_valid": False,
            "reason": "Não foi possível recuperar o período a partir das contagens.",
        }
    period_ok = period > 0 and pow(A, period, N) == 1
    if not period_ok:
        return {
            "recovered_period": period,
            "period_valid": False,
            "factorization_valid": False,
            "reason": "O período recuperado não satisfaz a^r mod N = 1.",
        }
    if period % 2:
        return {
            "recovered_period": period,
            "period_valid": True,
            "factorization_valid": False,
            "reason": "O período recuperado é ímpar; não permite a extração usual.",
        }
    x = pow(A, period // 2, N)
    if x in (1, N - 1):
        return {
            "recovered_period": period,
            "period_valid": True,
            "x": x,
            "factorization_valid": False,
            "reason": "a^(r/2) mod N é 1 ou -1; a extração não produz fatores não triviais.",
        }
    f1, f2 = sorted((gcd(x - 1, N), gcd(x + 1, N)))
    ok = f1 not in (1, N) and f2 not in (1, N) and f1 * f2 == N
    return {
        "recovered_period": period,
        "period_valid": True,
        "x": x,
        "factors": [f1, f2] if ok else None,
        "factorization_valid": ok,
        "verification": f"{f1} × {f2} = {f1 * f2}",
    }


def experiment_summary(row: dict[str, str], basis_ops: set[str]) -> dict:
    gates = parse_json_field(row, "native_gate_counts_json", {})
    physical = parse_json_field(row, "physical_qubits_used_json", [])
    final_layout = parse_json_field(row, "final_layout_json", [])
    gate_names = set(gates)
    unsupported = sorted(gate_names - basis_ops) if basis_ops else []
    return {
        "status": row.get("status"),
        "optimization_level": int(row["optimization_level"]),
        "depth": int(row["depth"]),
        "total_ops": int(row["total_ops"]),
        "two_qubit_ops": int(row["two_qubit_ops"]),
        "transpile_time_s": float(row["transpile_time_s"]),
        "log10_fidelity_proxy_independent_errors": float(
            row["log10_fidelity_proxy_independent_errors"]
        ),
        "num_qubits_output": int(row.get("num_qubits_output") or 0),
        "unique_physical_qubits_used": int(
            row.get("unique_physical_qubits_used") or len(physical)
        ),
        "physical_qubits_used": physical,
        "final_layout": final_layout,
        "native_gate_counts": gates,
        "native_gate_set_supported_by_snapshot": not unsupported,
        "unsupported_gate_names_vs_snapshot": unsupported,
        "explicit_swaps_after_translation": int(
            row.get("swap_count_after_translation") or 0
        ),
    }


def audit_mps_counts(csv_path: Path, recover_order) -> dict | None:
    """lê contagens Aer já salvas, sem iniciar outra simulação."""
    if not csv_path.exists():
        return None

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        counts = {row["bitstring"]: int(row["count"]) for row in csv.DictReader(f)}
    if not counts:
        return None

    shots = sum(counts.values())
    period = recover_order(counts, N, A, 2 * (N - 1).bit_length())
    phase_dimension = 1 << (2 * (N - 1).bit_length())
    shots_near_ideal_peak = 0
    for bitstring, count in counts.items():
        measured = int(bitstring.replace(" ", ""), 2)
        peak_index = round(measured * EXPECTED_PERIOD / phase_dimension)
        nearest_peak = peak_index * phase_dimension / EXPECTED_PERIOD
        if abs(measured - nearest_peak) <= 1:
            shots_near_ideal_peak += count

    return {
        "source_csv": str(csv_path),
        "shots": shots,
        "distinct_outcomes": len(counts),
        "maximum_outcome_count": max(counts.values()),
        **validate_period_and_factors(period),
        "shots_within_one_count_bin_of_nearest_r30_peak": shots_near_ideal_peak,
        "fraction_within_one_count_bin_of_nearest_r30_peak": (
            shots_near_ideal_peak / shots if shots else None
        ),
        "note": (
            "A auditoria de proximidade aos picos é descritiva. Para MPS com truncamento, "
            "não constitui prova de equivalência nem estimativa da probabilidade de fatoração."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=int, default=DEFAULT_SHOTS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.shots <= 0 or args.seed < 0:
        parser.error("--shots deve ser positivo e --seed não pode ser negativo.")

    project = Path(__file__).resolve().parent
    outdir = args.output or (project / "resultados")
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "resultados.csv"
    snapshot_path = outdir / "backend_snapshot.json"

    # 1. reproduz a validação ideal do circuito lógico de busca de ordem.
    # esta simulação numpy implementa a evolução lógica reduzida (registro de
    # contagem + registro alvo), não o circuito físico de 156 fios.
    try:
        from quantum import simulate_order_finding
        from classical import recover_order
    except Exception as exc:
        raise SystemExit(f"Não foi possível importar os módulos do projeto: {exc}")

    print(
        f"Simulação ideal do circuito lógico: N={N}, a={A}, shots={args.shots}, seed={args.seed}",
        flush=True,
    )
    counts = simulate_order_finding(N, A, shots=args.shots, seed=args.seed)
    shots_done = sum(counts.values())
    period = recover_order(counts, N, A, 2 * (N - 1).bit_length())
    order_factor_check = validate_period_and_factors(period)
    logical_result = {
        "method": "simulação ideal NumPy do circuito lógico de busca de ordem (módulo quantum.py)",
        "not_aer": True,
        "N": N,
        "a": A,
        "shots_requested": args.shots,
        "shots_obtained": shots_done,
        "seed": args.seed,
        "distinct_measurement_outcomes": len(counts),
        "measurement_counts": counts,
        **order_factor_check,
    }

    # 2. confere os resultados já medidos dos circuitos físicos transpilados.
    rows = load_experiment_rows(csv_path)
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        basis_ops = set(snapshot.get("basis_operation_names") or [])
    else:
        snapshot = {}
        basis_ops = set()

    e0 = experiment_summary(rows[REQUIRED_IDS[0]], basis_ops)
    e3 = experiment_summary(rows[REQUIRED_IDS[1]], basis_ops)
    comparison = {
        "E0_reference_L1_auto": e0,
        "E3_L3_auto": e3,
        "reductions_E3_vs_E0_percent": {
            "depth": 100 * (1 - e3["depth"] / e0["depth"]),
            "total_ops": 100 * (1 - e3["total_ops"] / e0["total_ops"]),
            "two_qubit_ops": 100 * (1 - e3["two_qubit_ops"] / e0["two_qubit_ops"]),
        },
        "log10_proxy_E3_minus_E0": (
            e3["log10_fidelity_proxy_independent_errors"]
            - e0["log10_fidelity_proxy_independent_errors"]
        ),
    }

    validation = {
        "validation_type": "reduced_validation_with_explicit_resource_limit",
        "backend": snapshot.get("backend_name", "fake_aachen"),
        "N": N,
        "a": A,
        "logical_original_ideal": logical_result,
        "transpiled_circuit_structural_audit": comparison,
        "aer_simulation_E0_E3": {
            "status": "E0_not_completed_E3_compacted_MPS_exploratory",
            "details": (
                "A tentativa Aer full-width de E0 (156 fios físicos, 2.519.962 instruções) "
                "foi interrompida manualmente antes de produzir contagens. Para E3 existem "
                "execuções compactadas MPS separadas, com bond dimension máximo 16 e truncamento "
                "de 1e-8, auditadas em transpiled_E3_mps_count_audits. Essa aproximação apresentou "
                "distribuição muito mais dispersa que a amostra lógica ideal e não deve ser tratada "
                "como validação conclusiva. O resultado ruidoso de 8 shots é somente exploratório."
            ),
        },
        "interpretation": (
            "A simulação NumPy valida o fluxo ideal do circuito lógico original. As métricas "
            "E0/E3 são resultados reais de transpilação. A execução compactada MPS de E3 é "
            "aproximada e inconclusiva quanto à preservação da distribuição; a execução ruidosa "
            "disponível tem somente 8 shots. A tentativa Aer full-width de E0 foi interrompida."
        ),
    }

    counts_path = outdir / "validacao_logica_counts.csv"
    with counts_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["bitstring", "count"])
        for bitstring, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            writer.writerow([bitstring, count])

    # lê as contagens mps já existentes. esta auditoria não inicia outro job aer.
    mps_dir = outdir / "validacao_compacta"
    mps_audits = {}
    if mps_dir.exists():
        for count_file in sorted(mps_dir.glob("E3_*_counts.csv")):
            audit = audit_mps_counts(count_file, recover_order)
            if audit is not None:
                mps_audits[count_file.name] = audit
    validation["transpiled_E3_mps_count_audits"] = mps_audits

    json_path = outdir / "validacao_reduzida.json"
    json_path.write_text(
        json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    md = [
        "# Validação reduzida — Shor / FakeAachen",
        "",
        "## 1. Circuito lógico original — simulação ideal",
        "",
        f"- Instância: N={N}, a={A}.",
        f"- Método: {logical_result['method']}.",
        f"- Shots: {shots_done}; seed: {args.seed}; resultados distintos: {len(counts)}.",
        f"- Período recuperado: {period}.",
        f"- Verificação modular: a^r mod N = {pow(A, period, N) if period else 'não disponível'}.",
        f"- Fatores recuperados: {logical_result.get('factors')}.",
        f"- Fatoração verificada: {'sim' if logical_result.get('factorization_valid') else 'não'}.",
        "",
        "Esta etapa simula o circuito lógico por uma implementação NumPy da evolução do registro de contagem e do registro alvo. Não é uma execução do Aer e não representa o circuito físico pós-transpilação.",
        "",
        "## 2. Auditoria estrutural dos circuitos transpilados",
        "",
        "| Métrica | E0 — Referência | E3 — Otimizado |",
        "|---|---:|---:|",
        f"| Profundidade | {e0['depth']:,} | {e3['depth']:,} |",
        f"| Operações totais | {e0['total_ops']:,} | {e3['total_ops']:,} |",
        f"| Operações de 2 qubits | {e0['two_qubit_ops']:,} | {e3['two_qubit_ops']:,} |",
        f"| Qubits físicos distintos usados | {e0['unique_physical_qubits_used']} | {e3['unique_physical_qubits_used']} |",
        f"| Tempo de transpilação (s) | {e0['transpile_time_s']:.3f} | {e3['transpile_time_s']:.3f} |",
        f"| log10(proxy) | {e0['log10_fidelity_proxy_independent_errors']:.3f} | {e3['log10_fidelity_proxy_independent_errors']:.3f} |",
        "",
        f"Reduções de E3 vs. E0: profundidade {comparison['reductions_E3_vs_E0_percent']['depth']:.2f}%; operações totais {comparison['reductions_E3_vs_E0_percent']['total_ops']:.2f}%; operações 2Q {comparison['reductions_E3_vs_E0_percent']['two_qubit_ops']:.2f}%.",
        f"A diferença de log10(proxy), E3 − E0, é {comparison['log10_proxy_E3_minus_E0']:.3f}; valor positivo favorece E3 nessa proxy aproximada.",
        "",
        "## 3. Auditoria das contagens MPS já existentes",
        "",
    ]
    if mps_audits:
        md.extend(
            [
                "As contagens abaixo foram lidas de CSVs existentes; esta rotina não inicia novas simulações Aer.",
                "",
                "| Arquivo | Shots | Resultados distintos | Maior frequência | Período | Fatores | Próximos a pico r=30 (±1 bin) | % |",
                "|---|---:|---:|---:|---:|---|---:|---:|",
            ]
        )
        for filename, audit in mps_audits.items():
            factors = audit.get("factors")
            md.append(
                f"| {filename} | {audit['shots']} | {audit['distinct_outcomes']} | "
                f"{audit['maximum_outcome_count']} | {audit.get('recovered_period')} | "
                f"{factors if factors is not None else '—'} | "
                f"{audit['shots_within_one_count_bin_of_nearest_r30_peak']} | "
                f"{100 * audit['fraction_within_one_count_bin_of_nearest_r30_peak']:.2f}% |"
            )
        md.extend(
            [
                "",
                "A distância aos picos esperados é apenas uma verificação descritiva. Bond dimension e truncamento limitam a precisão do MPS; recuperar um período no pós-processamento, isoladamente, não comprova que a distribuição foi preservada.",
                "",
            ]
        )
    else:
        md.extend(
            [
                "Não foram encontrados CSVs de contagens MPS E3 no diretório de validação.",
                "",
            ]
        )
    md.extend(
        [
            "## 4. Limitação da simulação dos circuitos físicos",
            "",
            "A tentativa Aer para E0 foi iniciada, mas foi interrompida manualmente antes de produzir contagens. A simulação lógica ideal NumPy não substitui uma distribuição de medições do circuito transpilado. A validação MPS E3 disponível é aproximada e deve ser interpretada à luz da auditoria de distribuição acima.",
            "A amostra ruidosa E3 de 8 shots é exploratória e pequena demais para estimar uma taxa de sucesso. Não há uma comparação estatística E0/E3 ideal e ruidosa concluída.",
            "",
            "## 5. Conclusão da validação reduzida",
            "",
            "A simulação ideal do circuito lógico recupera r=30 e os fatores 7 e 11. E3 apresenta melhoria estrutural e melhor proxy de fidelidade frente a E0 neste snapshot. A distribuição MPS aproximada de E3 deve ser tratada como inconclusiva quando diverge dos picos da amostra lógica; a execução ruidosa de 8 shots não permite estimar probabilidade de fatoração.",
            "",
            "Arquivos: `validacao_reduzida.json` e `validacao_logica_counts.csv`.",
        ]
    )
    md_path = outdir / "validacao_reduzida.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        f"Contagens lógicas: {shots_done}; período recuperado: {period}; fatores: {logical_result.get('factors')}",
        flush=True,
    )
    print(
        f"Fatoração verificada: {logical_result.get('factorization_valid')}", flush=True
    )
    print(f"Comparação E0/E3 gerada: {md_path}", flush=True)
    print(f"JSON detalhado: {json_path}", flush=True)
    print(
        "OBS.: nenhuma simulação Aer dos circuitos transpilados é reportada como concluída.",
        flush=True,
    )
    return 0 if logical_result.get("factorization_valid") else 2


if __name__ == "__main__":
    raise SystemExit(main())
