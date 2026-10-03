# Catálogo de Abends e Runbooks — LifeCore-Mainframe

> **Como usar:** cada entrada tem (1) descrição do abend, (2) causas prováveis no contexto LifeCore, (3) diagnóstico passo a passo e (4) prevenção.

---

## S0C7 — Data Exception (Dado Numérico Inválido)

### O que é
Instrução decimal detectou dado não numérico em campo `COMP-3` (Packed Decimal). É o abend mais comum em COBOL batch.

### Causas no LifeCore
| Campo | Programa | Causa típica |
|---|---|---|
| `APO-CAPITAL-SEGURADO` | VGCCAP01 | Arquivo de entrada com campo monetário corrompido ou em branco |
| `FAT-VALOR-LIQUIDO` | FATURA01 | Registro de apólice com tamanho errado (LRECL errado) |
| `PAG-VALOR` | PAGTO01 | Arquivo de pagamento enviado com encoding diferente (ASCII vs EBCDIC) |

### Diagnóstico
1. Localize o `SYSOUT` do step com abend → anote offset do PSW.
2. No SDSF, comande `S` no job → vá em `SYSUDUMP` ou `SYSABEND`.
3. Identifique a instrução AP/SP/MP/CP no dump → mapeie com o `OFFSET` na listagem do compilador (`OFFSET` option).
4. Inspecione o conteúdo do campo em hex: se contiver `40` (espaço) ou `00` no nibble low, confirma COMP-3 inválido.
5. Rastreie o registro problemático: use `WS-CTR-LIDOS` no dump de memória para identificar o número do registro.

### Prevenção
- Use `ARQVAL01` antes de qualquer programa que leia campos COMP-3.
- Valide campos numéricos com `NUMERIC` class test antes de operar.
- Defina `E00005` no `CPYERRO` para quarentenar registros com COMP-3 corrompido.

### Injeção de Teste
Veja `TESTDATA/APOLICE_S0C7.DAT` — registro com `APO-CAPITAL-SEGURADO` preenchido com espaços.

---

## S0C4 — Protection Exception (Violação de Endereçamento)

### O que é
Programa tentou acessar endereço de memória inválido. Em COBOL, geralmente causado por subscrito fora dos limites de tabela, ponteiro nulo ou REDEFINES mal alinhado.

### Causas no LifeCore
| Situação | Programa |
|---|---|
| `WS-IDX` ultrapassando limite de `WS-FAIXA` (5 entradas) | VGCCAP01 |
| Cursor DB2 sem `FETCH` antes de referência ao host variable | FATURA01/CONCIL01 |
| `PERFORM VARYING` com tabela de tamanho errado | qualquer |

### Diagnóstico
1. Localize o PSW no dump → converta para endereço de instrução.
2. Compare com o mapa de storage do programa (seção `REGISTER SAVE AREA`).
3. Verifique a base register e displacement → identifique o campo.
4. Inspecione registradores GR4–GR15 no dump.

### Prevenção
- Sempre codifique `UNTIL WS-IDX > N` (não `>= N+1`) em `PERFORM VARYING`.
- Use `OCCURS ... DEPENDING ON` apenas com campo PIC S9 validado.

---

## S322 — CPU Time Limit Exceeded

### O que é
O job excedeu o limite de tempo de CPU definido no JCL (`TIME=`) ou no parâmetro de instalação.

### Causas no LifeCore
| Situação | Programa |
|---|---|
| Loop infinito em `PERFORM UNTIL WS-EOF` sem AT END funcionar | ARQVAL01 |
| Arquivo de entrada vazio → AT END nunca disparado | qualquer |
| Cursor DB2 aberto sem `CLOSE` → re-processamento infinito | CONCIL01 |

### Diagnóstico
1. No SDSF, veja `SYSOUT` → procure `IEA995I TIME LIMIT EXCEEDED`.
2. Veja o último `DISPLAY` emitido → identifica o ponto do programa.
3. Verifique contadores (`WS-CTR-LIDOS`) via dump para estimar onde travou.

### Prevenção
- Sempre teste AT END e defina `88 WS-EOF VALUE 'S'` antes do `PERFORM UNTIL`.
- Adicione `TIME=(,30)` no JCL de desenvolvimento para forçar falha rápida.

---

## S806 — Module Not Found

### O que é
O sistema não encontrou o módulo executável na `STEPLIB` ou `JOBLIB`.

### Causas no LifeCore
| Causa | Solução |
|---|---|
| Programa não compilado / link-editado | Executar `LCCMPL01` (script de compile) |
| `STEPLIB` apontando para loadlib errada | Corrigir HLQ em LCDIA01 |
| Nome do programa diferente do `PROGRAM-ID` | Conferir `PROGRAM-ID` x membro do PDS |

### Diagnóstico
1. `IEF450I LCDIA01 STEP030 - ABEND S806 U0000` no log.
2. Mensagem `IEA995I MODULE ARQVAL01 NOT FOUND IN LOAD LIBRARY`.
3. Use `ISPF 3.4` → listar `LIFECORE.LOAD` → confirmar membro.

### Prevenção
- O script [`SCRIPTS/compile.sh`](../SCRIPTS/compile.sh) compila e gera o executável antes de submeter o JCL.

---

## SQLCODE -904 — Resource Unavailable

### O que é
DB2 não conseguiu alocar um recurso necessário (tablespace, buffer pool, lock).

### Causas no LifeCore
| Causa | Situação |
|---|---|
| Tablespace em `STOPPED` ou `COPY PENDING` | Após recovery sem COPY |
| Buffer pool indisponível | Limite de memória atingido |

### Diagnóstico
1. Log DB2 (`-DISPLAY DATABASE`) → verifica status dos objetos.
2. Comandos: `-DISPLAY DATABASE(LCDB) SPACENAM(*) RESTRICT`.
3. Se `COPY PENDING`: executar `RUNSTATS` + `COPY` antes de reiniciar.

### Prevenção
- Monitorar tablespaces antes do ciclo batch (script de healthcheck).
- Capturar SQLCODE no COBOL e emitir `E00009` no log.

---

## SQLCODE -911 — Deadlock

### O que é
Duas transações aguardando lock uma da outra. DB2 escolhe uma como "vítima" e faz rollback.

### Causas no LifeCore
| Causa | Situação |
|---|---|
| FATURA01 e PAGTO01 rodando concorrentes na mesma linha | Jobs submetidos fora de ordem |
| Cursor sem `WITH UR` em leitura e outro job atualizando | Falta de isolation level |

### Diagnóstico
1. SQLCODE -911, SQLERRMC = `00C9008E` (deadlock) ou `00C9008F` (timeout).
2. Trace DB2 IFCID 172 (deadlock) e IFCID 196 (timeout).
3. Identificar tabela e row envolvida pelo trace.

### Prevenção
- `FATURA01` antes de `PAGTO01` — garantido pelo encadeamento `COND` do `LCDIA01`.
- Use `COMMIT` frequente (a cada 1000 linhas) para liberar locks.
- `SELECT ... WITH UR` em cursores de leitura pura.

---

## SQLCODE -913 — Timeout

### O que é
Lock wait excedeu o timeout configurado no DB2 (`IRLMRWT`).

### Causas no LifeCore
| Causa |
|---|
| Job interativo no TSO/ISPF com lock aberto e batch esperando |
| `COMMIT` com intervalo muito longo em CONCIL01 |

### Diagnóstico
1. Trace IFCID 196 → identifica o job "holder" do lock.
2. Trace IFCID 20 → activity log do lock.
3. `-DISPLAY THREAD(*)` → identifica connections abertas.

### Prevenção
- Emita `COMMIT` a cada 500 registros nos programas de UPDATE/INSERT.
- Em ambientes de desenvolvimento: `-IRLM TIMEOUT(30)`.

---

## Tabela Resumo

| Abend / SQLCODE | Causa raiz | RC esperado | Arquivo de teste |
|---|---|---|---|
| S0C7 | COMP-3 corrompido | 16 | `APOLICE_S0C7.DAT` |
| S0C4 | Subscrito fora dos limites | 16 | `APOLICE_S0C4.DAT` |
| S322 | Loop infinito / arquivo vazio | 16 | `APOLICE_VAZIO.DAT` |
| S806 | Módulo não encontrado | 16 | — |
| -904 | Recurso DB2 indisponível | 12 | — |
| -911 | Deadlock | 8 | — |
| -913 | Timeout de lock | 8 | — |
