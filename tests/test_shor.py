"""testes rápidos do fluxo lógico de shor."""

import importlib
import unittest

from shor import factor


class TestShorLocal(unittest.TestCase):
    def test_modulos_importaveis(self):
        modules = (
            "shor",
            "quantum",
            "classical",
            "backends",
            "resources",
            "backend",
            "metricas",
            "graficos",
            "ruido",
            "otimizar",
            "validar",
            "validar_aer",
        )
        for name in modules:
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_rejeita_numeros_primos(self):
        for number in (2, 13):
            with self.subTest(number=number):
                with self.assertRaises(ValueError):
                    factor(number, mode="local")

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
