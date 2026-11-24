# Avaliação individual — Shor em FakeAachen

## Estado desta pasta

Esta é uma **base executável de investigação**, preparada para produzir os resultados locais da transpilação em FakeAachen. O ambiente usado para preparar esta pasta não tinha `qiskit`, `qiskit-aer` ou `qiskit-ibm-runtime` instalados, e não foi possível instalá-los por falta de acesso ao PyPI. Portanto, **não há métricas de transpilação preenchidas nem resultados inventados**. As tabelas, gráficos e relatório com números serão gerados quando o script for executado em um ambiente com as dependências instaladas.

O código lógico `shor_original.py` e o módulo de circuito `shor_quantum.py` foram extraídos dos dois blocos Markdown de código fornecidos na conversa. Foram preservados como arquivos-fonte. Os módulos `shor_classical.py`, `shor_resources.py` e `shor_backends.py` são auxiliares de compatibilidade incluídos para tornar os imports do código-base resolvíveis; confira-os com os arquivos originais entregues pelo professor caso ele disponibilize versões separadas.

## Equipamento-alvo

- Backend: `FakeAachen` (`qiskit_ibm_runtime.fake_provider`).
- Classe FakeProvider: backend de 156 qubits.
- Sistema correspondente na documentação atual da IBM: `ibm_aachen`, família Heron r3. O FakeProvider usa um **snapshot estático**; não deve ser descrito como calibração ao vivo nem como execução em QPU física.

## Instância fixa

- Módulo: `N=77` (mesma instância padrão da implementação-base).
- Base: `a=30`.
- Justificativa da base: com `seed=42`, a rotina de seleção do código-base testa `a=16` primeiro (ordem 15, ímpar) e depois `a=30` (ordem 30). A segunda tentativa é válida para extrair fatores: `30^15 mod 77 = 43`, `gcd(43-1,77)=7` e `gcd(43+1,77)=11`.
- Qubits lógicos: `n=ceil(log2(77))=7`; registrador de contagem com `2n=14`, alvo com `n=7`, total de 21.

O circuito é construído uma única vez com `build_order_finding_circuit(77, 30, synthesis="auto")` e reutilizado em todos os experimentos. A lógica não é alterada entre as configurações.

## Instalação recomendada

Use Python 3.11 em ambiente virtual (recomendado para reduzir incompatibilidades entre dependências científicas):

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

No Windows, ative com `.venv\\Scripts\\activate`.

## Teste local do código-base (não é FakeAachen)

Foi executado neste ambiente o circuito lógico no modo local NumPy para verificar a instância e o pós-processamento clássico:

```bash
python shor_original.py 77 --mode local --quantum --base 30 --seed 42 --shots 1024 --save-json evidencia_local_N77_a30.json
```

A execução recuperou o período 30 e os fatores 7 e 11. Esse teste valida o fluxo lógico local; **não** é uma transpilação nem uma execução no FakeAachen. O log e o JSON estão incluídos como evidência separada.

## Execução dos experimentos FakeAachen

Na pasta do projeto:

```bash
python shor_otimizado.py
```

O script irá:

1. Instanciar exclusivamente `FakeAachen`.
2. Extrair topologia, operações disponíveis, erros de porta, readout e T1/T2 quando o snapshot os disponibilizar.
3. Construir duas regiões conectadas para os testes de layout manual.
4. Transpilar a mesma instância nos nove cenários (uma referência + oito experimentos adicionais).
5. Gerar `resultados_fakeaachen/resultados.csv`, JSONs, circuitos QPY/texto, diagrama de conectividade e gráficos.
6. Gerar `relatorio_resultados.md` com a tabela consolidada e roteiro para responder às questões.

Para tentar também a validação ideal/noisy (pode ser muito pesada para esse circuito):

```bash
python shor_otimizado.py --validate --shots 4096
```

Não use os resultados de validação se o script registrar um erro. Guarde o log completo e os arquivos gerados.

## Experimentos

| ID | Configuração | Eixo investigado |
|---|---|---|
| E0 | `optimization_level=1`, layout automático, sem `initial_layout` | Referência obrigatória |
| E1 | `optimization_level=0`, layout automático | Nível de otimização |
| E2 | `optimization_level=2`, layout automático | Nível de otimização |
| E3 | `optimization_level=3`, layout automático | Nível de otimização |
| E4 | layout SABRE + roteamento SABRE, nível 1 | Estratégia de layout/roteamento |
| E5 | layout DENSE + roteamento BASIC, nível 1 | Estratégia de layout/roteamento |
| E6 | `initial_layout` manual em subgrafo conectado de menor custo de calibração | Seleção de qubits e mapeamento |
| E7 | Mesmo subconjunto de E6, ordem lógica-física invertida | Efeito do mapeamento |
| E8 | `initial_layout` manual em subgrafo BFS próximo ao centro dos índices físicos | Região/topologia |

E0 atende à referência pedida no enunciado; E1–E8 são oito configurações adicionais. O script mantém todos os registros, inclusive falhas de compilação, sem esconder resultados ruins.

## Métricas coletadas

- Profundidade e operações totais.
- Número de operações de dois qubits.
- SWAP explícitos remanescentes após tradução (muitas vezes zero, pois o roteamento pode decompô-los em portas nativas).
- Contagens por tipo de porta nativa.
- Mapeamentos inicial e final, quando expostos pelo Qiskit.
- Qubits físicos efetivamente usados.
- Tempo de transpilação.
- Erros médios de 1Q, 2Q e medição para operações com calibração disponível.
- Proxy multiplicativo de fidelidade por produto dos termos `(1 - erro)`.

**Limitação importante da proxy:** ela supõe erros independentes por instrução e não representa exatamente a probabilidade de fatoração correta. Não modela integralmente correlações, crosstalk, leakage, drift, erros coerentes ou agendamento temporal. Deve ser tratada como indicador comparativo aproximado, conforme a exigência do enunciado.

## Entregáveis após execução

O diretório `resultados_fakeaachen/` terá:

- `resultados.csv` — dados quantitativos de cada configuração.
- `backend_snapshot.json`, `calibracao_qubits.csv` e `calibracao_arestas.csv` — caracterização do FakeAachen.
- `topologia_fakeaachen.png` — diagrama de conectividade com as regiões candidatas.
- `regioes_qubits.json` — listas de qubits escolhidas.
- `circuito_logico.qpy/.txt`, `circuito_referencia.qpy/.txt`, `circuito_recomendado.qpy/.txt`.
- `profundidade.png`, `operacoes_totais.png`, `operacoes_2q.png`, `tempo_transpilacao.png`, `fidelidade_proxy.png` (este último apenas quando houver dados de erro disponíveis).
- `relatorio_resultados.md` — síntese automática para revisão.
- `versions.json` — versões reais do ambiente executado.

O `relatorio_modelo.md` contém estrutura para o relatório final. Converta-o para PDF **somente depois** de preencher e revisar os resultados que o script gerar.

## Atenção à reprodução

- Não altere `N=77` nem `a=30` entre experimentos.
- Não altere `shor_original.py` ou `shor_quantum.py` na investigação; as mudanças devem ficar em `shor_otimizado.py`.
- Registre sistema operacional e versões (`versions.json`).
- O seed do transpiler é fixado em 42. A mesma seed e os mesmos parâmetros devem ser usados nas comparações.
- Se o transpile de nível 3 ou a validação ficar sem recursos, registre a falha; não invente valores nem remova o experimento da tabela.
