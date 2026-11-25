"""testes rápidos do fluxo lógico de shor."""

import unittest

from shor import factor


class TestShorLocal(unittest.TestCase):
    def test_fatora_77_com_base_30(self):
        result = factor(
            77,
            mode="local",
            shots=1024,
            max_attempts=1,
            seed=42,
            quantum=True,
            base=30,
        )
        self.assertEqual(result.period, 30)
        self.assertEqual(result.factors, (7, 11))


if __name__ == "__main__":
    unittest.main()
