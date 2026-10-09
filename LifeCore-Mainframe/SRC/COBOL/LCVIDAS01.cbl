      *----------------------------------------------------------------*
      * LCVIDAS01 - BATCH: PROCESSA FILA DE IMPORTACAO DE VIDAS      *
      * Lê IMPORTACAO_VIDAS_ITEM com STATUS='PE',                    *
      * chama VGCCAP01 para calcular capital escalonado e            *
      * confirma STATUS='OK' no DB2.                                 *
      *                                                              *
      * Transação CICS de consulta: LCVD (via LCCICS09)             *
      * JCL de acionamento: LCVIDAS1.jcl                            *
      *----------------------------------------------------------------*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LCVIDAS01.
       AUTHOR. LIFECORE-IQ.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT RELATORIO ASSIGN TO DDRELAT
               ORGANIZATION IS SEQUENTIAL.

       DATA DIVISION.
       FILE SECTION.
       FD RELATORIO RECORDING MODE IS F
                    BLOCK CONTAINS 0 RECORDS.
       01  REL-LINHA               PIC X(133).

       WORKING-STORAGE SECTION.

      *----------------------------------------------------------------*
      * Contadores e controle                                          *
      *----------------------------------------------------------------*
       01  WS-TOTAL-LIDOS          PIC S9(9) COMP VALUE ZERO.
       01  WS-TOTAL-OK             PIC S9(9) COMP VALUE ZERO.
       01  WS-TOTAL-ERRO           PIC S9(9) COMP VALUE ZERO.
       01  WS-FIM-CURSOR           PIC X(01) VALUE 'N'.
       01  WS-DATA-HOJE            PIC X(08).
       01  WS-HORA-HOJE            PIC X(06).
       01  WS-RC                   PIC S9(9) COMP VALUE ZERO.

      *----------------------------------------------------------------*
      * Campos de trabalho para cálculo de capital                    *
      *----------------------------------------------------------------*
       01  WS-VL-SALARIO           PIC S9(13)V9(2) COMP-3.
       01  WS-NR-FATOR             PIC S9(05)V9(2) COMP-3.
       01  WS-VL-CAPITAL           PIC S9(15)V9(2) COMP-3.
       01  WS-TP-CAPITAL           PIC X(01) VALUE 'E'.

      *----------------------------------------------------------------*
      * Campos DB2 para leitura do lote                               *
      *----------------------------------------------------------------*
       01  WS-ID-IMPORTACAO        PIC X(36).
       01  WS-NR-LINHA             PIC S9(9) COMP.
       01  WS-CD-CPF               PIC X(11).
       01  WS-NM-SEGURADO          PIC X(60).
       01  WS-CD-SUB               PIC X(10).
       01  WS-CD-MODULO            PIC X(10).
       01  WS-CD-CARGO             PIC X(30).
       01  WS-VL-SAL-DB2           PIC S9(13)V9(2) COMP-3.
       01  WS-NR-FAT-DB2           PIC S9(05)V9(2) COMP-3.
       01  WS-VL-CAP-DB2           PIC S9(15)V9(2) COMP-3.
       01  WS-DT-ADMISSAO          PIC X(08).
       01  WS-NR-APOLICE           PIC X(14).
       01  WS-CD-EMPRESA           PIC S9(9) COMP.

      *----------------------------------------------------------------*
      * SQLCA                                                          *
      *----------------------------------------------------------------*
           EXEC SQL INCLUDE SQLCA END-EXEC.

      *----------------------------------------------------------------*
      * Cursor: busca lotes pendentes e seus itens                    *
      *----------------------------------------------------------------*
           EXEC SQL
               DECLARE C-VIDAS CURSOR FOR
               SELECT I.ID_IMPORTACAO,
                      V.NR_LINHA,
                      V.CD_CPF,
                      V.NM_SEGURADO,
                      V.CD_SUBESTIPULANTE,
                      V.CD_MODULO,
                      V.CD_CARGO,
                      V.VL_SALARIO,
                      V.NR_FATOR_MULT,
                      V.VL_CAPITAL,
                      V.DT_ADMISSAO,
                      I.NR_APOLICE,
                      I.CD_EMPRESA
                 FROM LIFECORE.IMPORTACAO_VIDAS  I
                 JOIN LIFECORE.IMPORTACAO_VIDAS_ITEM V
                   ON V.ID_IMPORTACAO = I.ID_IMPORTACAO
                WHERE I.CD_STATUS IN ('PE', 'PA')
                  AND V.CD_STATUS = 'OK'
                ORDER BY I.ID_IMPORTACAO, V.NR_LINHA
           END-EXEC.

       LINKAGE SECTION.

       PROCEDURE DIVISION.

       0000-MAIN.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-ABRIR-CURSOR
           IF WS-RC NOT = ZERO
               PERFORM 9000-ENCERRAR
               STOP RUN
           END-IF
           PERFORM 3000-PROCESSAR
               UNTIL WS-FIM-CURSOR = 'S'
           PERFORM 4000-FECHAR-CURSOR
           PERFORM 9000-ENCERRAR
           STOP RUN.

      *----------------------------------------------------------------*
       1000-INICIALIZAR.
           MOVE FUNCTION CURRENT-DATE(1:8)  TO WS-DATA-HOJE
           MOVE FUNCTION CURRENT-DATE(9:6)  TO WS-HORA-HOJE
           OPEN OUTPUT RELATORIO
           WRITE REL-LINHA FROM
               'LCVIDAS01 - INICIO ' WS-DATA-HOJE ' ' WS-HORA-HOJE.

      *----------------------------------------------------------------*
       2000-ABRIR-CURSOR.
           EXEC SQL OPEN C-VIDAS END-EXEC
           IF SQLCODE NOT = 0
               MOVE SQLCODE TO WS-RC
               WRITE REL-LINHA FROM
                   'ERRO ao abrir cursor C-VIDAS.'
           END-IF.

      *----------------------------------------------------------------*
       3000-PROCESSAR.
           EXEC SQL
               FETCH C-VIDAS
                INTO :WS-ID-IMPORTACAO,
                     :WS-NR-LINHA,
                     :WS-CD-CPF,
                     :WS-NM-SEGURADO,
                     :WS-CD-SUB,
                     :WS-CD-MODULO,
                     :WS-CD-CARGO,
                     :WS-VL-SAL-DB2,
                     :WS-NR-FAT-DB2,
                     :WS-VL-CAP-DB2,
                     :WS-DT-ADMISSAO,
                     :WS-NR-APOLICE,
                     :WS-CD-EMPRESA
           END-EXEC

           IF SQLCODE = 100
               MOVE 'S' TO WS-FIM-CURSOR
               EXIT PARAGRAPH
           END-IF

           IF SQLCODE NOT = 0
               ADD 1 TO WS-TOTAL-ERRO
               MOVE 'S' TO WS-FIM-CURSOR
               EXIT PARAGRAPH
           END-IF

           ADD 1 TO WS-TOTAL-LIDOS

      *    Recalcula capital escalonado se salário informado
           IF WS-VL-SAL-DB2 > ZERO
               MOVE WS-VL-SAL-DB2  TO WS-VL-SALARIO
               MOVE WS-NR-FAT-DB2  TO WS-NR-FATOR
               IF WS-NR-FATOR <= ZERO
                   MOVE 3.00 TO WS-NR-FATOR
               END-IF
               COMPUTE WS-VL-CAPITAL = WS-VL-SALARIO * WS-NR-FATOR
           ELSE
               MOVE WS-VL-CAP-DB2 TO WS-VL-CAPITAL
           END-IF

      *    Atualiza capital na COBERTURA do segurado
           EXEC SQL
               UPDATE LIFECORE.COBERTURA
                  SET VL_CAPITAL = :WS-VL-CAPITAL
                WHERE NR_APOLICE = :WS-NR-APOLICE
                  AND CD_COBERTURA = CHAR('COB' || TRIM(:WS-CD-CPF))
                  AND CD_STATUS = 'AT'
           END-EXEC

           IF SQLCODE NOT = 0 AND SQLCODE NOT = 100
               ADD 1 TO WS-TOTAL-ERRO
               EXIT PARAGRAPH
           END-IF

           ADD 1 TO WS-TOTAL-OK.

      *----------------------------------------------------------------*
       4000-FECHAR-CURSOR.
           EXEC SQL CLOSE C-VIDAS END-EXEC.

      *----------------------------------------------------------------*
       9000-ENCERRAR.
           EXEC SQL
               UPDATE LIFECORE.IMPORTACAO_VIDAS
                  SET CD_STATUS = 'OK'
                WHERE CD_STATUS IN ('PE', 'PA')
                  AND QT_GRAVADOS > 0
           END-EXEC
           EXEC SQL COMMIT END-EXEC

           WRITE REL-LINHA FROM
               'LCVIDAS01 - FIM LIDOS=' WS-TOTAL-LIDOS
               ' OK=' WS-TOTAL-OK ' ERRO=' WS-TOTAL-ERRO
           CLOSE RELATORIO.
