"""Pós-processamento e pré-processamento clássicos para a demonstração de Shor.

Não calcula a ordem por varredura de expoentes. A recuperação usa somente
denominadores observados, seus MMC e testes de exponenciação modular.

Referências:
https://learning.quantum.ibm.com/course/fundamentals-of-quantum-algorithms/phase-estimation-and-factoring
https://miller-rabin.appspot.com/ (bases determinísticas de Jim Sinclair)
"""

from __future__ import annotations

from collections.abc import Mapping
from math import gcd, isqrt, lcm
from operator import index
from secrets import randbelow

_TRIAL_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
_MR_BASES_64 = (2, 325, 9375, 28178, 450775, 9780504, 1795265022)
_PROBABLE_PRIME_ROUNDS = 32
_MAX_ORDER_HYPOTHESES = 256
_ORDER_TRIAL_LIMIT = 10_000


def _integer(value, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} deve ser um inteiro, sem booleanos.")
    try:
        return index(value)
    except TypeError as exc:
        raise ValueError(f"{name} deve ser um inteiro.") from exc


def _passes_miller_rabin(N: int, base: int, odd_part: int, twos: int) -> bool:
    base %= N
    if base in (0, 1):
        return True
    value = pow(base, odd_part, N)
    if value in (1, N - 1):
        return True
    for _ in range(twos - 1):
        value = value * value % N
        if value == N - 1:
            return True
    return False


def is_prime(N: int) -> bool:
    """Testa primalidade sem divisão até sqrt(N).

    O resultado é determinístico para N < 2**64. Acima disso, True significa
    provavelmente primo: 32 bases independentes uniformes de Miller–Rabin
    dão probabilidade de falso positivo no máximo 4**-32 por composto.
    False sempre certifica que N não é primo. Inteiros menores que 2 são
    aceitos e retornam False; tipos não inteiros e booleanos são rejeitados.
    A aleatoriedade acima de 64 bits independe da semente do simulador.
    """
    N = _integer(N, "N")
    if N < 2:
        return False
    for prime in _TRIAL_PRIMES:
        if N % prime == 0:
            return N == prime
    odd_part = N - 1
    twos = 0
    while odd_part % 2 == 0:
        odd_part //= 2
        twos += 1
    bases = (
        _MR_BASES_64
        if N < 1 << 64
        else (randbelow(N - 3) + 2 for _ in range(_PROBABLE_PRIME_ROUNDS))
    )
    return all(_passes_miller_rabin(N, base, odd_part, twos) for base in bases)


def _integer_root(N: int, exponent: int) -> int:
    """Piso da raiz inteira por busca binária, sem aproximação em float."""
    low = 1
    high = 1 << ((N.bit_length() + exponent - 1) // exponent)
    while low + 1 < high:
        middle = (low + high) // 2
        if pow(middle, exponent) <= N:
            low = middle
        else:
            high = middle
    return low


def perfect_power_factors(N: int) -> tuple[int, int] | None:
    """Encontra fatores de uma potência perfeita usando raízes inteiras.

    Examina O(log N) expoentes; cada raiz usa busca binária. Não percorre
    possíveis bases até sqrt(N). Os fatores retornados podem ser compostos.
    """
    N = _integer(N, "N")
    if N < 2:
        raise ValueError("N deve ser pelo menos 2.")
    square_root = isqrt(N)
    if square_root * square_root == N:
        return square_root, square_root
    # Todo expoente par já foi coberto pelo teste de quadrado perfeito.
    for exponent in range(3, N.bit_length(), 2):
        base = _integer_root(N, exponent)
        if pow(base, exponent) == N:
            return base, N // base
    return None


def _measurement_denominators(value: int, dimension: int, N: int) -> tuple[int, ...]:
    """Convergentes com q<N a no máximo um intervalo de medição da fase."""
    numerator, denominator = value, dimension
    previous_p, p = 0, 1
    previous_q, q = 1, 0
    candidates = []
    while denominator:
        quotient, remainder = divmod(numerator, denominator)
        previous_p, p = p, quotient * p + previous_p
        previous_q, q = q, quotient * q + previous_q
        if q >= N:
            break
        # |value/dimension - p/q| <= 1/dimension, inteiramente exato.
        if q > 1 and abs(value * q - p * dimension) <= q:
            candidates.append(q)
        numerator, denominator = denominator, remainder
    return tuple(candidates)


def _order_prime_factors(candidate: int) -> tuple[int, ...] | None:
    """Fatora candidatos modestos com trabalho limitado e resultado exato.

    Um cofator primo menor que 2**64 é certificado por Miller–Rabin
    determinístico. Cofatores compostos resistentes à divisão por fatores
    até 10.000, ou primos maiores sem certificado, retornam None. Isso evita
    afirmar ordem mínima a partir de uma fatoração incompleta ou provável.
    """
    remaining = candidate
    factors = []
    if remaining < 1 << 64 and is_prime(remaining):
        return (remaining,)
    divisor = 2
    while divisor * divisor <= remaining and divisor <= _ORDER_TRIAL_LIMIT:
        if remaining % divisor == 0:
            factors.append(divisor)
            while remaining % divisor == 0:
                remaining //= divisor
            if remaining < 1 << 64 and is_prime(remaining):
                factors.append(remaining)
                return tuple(factors)
        divisor = 3 if divisor == 2 else divisor + 2
    if remaining > 1:
        if divisor * divisor > remaining or (remaining < 1 << 64 and is_prime(remaining)):
            factors.append(remaining)
        else:
            return None
    return tuple(factors)


def _minimal_order(candidate: int, N: int, a: int) -> int | None:
    if pow(a, candidate, N) != 1:
        return None
    prime_factors = _order_prime_factors(candidate)
    if prime_factors is None:
        return None
    for prime in prime_factors:
        while candidate % prime == 0 and pow(a, candidate // prime, N) == 1:
            candidate //= prime
    return candidate


def recover_order(counts, N: int, a: int, num_counting_qubits: int) -> int | None:
    """Recupera uma ordem mínima certificada, ou None por dados insuficientes.

    Aceita contagens inteiras não negativas, indexadas por strings binárias
    com exatamente num_counting_qubits caracteres. Valida o histograma
    completo antes da recuperação, inclusive entradas de frequência zero.

    Usa convergentes de cada fase a até um intervalo de medição (1/2**m),
    e combina denominadores de medições distintas por MMC. Todas as ordens
    candidatas satisfazem r<N e só são aceitas após pow(a,r,N)==1. Não tenta
    multiplicadores arbitrários: uma única fase 1/2 nunca inventa r=4.

    Para tolerar dados ruidosos sem busca combinatória ilimitada, mantém até
    256 hipóteses, priorizando a frequência das observações compatíveis.
    Essa poda pode descartar evidência útil em histogramas muito ruidosos.
    A redução à ordem mínima exige fatoração exata e barata do candidato;
    se ela não for possível, esse candidato é descartado, nunca reportado
    incorretamente como mínimo. Veja _order_prime_factors para o limite.
    """
    N = _integer(N, "N")
    a = _integer(a, "a")
    num_counting_qubits = _integer(num_counting_qubits, "num_counting_qubits")
    if N < 3 or not 1 < a < N or gcd(a, N) != 1:
        raise ValueError("Exige N >= 3, 1 < a < N e base coprima de N.")
    if num_counting_qubits < 1:
        raise ValueError("O número de bits de contagem deve ser positivo.")
    if not isinstance(counts, Mapping):
        raise ValueError("counts deve mapear strings binárias para contagens inteiras.")
    observations = []
    for measurement, count in counts.items():
        if (
            not isinstance(measurement, str)
            or len(measurement) != num_counting_qubits
            or any(bit not in "01" for bit in measurement)
        ):
            raise ValueError("Cada medição deve ser binária e ter a largura do registrador.")
        count = _integer(count, "contagem")
        if count < 0:
            raise ValueError("As contagens devem ser não negativas.")
        value = int(measurement, 2)
        if count and value:
            observations.append((value, count))

    dimension = 1 << num_counting_qubits
    hypotheses: dict[int, int] = {}
    checked: set[int] = set()
    for value, count in sorted(observations, key=lambda item: (-item[1], item[0])):
        denominators = _measurement_denominators(value, dimension, N)
        updated = hypotheses.copy()
        for denominator in denominators:
            # Alternativas da mesma medição não são combinadas entre si.
            additions = [(denominator, count)]
            additions.extend((lcm(candidate, denominator), score + count)
                             for candidate, score in hypotheses.items())
            for candidate, score in additions:
                if candidate >= N:
                    continue
                if candidate not in checked:
                    checked.add(candidate)
                    order = _minimal_order(candidate, N, a)
                    if order is not None:
                        return order
                updated[candidate] = max(updated.get(candidate, 0), score)
        hypotheses = dict(sorted(updated.items(), key=lambda item: (-item[1], item[0]))
                          [:_MAX_ORDER_HYPOTHESES])
    return None