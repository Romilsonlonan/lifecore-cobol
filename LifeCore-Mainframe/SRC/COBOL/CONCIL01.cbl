      *================================================================*
      * PROGRAMA  : CONCIL01                                          *
      * DESCRICAO : Conciliacao entre Faturado e Pago                 *
      *             Match entre arquivo de fatura e arquivo de pagto  *
      *             Gera arquivo de conciliacao com status detalhado  *
      * PROJETO   : LifeCore-Mainframe                                *
      * DB2 PLAN  : LCCONPL                                           *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CONCIL01.
       AUTHOR.     LIFECORE-TEAM.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ARQ-FATURA
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.FATURA'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-FAT.
           SELECT ARQ-PAGAMENTO
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.PAGAMENTO'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-PAG.
           SELECT ARQ-CONCILIACAO
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.CONCILIACAO'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-CON.

       DATA DIVISION.
       FILE SECTION.
       FD  ARQ-FATURA      RECORD CONTAINS 250 CHARACTERS.
       01  FS-FATURA                     PIC X(250).
       FD  ARQ-PAGAMENTO   RECORD CONTAINS 200 CHARACTERS.
       01  FS-PAGAMENTO                  PIC X(200).
       FD  ARQ-CONCILIACAO RECORD CONTAINS 220 CHARACTERS.
       01  FS-CONCILIACAO                PIC X(220).

       WORKING-STORAGE SECTION.
       01  WS-FS-FAT                     PIC X(02).
       01  WS-FS-PAG                     PIC X(02).
       01  WS-FS-CON                     PIC X(02).
       01  WS-FIM-FAT                    PIC X(01) VALUE 'N'.
           88  WS-EOF-FAT                VALUE 'S'.
       01  WS-FIM-PAG                    PIC X(01) VALUE 'N'.
           88  WS-EOF-PAG                VALUE 'S'.

       01  WS-CTR-OK                     PIC 9(07) VALUE ZEROS.
       01  WS-CTR-DIVERGENCIAS           PIC 9(07) VALUE ZEROS.
       01  WS-CTR-SEM-PAGTO              PIC 9(07) VALUE ZEROS.
       01  WS-SEQ                        PIC 9(10) VALUE ZEROS.
       01  WS-TOLERANCIA                 PIC S9(09)V9 COMP-3 VALUE 0
                                         .

       COPY CPYSQLCA.
       COPY CPYFATU.
       COPY CPYPAGT.
       COPY CPYCONC.

       PROCEDURE DIVISION.
       0000-PRINCIPAL.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-PROCESSAR
           PERFORM 3000-FINALIZAR
           STOP RUN.

       1000-INICIALIZAR.
           OPEN INPUT  ARQ-FATURA
           OPEN INPUT  ARQ-PAGAMENTO
           OPEN OUTPUT ARQ-CONCILIACAO
           PERFORM 9100-LER-FATURA
           PERFORM 9200-LER-PAGAMENTO.

       2000-PROCESSAR.
           PERFORM UNTIL WS-EOF-FAT
               IF WS-EOF-PAG
                   PERFORM 2400-SEM-PAGAMENTO
               ELSE
                   EVALUATE TRUE
                       WHEN FAT-NUMERO EQUAL PAG-FATURA-NUMERO
                           PERFORM 2100-CONCILIAR
                       WHEN FAT-NUMERO < PAG-FATURA-NUMERO
                           PERFORM 2400-SEM-PAGAMENTO
                       WHEN OTHER
                           PERFORM 9200-LER-PAGAMENTO
                   END-EVALUATE
               END-IF
           END-PERFORM.

       2100-CONCILIAR.
           INITIALIZE REG-CONCILIACAO
           ADD 1 TO WS-SEQ
           MOVE 'D1'               TO CON-TIPO-REGISTRO
           MOVE WS-SEQ             TO CON-NUMERO
           MOVE FAT-NUMERO         TO CON-FATURA-NUMERO
           MOVE PAG-NUMERO         TO CON-PAGAMENTO-NUMERO
           MOVE FAT-VALOR-LIQUIDO  TO CON-VALOR-FATURADO
           MOVE PAG-VALOR          TO CON-VALOR-PAGO
           MOVE PAG-NSU            TO CON-NSU
           MOVE PAG-COD-AUTORIZACAO TO CON-COD-AUTORIZACAO
           SUBTRACT FAT-VALOR-LIQUIDO FROM PAG-VALOR
               GIVING CON-VALOR-DIFERENCA
           IF CON-VALOR-DIFERENCA >= WS-TOLERANCIA * -1
               AND CON-VALOR-DIFERENCA <= WS-TOLERANCIA
               MOVE 'OK' TO CON-STATUS
               ADD 1 TO WS-CTR-OK
           ELSE
               MOVE 'DV' TO CON-STATUS
               ADD 1 TO WS-CTR-DIVERGENCIAS
           END-IF
           WRITE FS-CONCILIACAO FROM REG-CONCILIACAO
           PERFORM 9300-INSERT-CONCIL-DB2
           PERFORM 9100-LER-FATURA
           PERFORM 9200-LER-PAGAMENTO.

       2400-SEM-PAGAMENTO.
           INITIALIZE REG-CONCILIACAO
           MOVE 'D1'               TO CON-TIPO-REGISTRO
           MOVE FAT-NUMERO         TO CON-FATURA-NUMERO
           MOVE FAT-VALOR-LIQUIDO  TO CON-VALOR-FATURADO
           MOVE ZEROS              TO CON-VALOR-PAGO
           MOVE 'SP'               TO CON-STATUS
           ADD 1 TO WS-CTR-SEM-PAGTO
           WRITE FS-CONCILIACAO FROM REG-CONCILIACAO
           PERFORM 9100-LER-FATURA.

       3000-FINALIZAR.
      *        EXEC SQL COMMIT END-EXEC
           DISPLAY '*** CONCIL01 RELATORIO FINAL ***'
           DISPLAY 'CONCILIADOS OK      : ' WS-CTR-OK
           DISPLAY 'DIVERGENCIAS        : ' WS-CTR-DIVERGENCIAS
           DISPLAY 'SEM PAGAMENTO       : ' WS-CTR-SEM-PAGTO
           CLOSE ARQ-FATURA ARQ-PAGAMENTO ARQ-CONCILIACAO
           IF WS-CTR-DIVERGENCIAS > ZEROS OR WS-CTR-SEM-PAGTO > ZEROS
               MOVE 4 TO RETURN-CODE
           END-IF.

       9100-LER-FATURA.
           READ ARQ-FATURA INTO REG-FATURA
           AT END MOVE 'S' TO WS-FIM-FAT
           END-READ.

       9200-LER-PAGAMENTO.
           READ ARQ-PAGAMENTO INTO REG-PAGAMENTO
           AT END MOVE 'S' TO WS-FIM-PAG
           END-READ.

       9300-INSERT-CONCIL-DB2.
      *    DB2 (z/OS): descomente apos BIND com LCCONPL
      *        EXEC SQL
      *            INSERT INTO CONCILIACAO (
      *                NR_CONCILIACAO, NR_FATURA, NR_PAGAMENTO,
      *                VL_FATURADO, VL_PAGO, VL_DIFERENCA, CD_STATUS
      *            ) VALUES (
      *                :CON-NUMERO, :CON-FATURA-NUMERO,
      *                :CON-PAGAMENTO-NUMERO, :CON-VALOR-FATURADO,
      *                :CON-VALOR-PAGO, :CON-VALOR-DIFERENCA, :CON-STATUS
      *            )
      *        END-EXEC
           DISPLAY 'CONCIL01 INSERT CONC=' CON-NUMERO.
