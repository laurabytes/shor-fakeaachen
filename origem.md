# origem dos arquivos

- `quantum.py`: circuito lógico derivado do código-base fornecido na disciplina. A implementação matemática foi preservada.
- `shor.py`: organiza as etapas didáticas da fatoração e conecta o circuito aos simuladores.
- `classical.py`, `backends.py` e `resources.py`: funções auxiliares de pós-processamento, execução e memória.
- `backend.py`, `metricas.py` e `graficos.py`: análise do snapshot, métricas de transpilação e visualização.
- `otimizar.py`: compara os níveis de otimização, layouts e roteamentos.
- `validar.py`, `ruido.py` e `validar_aer.py`: validação lógica, modelo de ruído e simulação MPS compactada.

## instância

O estudo usa N=77 e a=30. A mesma instância matemática e o mesmo circuito lógico são mantidos entre as configurações de transpilação. Na seleção inicial com seed 42, a base 16 produziu ordem 15, que não permitiu extrair fatores. A base 30 produziu ordem 30 e os fatores 7 e 11.

Os resultados já registrados não foram recalculados durante a reorganização dos arquivos.
