#!/usr/bin/env python3
"""Ponto de entrada compatível para a validação Aer compactada.

A implementação mantida está em validacao_aer_compacta_ruido.py. Ela oferece
os modos ideal e noisy; no modo noisy, usa um modelo simplificado de ruído
derivado do snapshot FakeAachen, documentado no JSON de saída.

Este arquivo permanece para preservar comandos e referências anteriores.
"""
from __future__ import annotations

from validacao_aer_compacta_ruido import main


if __name__ == "__main__":
    raise SystemExit(main())
