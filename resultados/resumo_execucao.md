# resumo da execução

- backend: fake_aachen
- qubits físicos: 156
- instância: N=77, a=30
- seed do transpiler: 42

| experimento | status | profundidade | operações | operações 2q | tempo (s) | log10(proxy) |
|---|---:|---:|---:|---:|---:|---:|
| E5_dense_basic | skipped | — | — | — | — | — |
| E0_reference_L1_auto | ok | 1765950 | 2519962 | 602131 | 4.22 | -444.635 |
| E1_L0_auto | ok | 2992515 | 5280381 | 1271527 | 3.28 | -1724.125 |
| E2_L2_auto | ok | 1437404 | 2171877 | 544979 | 8.31 | -488.067 |
| E3_L3_auto | ok | 1412349 | 2117589 | 531587 | 11.19 | -426.295 |
| E4_sabre_sabre | ok | 1765950 | 2519962 | 602131 | 3.97 | -5296.343 |
| E6_manual_low_error | ok | 1866105 | 2667170 | 649873 | 3.99 | -631.359 |
| E7_manual_low_error_reversed | ok | 1866198 | 2758427 | 682258 | 4.77 | -828.172 |
| E8_manual_center | ok | 1876816 | 2644351 | 638926 | 4.41 | -1701.664 |

os dados completos estão em `resultados.csv`.
a análise e as limitações estão em `../relatorio.md`.
E5 permanece registrado como pulado porque não produziu métricas.
