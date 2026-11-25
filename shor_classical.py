"""Rotinas clássicas auxiliares para a implementação de Shor fornecida."""
from __future__ import annotations
from fractions import Fraction
from math import gcd, lcm


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for p in small:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        s += 1
        d //= 2
    # Bases determinísticas para inteiros de 64 bits; acima disso são uma
    # bateria forte, mas probabilística.
    bases = (2, 325, 9375, 28178, 450775, 9780504, 1795265022) if n < 2**64 else small
    for a in bases:
        a %= n
        if a in (0, 1):
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _integer_nth_root(n: int, k: int) -> int:
    lo, hi = 0, 1 << ((n.bit_length() + k - 1) // k)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if mid**k <= n:
            lo = mid
        else:
            hi = mid
    return lo


def perfect_power_factors(n: int):
    if n < 4:
        return None
    for k in range(n.bit_length(), 1, -1):
        root = _integer_nth_root(n, k)
        if root > 1 and root**k == n:
            # Retorna uma decomposição não trivial em dois fatores.
            if k % 2 == 0:
                return root**(k // 2), root**(k // 2)
            return root, root**(k - 1)
    return None


def _measurement_integer(bitstring: str) -> int:
    # Qiskit pode separar registradores clássicos com espaços.
    return int(bitstring.replace(" ", ""), 2)


def recover_order(counts: dict[str, int], N: int, a: int, num_counting_qubits: int):
    """Tenta recuperar r por frações contínuas e combina divisores por MMC.

    Cada denominador isolado pode ser apenas um divisor da ordem. A rotina
    valida sempre pow(a, r, N) == 1 antes de devolver um candidato.
    """
    Q = 1 << num_counting_qubits
    candidates = []
    for bitstring, count in sorted(counts.items(), key=lambda item: item[1], reverse=True):
        y = _measurement_integer(bitstring)
        if y == 0:
            continue
        denominator = Fraction(y, Q).limit_denominator(N).denominator
        if denominator > 1 and denominator not in candidates:
            candidates.append(denominator)
        if denominator > 1:
            multiple = denominator
            while multiple <= N:
                if pow(a, multiple, N) == 1:
                    return multiple
                multiple += denominator
    combined = 1
    for denominator in candidates:
        combined = lcm(combined, denominator)
        if combined <= N and pow(a, combined, N) == 1:
            return combined
    # Procura múltiplos dos denominadores combinados, sem aceitar períodos
    # que não satisfaçam a congruência modular.
    for denominator in candidates:
        for k in range(1, max(2, N // denominator + 1)):
            candidate = denominator * k
            if candidate <= N and pow(a, candidate, N) == 1:
                return candidate
    return None
