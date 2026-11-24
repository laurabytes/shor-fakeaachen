# Otimização da Transpilação do Algoritmo de Shor em FakeAachen

**Aluna:** [preencher]  
**Disciplina:** Computação Quântica Aplicada à Defesa Cibernética  
**Professor:** Anderson Fernandes Pereira dos Santos  
**Equipamento:** FakeAachen — família Heron r3 (156 qubits na classe FakeProvider)

> Modelo de relatório. Preencher com os arquivos de resultados gerados pelo script antes de converter para PDF. Não submeter sem resultados efetivamente executados.

## Resumo
[Após a execução, resumir objetivo, configurações, principal resultado e limitação.]

## 1. Introdução e objetivo
A avaliação investiga estratégias de transpilação para preservar o circuito lógico de Shor e adaptar sua implementação à topologia, às portas suportadas e às propriedades operacionais do FakeAachen. A comparação deve considerar profundidade, portas totais, operações de dois qubits, roteamento, mapeamento físico e indicadores baseados no snapshot.

## 2. Caracterização do equipamento
Inserir `backend_snapshot.json`, a tabela `calibracao_qubits.csv` e a figura `topologia_fakeaachen.png`. A classe FakeAachen representa um backend simulado de 156 qubits. Os dados do FakeProvider são snapshots históricos e não calibração de QPU em tempo real.

## 3. Circuito de referência
Instância fixa: N=77, a=30, 7 qubits de alvo e 14 qubits de contagem, totalizando 21 qubits lógicos. A base a=30 decorre da execução reprodutível do seletor do código-base com seed=42: a primeira tentativa a=16 apresenta ordem ímpar (15), e a segunda a=30 apresenta ordem 30. Verificação: 30^15 mod 77 = 43, gcd(43−1,77)=7 e gcd(43+1,77)=11. Confirmar os fatores: 7 × 11 = 77.

A referência usa obrigatoriamente `optimization_level=1` e não define `initial_layout` manual. Registrar versões e seed a partir de `versions.json`.

## 4. Metodologia experimental
[Descrever construção única do circuito, os mesmos N/a em todos os testes e os oito experimentos E1–E8. Inserir a tabela de `resultados.csv`; manter linhas com status de erro e explicar sua causa.]

## 5. Resultados
Inserir a tabela de `resultados.csv` e os gráficos de profundidade, operações totais, operações 2Q, tempo de transpilação e proxy de fidelidade.

| ID | Configuração | Profundidade | Operações | Operações 2Q | SWAPs finais | Tempo (s) | Proxy |
|---|---|---:|---:|---:|---:|---:|---:|
| E0 | Referência L1 automática | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| E1 | L0 automático | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| E2 | L2 automático | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| E3 | L3 automático | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| E4 | SABRE/SABRE | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| E5 | DENSE/BASIC | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| E6 | Subgrafo de menor custo, layout manual | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| E7 | Mesmo subconjunto, mapeamento invertido | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| E8 | Subgrafo central BFS, layout manual | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

A proxy multiplicativa de fidelidade é definida por \(F_{proxy}=\prod_i(1-e_i)\), apenas para instruções com erro disponível no target. Ela supõe independência e não deve ser chamada de probabilidade exata de fatoração correta.

## 6. Validação
[Se `--validate` tiver sido executado com sucesso, inserir distribuição ideal e com ruído do FakeAachen, shots e resultados do pós-processamento. Se não tiver sido possível, declarar a limitação e anexar o log.]

## 7. Análise crítica — respostas obrigatórias

### Questão 1 — Como a topologia influenciou a implementação?
[Relacionar conexões disponíveis, mapeamento, operações 2Q e eventuais operações de roteamento com os dados do experimento.]

### Questão 2 — O layout manual superou o automático?
[Comparar E6/E7/E8 com E0 usando resultados, sem pressupor que sim.]

### Questão 3 — Menor profundidade também significou melhor proxy de fidelidade?
[Comparar as duas métricas; explicar trade-offs.]

### Questão 4 — Qual foi o impacto das operações 2Q e do roteamento?
[Usar número de gates 2Q, SWAPs explícitos e distribuição de portas nativas. Lembrar que SWAP pode ser decomposto antes da contagem final.]

### Questão 5 — Qual estratégia é recomendada para FakeAachen?
[Recomendar a configuração sustentada pelos indicadores e justificar eventuais compromissos.]

### Questão 6 — Quais características do equipamento foram determinantes? As conclusões generalizam?
[Discutir 156 qubits, topologia, portas nativas e heterogeneidade das calibrações. Limitar a conclusão ao snapshot FakeAachen e à instância estudada.]

## 8. Limitações
- FakeProvider é um modelo simulado baseado em snapshot, não QPU física.
- O circuito-base é pequeno e utiliza uma síntese didática de aritmética modular por permutações; os resultados não são recursos de Shor escalável para RSA real.
- Proxy de fidelidade simplifica erros e não inclui correlações nem todos os efeitos físicos.
- Resultados podem variar conforme versões de Qiskit e seed; todas devem ser documentadas.

## 9. Conclusão
[Indicar a estratégia recomendada, ganhos/perdas sobre E0, evidências, limitações e trabalhos futuros.]

## Apêndice — Reprodutibilidade
Anexar `README.md`, `requirements.txt`, `shor_original.py`, `shor_quantum.py`, `shor_otimizado.py`, `resultados.csv`, `versions.json` e os artefatos gerados.
