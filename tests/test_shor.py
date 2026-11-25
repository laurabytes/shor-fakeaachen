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
            "otimizar",
            "validar",
            "validar_aer",
        )
        for name in modules:
            with self.subTest(module=name):
                importlib.import_module(name)

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
