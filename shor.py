"""demonstração das etapas do algoritmo de shor."""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field
from math import gcd

from resources import check_resources, memory_budget_mb

ETAPAS = {
    1: "entrada e validação de N",
    2: "pré-processamento clássico",
    3: "escolha da base e cálculo do mdc",
    4: "busca quântica da ordem",
    5: "recuperação e validação do período",
    6: "extração dos fatores",
}

SMALL_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97)


@dataclass
class FactorizationResult:
    N: int
    factors: tuple[int, int]
    method: str
    attempts: int = 0
    base: int | None = None
    period: int | None = None
    counts: dict[str, int] = field(default_factory=dict)
    execution_mode: str = "classical"
    steps: list[dict] = field(default_factory=list)


def validate_N(N: int) -> None:
    if isinstance(N, bool) or not isinstance(N, int) or N < 2:
        raise ValueError("N deve ser um inteiro maior ou igual a 2.")


def preprocess(N: int, use_quantum: bool = False):
    from classical import is_prime, perfect_power_factors

    validate_N(N)
    if N % 2 == 0:
        return (2, N // 2), "divisão por 2"
    if not use_quantum:
        for p in SMALL_PRIMES:
            if p < N and N % p == 0:
                return tuple(sorted((p, N // p))), "divisão por primo pequeno"
    if is_prime(N):
        raise ValueError(f"{N} é primo; não há fatoração não trivial.")
    factors = perfect_power_factors(N)
    if factors:
        return factors, "potência perfeita"
    return None, None


def choose_base(N: int, rng: random.Random, base: int | None = None) -> tuple[int, int]:
    a = base if base is not None else rng.randint(2, N - 1)
    return a, gcd(a, N)


def validate_period(N: int, a: int, period: int | None) -> int | None:
    if period is None or period <= 0 or period % 2 or pow(a, period, N) != 1:
        return None
    value = pow(a, period // 2, N)
    return None if value in (1, N - 1) else value


def extract_factors(N: int, value: int) -> tuple[int, int] | None:
    factors = tuple(sorted((gcd(value - 1, N), gcd(value + 1, N))))
    if factors[0] > 1 and factors[1] < N and factors[0] * factors[1] == N:
        return factors
    return None


def run_order_finding(
    N: int,
    a: int,
    *,
    mode: str,
    shots: int,
    seed: int | None,
    backend_name: str | None,
    fake_noise: bool,
    synthesis: str,
    show_circuit: bool,
    progress=None,
) -> dict[str, int]:
    if mode == "local":
        from quantum import simulate_order_finding

        return simulate_order_finding(N, a, shots=shots, seed=seed)

    from quantum import build_order_finding_circuit

    selected_synthesis = synthesis
    n = (N - 1).bit_length()
    if mode == "aer" and synthesis == "auto" and not (
        N == (1 << n) - 1 and a & (a - 1) == 0
    ):
        selected_synthesis = "dense"
    circuit = build_order_finding_circuit(N, a, synthesis=selected_synthesis)
    if show_circuit and progress:
        progress("circuito lógico:")
        progress(str(circuit.draw(output="text", fold=120)))

    try:
        if mode == "aer":
            from backends import run_aer

            return run_aer(circuit, shots=shots, seed=seed, progress=progress)
        from backends import run_fake

        return run_fake(
            circuit,
            shots=shots,
            seed=seed,
            backend_name=backend_name,
            noise=fake_noise,
            progress=progress,
        )
    except Exception as exc:
        raise RuntimeError(f"falha na execução {mode}: {exc}") from exc


def factor(
    N: int = 77,
    *,
    mode: str = "local",
    shots: int = 1024,
    max_attempts: int = 20,
    seed: int | None = None,
    quantum: bool = False,
    base: int | None = None,
    backend_name: str | None = None,
    progress=None,
    max_memory_mb: int | None = None,
    fake_noise: bool = True,
    show_circuit: bool = False,
    synthesis: str = "auto",
) -> FactorizationResult:
    validate_N(N)
    if mode not in {"local", "aer", "fake"}:
        raise ValueError("mode deve ser local, aer ou fake.")
    if synthesis not in {"auto", "dense", "permutation"}:
        raise ValueError("synthesis deve ser auto, dense ou permutation.")
    if isinstance(shots, bool) or not isinstance(shots, int) or shots < 1:
        raise ValueError("shots deve ser um inteiro positivo.")
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts deve ser um inteiro positivo.")
    if base is not None and (isinstance(base, bool) or not isinstance(base, int) or not 1 < base < N):
        raise ValueError("a base deve ser um inteiro com 1 < a < N.")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
        raise ValueError("seed deve ser um inteiro não negativo.")
    if not isinstance(fake_noise, bool):
        raise ValueError("fake_noise deve ser booleano.")

    budget = memory_budget_mb(max_memory_mb) if mode == "local" else None
    steps = []

    def record(stage: int, detail: str) -> None:
        steps.append({"stage": stage, "name": ETAPAS[stage], "detail": detail})
        if progress:
            progress(f"etapa {stage} — {ETAPAS[stage]}: {detail}")

    record(1, f"N={N}; executor={mode}.")
    factors, method = preprocess(N, use_quantum=quantum)
    if factors:
        record(2, f"fatores {factors[0]} × {factors[1]} por {method}.")
        return FactorizationResult(N, factors, method, steps=steps)
    record(2, "entrada composta; prosseguir para a busca da ordem.")

    rng = random.Random(seed)
    n = (N - 1).bit_length()
    from classical import recover_order

    for attempt in range(1, max_attempts + 1):
        a, divisor = choose_base(N, rng, base)
        record(3, f"tentativa {attempt}/{max_attempts}: a={a}; mdc(a,N)={divisor}.")
        if divisor > 1:
            factors = tuple(sorted((divisor, N // divisor)))
            return FactorizationResult(N, factors, "mdc clássico", attempt, a, steps=steps)
        if a == N - 1:
            if base is not None:
                raise ValueError("a base N−1 sempre produz raiz trivial; escolha outra.")
            continue

        check_resources(N, mode, budget)
        record(4, f"{3 * n} qubits ({2 * n} de contagem + {n} de alvo); {shots} shots.")
        sample_seed = rng.randrange(2**32)
        counts = run_order_finding(
            N, a, mode=mode, shots=shots, seed=sample_seed,
            backend_name=backend_name, fake_noise=fake_noise,
            synthesis=synthesis, show_circuit=show_circuit, progress=progress,
        )
        period = recover_order(counts, N, a, 2 * n)
        value = validate_period(N, a, period)
        if period is None:
            record(5, "não foi possível recuperar o período.")
        elif value is None:
            record(5, f"ordem candidata r={period}; raiz trivial ou período inválido.")
        else:
            record(5, f"ordem r={period}; a^r mod N={pow(a, period, N)}; x={value}.")

        if value is not None:
            factors = extract_factors(N, value)
            if factors:
                record(6, f"fatores {factors[0]} × {factors[1]} = {N}.")
                method = {
                    "local": "simulação lógica NumPy",
                    "aer": "AerSimulator ideal",
                    "fake": "FakeAachen + AerSimulator" + (" com ruído" if fake_noise else " sem ruído"),
                }[mode]
                return FactorizationResult(
                    N, factors, method, attempt, a, period, counts, mode, steps
                )

        if base is not None:
            raise RuntimeError(
                f"a base fixa {a} não permitiu extrair fatores; tente outra base ou mais shots."
            )

    raise RuntimeError(f"nenhum fator encontrado após {max_attempts} tentativa(s).")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("N", type=int, nargs="?", default=77)
    parser.add_argument("--mode", choices=("local", "aer", "fake"), default="local")
    parser.add_argument("--quantum", action="store_true", help="pula a divisão por primos pequenos")
    parser.add_argument("--base", type=int, help="fixa a base a")
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--max-attempts", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--backend", help="nome do backend fake; padrão: FakeAachen")
    parser.add_argument("--fake-ideal", action="store_true", help="desativa o ruído do FakeAachen")
    parser.add_argument("--max-memory-mb", type=int)
    parser.add_argument("--show-circuit", action="store_true")
    parser.add_argument("--synthesis", choices=("auto", "permutation", "dense"), default="auto")
    args = parser.parse_args(argv)

    try:
        if args.fake_ideal and args.mode != "fake":
            raise ValueError("--fake-ideal exige --mode fake.")
        result = factor(
            args.N, mode=args.mode, shots=args.shots,
            max_attempts=args.max_attempts, seed=args.seed,
            quantum=args.quantum, base=args.base,
            backend_name=args.backend, progress=print,
            max_memory_mb=args.max_memory_mb,
            fake_noise=not args.fake_ideal, show_circuit=args.show_circuit,
            synthesis=args.synthesis,
        )
        p, q = result.factors
        print(f"fatores encontrados: {p} × {q} = {result.N}")
        print(f"método: {result.method}")
        if result.period is not None:
            print(f"período validado: {result.period}; base: {result.base}")
        return 0
    except ImportError as exc:
        print(f"dependência ausente: {exc}. instale requirements.txt.", file=sys.stderr)
        return 2
    except MemoryError as exc:
        print(f"memória insuficiente: {exc}", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
