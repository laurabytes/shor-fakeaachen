# Organização do código

- `shor_original.py`: versão de referência preservada a partir do código-fonte reunido anteriormente; os módulos `shor_*.py` mantêm compatibilidade com os auxiliares deste projeto.
- `shor.py` e `quantum.py`: fluxo de execução e circuito lógico utilizados no projeto.
- `classical.py`, `backends.py` e `resources.py`: pós-processamento, simuladores e estimativa de recursos.
- `shor_otimizado.py`: entrada principal dos experimentos; chama `otimizar.py`.
- `backend.py`, `metricas.py` e `graficos.py`: caracterização, métricas e gráficos.
- `validar.py`, `validar_aer.py` e `ruido.py`: validação lógica, simulação MPS e modelo aproximado de ruído.

A instância de comparação permanece N=77 e a=30. Os resultados já registrados não foram recalculados durante esta reorganização.
