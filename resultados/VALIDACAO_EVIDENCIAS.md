# Auditoria das evidências de validação

## Estado dos artefatos versionados

| Etapa | Arquivo | Estado comprovado | Interpretação permitida |
|---|---|---|---|
| Lógica ideal | `resultados/validacao_counts.json` | 1.024 shots; r=30; fatores 7 e 11 | Valida o fluxo lógico ideal, não o circuito transpilado |
| E3 MPS ideal, 1.024 shots | `E3_ideal_mps_bond16_shots1024_counts.csv` | 975 bitstrings; soma=1.024; máximo=3 | Distribuição disponível, mas sem JSON pareado para auditar metadados |
| E3 MPS ideal, 8 shots | `E3_ideal_mps_bond16_shots8.json` | concluído; 8 resultados distintos; sem período/fatores | Execução curta separada, exploratória |
| E3 MPS ruidoso, 8 shots | `E3_noisy_mps_bond16_shots8.json` | interrompido; nenhuma contagem | Não existe resultado ruidoso válido |
| Aer E0/E3 | `resultados/validacao_counts.json` | erro `Invalid option max_qubits` em ambos | Não houve comparação Aer dos circuitos transpilados |

## Auditoria estrutural do CSV MPS 1.024

- Linhas de resultados distintas: 975.
- Soma das frequências: 1.024.
- Frequência máxima: 3.
- JSON de execução pareado: não localizado no repositório.
- Consequência: não atribuir ao CSV, isoladamente, metadados de execução, tempo, versão, parâmetros MPS ou pós-processamento que não estejam nele.

O relatório anterior registra recuperação de período 30 e fatores 7 e 11 no pós-processamento da amostra de 1.024 shots. Como o JSON correspondente não está versionado, esse registro é mantido como anotação do resumo de validação, mas não é apresentado como totalmente reproduzível a partir dos artefatos atuais.

## Separação obrigatória das conclusões

1. **Equivalência/validação lógica:** a simulação ideal lógica recupera r=30 e (7,11).
2. **Circuito transpilado E3 ideal:** há CSV de 1.024 shots, porém sem metadados pareados; a amostra é dispersa e a validação permanece limitada.
3. **Circuito transpilado sob ruído:** não validado; a execução foi interrompida.
4. **Comparação E0 versus E3 por Aer:** não realizada com sucesso; o JSON registra erro de opção.

Não afirmar sucesso de fatoração sob ruído, equivalência estatística entre E0 e E3, nem execução em QPU física.

## Backend e família de processadores

- Qiskit documenta `FakeAachen` como backend fake de 156 qubits.
- A classe pública não declara diretamente a família/revisão do processador.
- A IBM informou em março de 2026 que o QPU real `ibm_aachen` foi atualizado para Heron r3.
- Formulação adotada: resultados medidos no snapshot `FakeAachen` de 156 qubits; Heron r3 é contexto do QPU real `ibm_aachen`, não uma propriedade diretamente verificada no objeto fake.

## Experimentos

E0 é a referência. E1, E2, E3, E4, E6, E7 e E8 são sete experimentos adicionais concluídos, atendendo ao mínimo de seis. E5 permanece na tabela como pulado, sem métricas inventadas.
