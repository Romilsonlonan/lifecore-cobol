      *================================================================*
      * PROGRAMA  : CALCCAP                                           *
      * DESCRICAO : Subprograma de Calculo de Capital Segurado        *
      *             Chamado via CALL 'CALCCAP' USING INPUT OUTPUT     *
      *                                                               *
      *   Conceitos absorvidos de projetos anteriores:                *
      *                                                               *
      *   1. Calculo progressivo por faixa (tipo B)                   *
      *      Originado do padrao CALCULA-INSS do FOLHA.CBL.           *
      *      Cada faixa acumula apenas o excedente, nao salta para    *
      *      o fator da faixa inteira. Exemplo com 3 faixas:          *
      *        Salario = R$ 12.000                                     *
      *        Faixa 1: ate  5.000 → fator 1x → capital  5.000       *
      *        Faixa 2: ate 10.000 → fator 2x → capital 10.000        *
      *        Faixa 3: acima     → fator 3x → (12.000-10.000)*3      *
      *        Capital total = 5.000 + 10.000 + 6.000 = 21.000        *
      *                                                               *
      *   2. Atualização por IPCA (tipo E — escalonado temporal)      *
      *      Originado do padrao de exponenciacao do JUROS-COMPOSTOS  *
      *      adaptado para o contexto de seguros:                     *
      *        Capital_atualizado = Capital_base * (1 + IPCA/100)^n   *
      *      Onde n = anos de vigencia da apolice.                    *
      *      O IPCA e o indexador oficial SUSEP para VGC/GLB.         *
      *      Exemplo: capital R$ 100.000, IPCA 4.83%, 3 anos          *
      *        = 100.000 * (1.0483)^3 = 115.233                       *
      *                                                               *
      * PROJETO   : LifeCore-Mainframe                                *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALCCAP.
       AUTHOR.     LIFECORE-TEAM.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *--- Auxiliares internos de calculo ---
       01  WS-CAPITAL-ACUM               PIC S9(15)V99 COMP-3.
       01  WS-CAPITAL-FAIXA              PIC S9(13)V99 COMP-3.
       01  WS-SAL-FAIXA-ANT              PIC S9(11)V99 COMP-3.
       01  WS-SAL-EXCEDENTE              PIC S9(11)V99 COMP-3.
       01  WS-FATOR-IPCA                 PIC S9(05)V9(08) COMP-3.
       01  WS-IDX                        PIC 9(02).

       LINKAGE SECTION.
      *--- Entrada ---
       01  LK-INPUT.
           05  LK-TIPO-CAPITAL           PIC X(01).
               88  LK-TIPO-FIXO          VALUE 'F'.
               88  LK-TIPO-ESCALONADO    VALUE 'E'.
               88  LK-TIPO-MULT-SAL      VALUE 'M'.
               88  LK-TIPO-POR-FAIXA     VALUE 'B'.
               88  LK-TIPO-PARAMETRICO   VALUE 'P'.
           05  LK-CAPITAL-BASE           PIC S9(13)V99 COMP-3.
           05  LK-SALARIO-BASE           PIC S9(11)V99 COMP-3.
           05  LK-FATOR-MULT             PIC S9(03)V99 COMP-3.
           05  LK-IPCA-ANUAL             PIC S9(03)V99 COMP-3.
           05  LK-ANOS-VIGENCIA          PIC 9(03).
           05  LK-FAIXA OCCURS 5 TIMES.
               10  LK-FAIXA-LIMITE       PIC S9(11)V99 COMP-3.
               10  LK-FAIXA-FATOR        PIC S9(03)V99 COMP-3.

      *--- Saida ---
       01  LK-OUTPUT.
           05  LK-CAPITAL-CALCULADO      PIC S9(13)V99 COMP-3.
           05  LK-RETURN-CODE            PIC 9(02).

       PROCEDURE DIVISION USING LK-INPUT LK-OUTPUT.
       0000-PRINCIPAL.
           MOVE ZEROS TO LK-CAPITAL-CALCULADO
           MOVE ZEROS TO LK-RETURN-CODE

           EVALUATE TRUE
               WHEN LK-TIPO-FIXO
                   PERFORM 1000-CAPITAL-FIXO
               WHEN LK-TIPO-ESCALONADO
                   PERFORM 2000-CAPITAL-ESCALONADO-IPCA
               WHEN LK-TIPO-MULT-SAL
                   PERFORM 3000-CAPITAL-MULT-SALARIAL
               WHEN LK-TIPO-POR-FAIXA
                   PERFORM 4000-CAPITAL-PROGRESSIVO-FAIXA
               WHEN LK-TIPO-PARAMETRICO
                   PERFORM 5000-CAPITAL-PARAMETRICO
               WHEN OTHER
                   DISPLAY 'CALCCAP TIPO INVALIDO: ' LK-TIPO-CAPITAL
                   MOVE 4 TO LK-RETURN-CODE
           END-EVALUATE.

           GOBACK.

      *----------------------------------------------------------------*
      * Tipo F — Fixo                                                  *
      * Capital ja definido na apolice, nao recalcula.                 *
      *----------------------------------------------------------------*
       1000-CAPITAL-FIXO.
           MOVE LK-CAPITAL-BASE TO LK-CAPITAL-CALCULADO.

      *----------------------------------------------------------------*
      * Tipo E — Escalonado com atualizacao por IPCA                   *
      *                                                                *
      * Formula: Capital_atualizado = Capital_base * (1+IPCA/100)^n   *
      * Onde n = anos de vigencia da apolice                           *
      *                                                                *
      * O IPCA (Indice Nacional de Precos ao Consumidor Amplo) e o    *
      * indexador oficial SUSEP para apolices de vida em grupo.        *
      * Capturado via parametro LK-IPCA-ANUAL (ex: 4.83 para 4.83%).  *
      *----------------------------------------------------------------*
       2000-CAPITAL-ESCALONADO-IPCA.
           COMPUTE WS-FATOR-IPCA =
               (1 + (LK-IPCA-ANUAL / 100)) ** LK-ANOS-VIGENCIA
           COMPUTE LK-CAPITAL-CALCULADO =
               LK-CAPITAL-BASE * WS-FATOR-IPCA.

      *----------------------------------------------------------------*
      * Tipo M — Multiplo Salarial                                     *
      * Capital = salario-base * fator-multiplicador                   *
      * Ex: fator 24 = 24 salarios de cobertura                        *
      *----------------------------------------------------------------*
       3000-CAPITAL-MULT-SALARIAL.
           MULTIPLY LK-SALARIO-BASE BY LK-FATOR-MULT
               GIVING LK-CAPITAL-CALCULADO.

      *----------------------------------------------------------------*
      * Tipo B — Progressivo por Faixa Salarial                        *
      *                                                                *
      * Baseado no padrao progressivo do INSS (FOLHA.CBL/CALCULA-INSS)*
      * adaptado para seguros: cada faixa contribui com o excedente   *
      * sobre a faixa anterior multiplicado pelo fator da faixa.       *
      *                                                                *
      * Exemplo: salario R$ 12.000, faixas ate 5k(1x), 10k(2x), inf(3x)*
      *   Faixa 1:  5.000        *  1 =  5.000                         *
      *   Faixa 2: (10.000-5.000)* 2 = 10.000                         *
      *   Faixa 3: (12.000-10.000)*3 =  6.000                         *
      *   Capital total           = 21.000                             *
      *----------------------------------------------------------------*
       4000-CAPITAL-PROGRESSIVO-FAIXA.
           MOVE ZEROS TO WS-CAPITAL-ACUM
           MOVE ZEROS TO WS-SAL-FAIXA-ANT

           PERFORM VARYING WS-IDX FROM 1 BY 1 UNTIL WS-IDX > 5

               IF LK-SALARIO-BASE > WS-SAL-FAIXA-ANT

                   IF LK-SALARIO-BASE <= LK-FAIXA-LIMITE(WS-IDX)
      *                Salario esta nesta faixa — pega so o excedente
                       SUBTRACT WS-SAL-FAIXA-ANT FROM LK-SALARIO-BASE
                           GIVING WS-SAL-EXCEDENTE
                       MULTIPLY WS-SAL-EXCEDENTE
                           BY LK-FAIXA-FATOR(WS-IDX)
                           GIVING WS-CAPITAL-FAIXA
                       ADD WS-CAPITAL-FAIXA TO WS-CAPITAL-ACUM
                       MOVE LK-FAIXA-LIMITE(WS-IDX)
                           TO WS-SAL-FAIXA-ANT
                   ELSE
      *                Salario ultrapassa o limite desta faixa
      *                Calcula o valor cheio da faixa
                       SUBTRACT WS-SAL-FAIXA-ANT
                           FROM LK-FAIXA-LIMITE(WS-IDX)
                           GIVING WS-SAL-EXCEDENTE
                       MULTIPLY WS-SAL-EXCEDENTE
                           BY LK-FAIXA-FATOR(WS-IDX)
                           GIVING WS-CAPITAL-FAIXA
                       ADD WS-CAPITAL-FAIXA TO WS-CAPITAL-ACUM
                       MOVE LK-FAIXA-LIMITE(WS-IDX)
                           TO WS-SAL-FAIXA-ANT
                   END-IF
               END-IF

           END-PERFORM

           MOVE WS-CAPITAL-ACUM TO LK-CAPITAL-CALCULADO.

      *----------------------------------------------------------------*
      * Tipo P — Parametrico                                           *
      * Capital = salario * fator (configurado por produto/apolice)    *
      *----------------------------------------------------------------*
       5000-CAPITAL-PARAMETRICO.
           MULTIPLY LK-SALARIO-BASE BY LK-FATOR-MULT
               GIVING LK-CAPITAL-CALCULADO.
