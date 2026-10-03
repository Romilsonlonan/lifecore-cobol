      *================================================================*
      * PROGRAMA  : DISPUT01                                          *
      * DESCRICAO : Tratamento de Chargebacks e Abertura de Disputas  *
      *             Identifica CB no clearing e registra no DB2       *
      * PROJETO   : LifeCore-Mainframe                                *
      * FLUXO     : CONCILIACAO → CHARGEBACK → DISPUTA → OPERACAO     *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DISPUT01.
       AUTHOR.     LIFECORE-TEAM.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ARQ-LIQUIDACAO
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.LIQUIDACAO'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-LIQ.
           SELECT ARQ-DISPUTAS
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.DISPUTAS'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-DIS.

       DATA DIVISION.
       FILE SECTION.
       FD  ARQ-LIQUIDACAO RECORD CONTAINS 300 CHARACTERS.
       01  FS-LIQUIDACAO                 PIC X(300).
       FD  ARQ-DISPUTAS   RECORD CONTAINS 300 CHARACTERS.
       01  FS-DISPUTAS                   PIC X(300).

       WORKING-STORAGE SECTION.
       01  WS-FS-LIQ                     PIC X(02).
       01  WS-FS-DIS                     PIC X(02).
       01  WS-FIM                        PIC X(01) VALUE 'N'.
           88  WS-EOF                    VALUE 'S'.
       01  WS-CTR-DISPUTAS               PIC 9(07) VALUE ZEROS.
       01  WS-CTR-DIVERGENCIAS           PIC 9(07) VALUE ZEROS.
       01  WS-DISPUTA-SEQ                PIC 9(10) VALUE ZEROS.

       COPY CPYSQLCA.

      *    Layout de saida de disputa
       01  REG-DISPUTA.
           05  DIS-NUMERO                PIC 9(10)    COMP-3.
           05  DIS-NSU                   PIC X(12).
           05  DIS-TIPO                  PIC X(04).
               88  DIS-CHARGEBACK        VALUE 'CB00'.
               88  DIS-DIVERGENCIA       VALUE 'DIVG'.
           05  DIS-VALOR                 PIC S9(13)V99 COMP-3.
           05  DIS-DATA-ABERTURA         PIC X(08).
           05  DIS-STATUS                PIC X(02).
               88  DIS-ABERTA            VALUE 'AB'.
               88  DIS-ENCERRADA         VALUE 'EN'.
               88  DIS-GANHA             VALUE 'GA'.
               88  DIS-PERDIDA           VALUE 'PE'.
           05  DIS-OBSERVACAO            PIC X(80).
           05  DIS-FILLER                PIC X(176).

       COPY CPYLIQ.

       PROCEDURE DIVISION.
       0000-PRINCIPAL.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-PROCESSAR UNTIL WS-EOF
           PERFORM 3000-FINALIZAR
           STOP RUN.

       1000-INICIALIZAR.
           OPEN INPUT  ARQ-LIQUIDACAO
           OPEN OUTPUT ARQ-DISPUTAS
           PERFORM 9100-LER.

       2000-PROCESSAR.
           EVALUATE TRUE
               WHEN LIQ-DIVERGENCIA
                   PERFORM 2100-ABRIR-DISPUTA-DIVERGENCIA
               WHEN LIQ-NAO-ENCONTRADO
                   PERFORM 2200-ABRIR-DISPUTA-NAO-ENCONTRADO
               WHEN OTHER
                   CONTINUE
           END-EVALUATE
           PERFORM 9100-LER.

       2100-ABRIR-DISPUTA-DIVERGENCIA.
           ADD 1 TO WS-DISPUTA-SEQ WS-CTR-DIVERGENCIAS
           INITIALIZE REG-DISPUTA
           MOVE WS-DISPUTA-SEQ             TO DIS-NUMERO
           MOVE LIQ-NSU                    TO DIS-NSU
           MOVE 'DIVG'                     TO DIS-TIPO
           MOVE LIQ-DIFERENCA              TO DIS-VALOR
           MOVE FUNCTION CURRENT-DATE(1:8) TO DIS-DATA-ABERTURA
           MOVE 'AB'                       TO DIS-STATUS
           MOVE 'DIVERGENCIA DE VALOR NA LIQUIDACAO' TO DIS-OBSERVACAO
           WRITE FS-DISPUTAS FROM REG-DISPUTA
           PERFORM 9300-INSERT-DISPUTA-DB2.

       2200-ABRIR-DISPUTA-NAO-ENCONTRADO.
           ADD 1 TO WS-DISPUTA-SEQ WS-CTR-DISPUTAS
           INITIALIZE REG-DISPUTA
           MOVE WS-DISPUTA-SEQ             TO DIS-NUMERO
           MOVE LIQ-NSU                    TO DIS-NSU
           MOVE 'CB00'                     TO DIS-TIPO
           MOVE LIQ-VALOR-CLEARING         TO DIS-VALOR
           MOVE FUNCTION CURRENT-DATE(1:8) TO DIS-DATA-ABERTURA
           MOVE 'AB'                       TO DIS-STATUS
           MOVE 'SEM CORRESPONDENCIA NA AGENDA'
               TO DIS-OBSERVACAO
           WRITE FS-DISPUTAS FROM REG-DISPUTA
           PERFORM 9300-INSERT-DISPUTA-DB2.

       3000-FINALIZAR.
      *        EXEC SQL COMMIT END-EXEC
           DISPLAY '*** DISPUT01 RELATORIO FINAL ***'
           DISPLAY 'CHARGEBACKS / CB   : ' WS-CTR-DISPUTAS
           DISPLAY 'DIVERGENCIAS VALOR : ' WS-CTR-DIVERGENCIAS
           CLOSE ARQ-LIQUIDACAO ARQ-DISPUTAS
           IF WS-CTR-DISPUTAS > ZEROS OR WS-CTR-DIVERGENCIAS > ZEROS
               MOVE 4 TO RETURN-CODE
           END-IF.

       9100-LER.
           READ ARQ-LIQUIDACAO INTO REG-LIQUIDACAO
           AT END MOVE 'S' TO WS-FIM
           END-READ.

       9300-INSERT-DISPUTA-DB2.
      *    DB2 (z/OS): descomente o EXEC SQL abaixo apos BIND
      *        EXEC SQL
      *            INSERT INTO DISPUTA (
      *                NR_DISPUTA, NR_NSU, TP_DISPUTA,
      *                VL_DISPUTA, DT_ABERTURA, CD_STATUS, DS_OBSERVACAO
      *            ) VALUES (
      *                :DIS-NUMERO, :DIS-NSU, :DIS-TIPO,
      *                :DIS-VALOR, :DIS-DATA-ABERTURA,
      *                :DIS-STATUS, :DIS-OBSERVACAO
      *            )
      *        END-EXEC
           DISPLAY 'DISPUT01 INSERT DISPUTA NR=' DIS-NUMERO.
