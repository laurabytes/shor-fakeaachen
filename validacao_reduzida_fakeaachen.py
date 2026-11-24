#!/usr/bin/env python3
"""Validação reduzida e reprodutível para o estudo Shor/FakeAachen.

Executa a simulação ideal do circuito lógico de busca de ordem usando a
implementação NumPy do projeto, recupera e verifica o período/fatores e
consolida as métricas já medidas dos circuitos transpilados E0 e E3.

IMPORTANTE: esta rotina NÃO simula os circuitos físicos transpilados E0/E3
no Aer. Essa execução foi tentada, mas interrompida devido ao custo do circuito
(156 fios físicos, >2 milhões de instruções). O relatório deixa essa limitação
explícita; não atribui contagens simuladas a E0/E3.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from math import gcd

N = 77
A = 30
DEFAULT_SHOTS = 1024
DEFAULT_SEED = 42
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
        return {"period_valid": False, "factorization_valid": False,
                "reason": "Não foi possível recuperar o período a partir das contagens."}
    period_ok = (period > 0 and pow(A, period, N) == 1)
    if not period_ok:
        return {"recovered_period": period, "period_valid": False,
                "factorization_valid": False,
                "reason": "O período recuperado não satisfaz a^r mod N = 1."}
    if period % 2:
        return {"recovered_period": period, "period_valid": True,
                "factorization_valid": False,
                "reason": "O período recuperado é ímpar; não permite a extração usual."}
    x = pow(A, period // 2, N)
    if x in (1, N - 1):
        return {"recovered_period": period, "period_valid": True,
                "x": x, "factorization_valid": False,
                "reason": "a^(r/2) mod N é 1 ou -1; a extração não produz fatores não triviais."}
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
        "log10_fidelity_proxy_independent_errors": float(row["log10_fidelity_proxy_independent_errors"]),
        "num_qubits_output": int(row.get("num_qubits_output") or 0),
        "unique_physical_qubits_used": int(row.get("unique_physical_qubits_used") or len(physical)),
        "physical_qubits_used": physical,
        "final_layout": final_layout,
        "native_gate_counts": gates,
        "native_gate_set_supported_by_snapshot": not unsupported,
        "unsupported_gate_names_vs_snapshot": unsupported,
        "explicit_swaps_after_translation": int(row.get("swap_count_after_translation") or 0),
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
    outdir = args.output or (project / "resultados_fakeaachen")
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "resultados.csv"
    snapshot_path = outdir / "backend_snapshot.json"

    # 1. Reproduz a validação ideal do circuito lógico de busca de ordem.
    # Esta simulação NumPy implementa a evolução lógica reduzida (registro de
    # contagem + registro alvo), não o circuito físico de 156 fios.
    try:
        from shor_quantum import simulate_order_finding
        from shor_classical import recover_order
    except Exception as exc:
        raise SystemExit(f"Não foi possível importar os módulos do projeto: {exc}")

    print(f"Simulação ideal do circuito lógico: N={N}, a={A}, shots={args.shots}, seed={args.seed}", flush=True)
    counts = simulate_order_finding(N, A, shots=args.shots, seed=args.seed)
    shots_done = sum(counts.values())
    period = recover_order(counts, N, A, 2 * (N - 1).bit_length())
    order_factor_check = validate_period_and_factors(period)
    logical_result = {
        "method": "simulação ideal NumPy do circuito lógico de busca de ordem (módulo shor_quantum.py)",
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

    # 2. Confere os resultados já medidos dos circuitos físicos transpilados.
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
            "status": "not_completed_manual_interrupt",
            "details": (
                "Aer iniciou a tentativa sobre E0 (156 fios físicos, 2.519.962 instruções), "
                "mas a execução foi interrompida manualmente com Ctrl+C antes da conclusão. "
                "A tentativa anterior também registrou a opção max_qubits inválida; essa opção "
                "foi retirada na versão seguinte. Nenhuma contagem Aer ideal/ruidosa de E0 ou E3 "
                "é reportada neste arquivo."
            ),
        },
        "interpretation": (
            "A evidência ideal diz respeito ao circuito lógico original. As métricas de E0 e E3 "
            "são resultados reais de transpilação, e a auditoria estrutural confere os dados "
            "registrados no CSV e as portas frente ao snapshot. Isso não substitui uma simulação "
            "de distribuição de medições dos circuitos transpilados."
        ),
    }

    json_path = outdir / "validacao_reduzida.json"
    json_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")

    counts_path = outdir / "validacao_logica_counts.csv"
    with counts_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["bitstring", "count"])
        for bitstring, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            writer.writerow([bitstring, count])

    md = [
        "# Validação reduzida — Shor / FakeAachen", "",
        "## 1. Circuito lógico original — simulação ideal", "",
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
        "## 2. Auditoria estrutural dos circuitos transpilados", "",
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
        "## 3. Limitação da simulação dos circuitos físicos", "",
        "A tentativa de Aer para E0 e E3 foi iniciada, mas a execução de E0 foi interrompida manualmente antes de produzir contagens. Uma tentativa anterior falhou por uma opção Aer inválida (`max_qubits`), que foi removida na versão posterior. Não há, portanto, resultados Aer ideal ou ruidoso para os circuitos transpilados.",
        "A simulação ideal do circuito lógico original foi concluída. A comparação E0/E3 nesta etapa utiliza métricas reais de transpilação e proxy independente de erros, não distribuição experimental de medições pós-transpilação.",
        "",
        "## 4. Conclusão da validação reduzida", "",
        "A simulação ideal lógica recupera um período válido e fatores não triviais quando a verificação passa. E3 apresenta melhoria estrutural e melhor proxy de fidelidade frente a E0 neste snapshot e nesta instância. A equivalência lógica formal dos circuitos transpilados não foi testada por simulação Aer nesta execução; a simulação ruidosa completa permanece pendente por limitação computacional.",
        "",
        "Arquivos: `validacao_reduzida.json` e `validacao_logica_counts.csv`.",
    ]
    md_path = outdir / "validacao_reduzida.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"Contagens lógicas: {shots_done}; período recuperado: {period}; fatores: {logical_result.get('factors')}", flush=True)
    print(f"Fatoração verificada: {logical_result.get('factorization_valid')}", flush=True)
    print(f"Comparação E0/E3 gerada: {md_path}", flush=True)
    print(f"JSON detalhado: {json_path}", flush=True)
    print("OBS.: nenhuma simulação Aer dos circuitos transpilados é reportada como concluída.", flush=True)
    return 0 if logical_result.get("factorization_valid") else 2


if __name__ == "__main__":
    raise SystemExit(main())
