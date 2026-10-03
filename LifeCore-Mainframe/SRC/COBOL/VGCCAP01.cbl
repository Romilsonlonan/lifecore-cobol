      *================================================================*
      * PROGRAMA  : VGCCAP01                                          *
      * DESCRICAO : Calculo de Capital Segurado                       *
      *                                                               *
      *   Tipo F — Fixo        : capital ja definido na apolice       *
      *   Tipo E — Escalonado  : capital atualizado por IPCA          *
      *                          Capital = Base * (1 + IPCA/100)^Anos *
      *   Tipo M — Mult.Salarial: capital = salario * multiplicador   *
      *   Tipo B — Por Faixa   : calculo PROGRESSIVO por faixa        *
      *                          (cada faixa tem seu fator — igual    *
      *                           ao INSS progressivo, nao salta)     *
      *   Tipo P — Parametrico : capital = salario * fator            *
      *                                                               *
      * NOTA IPCA: o indice IPCA (Indice Nacional de Precos ao        *
      *   Consumidor Amplo) e o indexador oficial de seguros no       *
      *   Brasil (SUSEP). Usado para reajuste anual de capital e      *
      *   premio nas apolices de vida em grupo (VGC/GLB).             *
      *   Fonte: IBGE. Parametrizado via WS-IPCA-ANUAL.               *
      *                                                               *
      * SUBPROGRAMA: chama CALCCAP para calculos complexos            *
      * PROJETO   : LifeCore-Mainframe                                *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. VGCCAP01.
       AUTHOR.     LIFECORE-TEAM.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ARQ-APOLICE
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.APOLICE'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-APOLICE.
           SELECT ARQ-CAPITAL
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.CAPITAL'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-CAPITAL.

       DATA DIVISION.
       FILE SECTION.
       FD  ARQ-APOLICE RECORD CONTAINS 300 CHARACTERS.
       01  FS-APOLICE                    PIC X(300).
       FD  ARQ-CAPITAL RECORD CONTAINS 300 CHARACTERS.
       01  FS-CAPITAL                    PIC X(300).

       WORKING-STORAGE SECTION.
       01  WS-FS-APOLICE                 PIC X(02).
       01  WS-FS-CAPITAL                 PIC X(02).
       01  WS-FIM                        PIC X(01) VALUE 'N'.
           88  WS-EOF                    VALUE 'S'.

      *----------------------------------------------------------------*
      * Tabela de faixas salariais para calculo PROGRESSIVO (tipo B)   *
      * Cada faixa tem limite superior e fator multiplicador.           *
      * O calculo e progressivo: cada faixa acumula apenas o           *
      * excedente da faixa anterior (igual ao INSS progressivo).       *
      * Parametros normalmente carregados de tabela DB2/parm.          *
      *----------------------------------------------------------------*
       01  WS-FAIXAS-CAPITAL.
           05  WS-FAIXA OCCURS 5 TIMES.
               10  WS-FAIXA-LIMITE-SAL  PIC S9(11)V99 COMP-3.
               10  WS-FAIXA-FATOR-CAP   PIC S9(03)V99 COMP-3.

      *----------------------------------------------------------------*
      * IPCA — indice de reajuste para tipo E (escalonado temporal)    *
      * Exemplo: 4.83% ao ano (media historica IPCA 10 anos)           *
      *----------------------------------------------------------------*
       01  WS-IPCA-ANUAL                 PIC S9(03)V99 COMP-3.
       01  WS-ANOS-VIGENCIA              PIC 9(03)     VALUE ZEROS.

      *----------------------------------------------------------------*
      * Interface com subprograma CALCCAP (LINKAGE SECTION)            *
      *----------------------------------------------------------------*
       01  WS-CALCCAP-INPUT.
           05  CC-TIPO-CAPITAL           PIC X(01).
           05  CC-CAPITAL-BASE           PIC S9(13)V99 COMP-3.
           05  CC-SALARIO-BASE           PIC S9(11)V99 COMP-3.
           05  CC-FATOR-MULT             PIC S9(03)V99 COMP-3.
           05  CC-IPCA-ANUAL             PIC S9(03)V99 COMP-3.
           05  CC-ANOS-VIGENCIA          PIC 9(03).
           05  CC-FAIXA OCCURS 5 TIMES.
               10  CC-FAIXA-LIMITE       PIC S9(11)V99 COMP-3.
               10  CC-FAIXA-FATOR        PIC S9(03)V99 COMP-3.

       01  WS-CALCCAP-OUTPUT.
           05  CC-CAPITAL-CALCULADO      PIC S9(13)V99 COMP-3.
           05  CC-RETURN-CODE            PIC 9(02).

       01  WS-IDX                        PIC 9(02).

       COPY CPYAPOL.

       PROCEDURE DIVISION.
       0000-PRINCIPAL.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-PROCESSAR UNTIL WS-EOF
           PERFORM 3000-FINALIZAR
           STOP RUN.

       1000-INICIALIZAR.
      *    IPCA: carregado de parametro/DB2 em producao
      *    Aqui inicializado com media historica (4.83% a.a.)
           MOVE 4.83 TO WS-IPCA-ANUAL

      *    Tabela de faixas salariais para capital progressivo (tipo B)
      *    Faixa 1: ate  5.000  → fator 1.0x (1 salario)
      *    Faixa 2: ate 10.000  → fator 2.0x (2 salarios)
      *    Faixa 3: ate 20.000  → fator 3.0x (3 salarios)
      *    Faixa 4: ate 40.000  → fator 4.0x (4 salarios)
      *    Faixa 5: acima 40.000→ fator 5.0x (5 salarios)
           MOVE  5000.00  TO WS-FAIXA-LIMITE-SAL(1)
           MOVE     1.00  TO WS-FAIXA-FATOR-CAP(1)
           MOVE 10000.00  TO WS-FAIXA-LIMITE-SAL(2)
           MOVE     2.00  TO WS-FAIXA-FATOR-CAP(2)
           MOVE 20000.00  TO WS-FAIXA-LIMITE-SAL(3)
           MOVE     3.00  TO WS-FAIXA-FATOR-CAP(3)
           MOVE 40000.00  TO WS-FAIXA-LIMITE-SAL(4)
           MOVE     4.00  TO WS-FAIXA-FATOR-CAP(4)
           MOVE 99999999  TO WS-FAIXA-LIMITE-SAL(5)
           MOVE     5.00  TO WS-FAIXA-FATOR-CAP(5)

           OPEN INPUT  ARQ-APOLICE
           OPEN OUTPUT ARQ-CAPITAL
           PERFORM 9100-LER-APOLICE.

       2000-PROCESSAR.
           IF APO-TIPO-HEADER OR APO-TIPO-TRAILER
               PERFORM 9100-LER-APOLICE
           ELSE
               PERFORM 2100-PREPARAR-CHAMADA
               CALL 'CALCCAP' USING WS-CALCCAP-INPUT
                                    WS-CALCCAP-OUTPUT
               IF CC-RETURN-CODE EQUAL ZEROS
                   MOVE CC-CAPITAL-CALCULADO TO APO-CAPITAL-SEGURADO
               ELSE
                   DISPLAY 'VGCCAP01 ERRO CALCCAP RC='
                            CC-RETURN-CODE
                            ' APO=' APO-NUMERO
               END-IF
               WRITE FS-CAPITAL FROM REG-APOLICE
               PERFORM 9100-LER-APOLICE
           END-IF.

       2100-PREPARAR-CHAMADA.
      *    Transfere dados da apolice para a interface do subprograma
           MOVE APO-TIPO-CAPITAL        TO CC-TIPO-CAPITAL
           MOVE APO-CAPITAL-SEGURADO    TO CC-CAPITAL-BASE
           MOVE APO-SALARIO-BASE        TO CC-SALARIO-BASE
           MOVE APO-FATOR-MULTIPLICADOR TO CC-FATOR-MULT
           MOVE WS-IPCA-ANUAL           TO CC-IPCA-ANUAL

      *    Anos de vigencia = diferenca entre FIM e INI (simplificado)
           COMPUTE WS-ANOS-VIGENCIA =
               (FUNCTION NUMVAL(APO-VIGENCIA-FIM(1:4)) -
                FUNCTION NUMVAL(APO-VIGENCIA-INI(1:4)))
           IF WS-ANOS-VIGENCIA < 1
               MOVE 1 TO WS-ANOS-VIGENCIA
           END-IF
           MOVE WS-ANOS-VIGENCIA TO CC-ANOS-VIGENCIA

      *    Copia tabela de faixas para interface
           PERFORM VARYING WS-IDX FROM 1 BY 1
               UNTIL WS-IDX > 5
               MOVE WS-FAIXA-LIMITE-SAL(WS-IDX)
                   TO CC-FAIXA-LIMITE(WS-IDX)
               MOVE WS-FAIXA-FATOR-CAP(WS-IDX)
                   TO CC-FAIXA-FATOR(WS-IDX)
           END-PERFORM.

       3000-FINALIZAR.
           CLOSE ARQ-APOLICE ARQ-CAPITAL.

       9100-LER-APOLICE.
           READ ARQ-APOLICE INTO REG-APOLICE
           AT END MOVE 'S' TO WS-FIM
           END-READ.
