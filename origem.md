# origem dos arquivos

- `shor.py` e `quantum.py`: derivados dos blocos de código fornecidos no material da disciplina. a estrutura das etapas e a implementação lógica foram preservadas; ajustes pontuais de importação e documentação foram realizados.
- `classical.py`, `backends.py` e `resources.py`: módulos auxiliares criados para apoiar o pós-processamento, os executores de simulação e as verificações de recursos. não são apresentados como arquivos originais do professor.
- `otimizar.py`: script desenvolvido para caracterizar o FakeAachen e comparar níveis de otimização, métodos de layout e roteamento.
- `validar.py` e `validar_aer.py`: scripts de validação e auditoria associados aos resultados experimentais.

## instância usada

o estudo foi fixado em N=77 e a=30. na execução de seleção com seed 42, a base 16 produziu ordem 15, que não permitiu extrair fatores. a base 30 produziu ordem 30 e os fatores 7 e 11. por isso, a mesma base válida foi usada em todas as comparações de transpilação.

as alterações de organização e nome dos arquivos não têm o objetivo de modificar o circuito lógico do material-base.
