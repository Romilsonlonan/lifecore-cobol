      *================================================================*
      * PROGRAMA  : PAGTO01                                           *
      * DESCRICAO : Baixa de Pagamentos                               *
      *             Lê arquivo de pagamentos e atualiza FATURA no DB2 *
      * PROJETO   : LifeCore-Mainframe                                *
      * PCI NOTE  : PAN nao armazenado. Token + ultimos 4 digitos     *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAGTO01.
       AUTHOR.     LIFECORE-TEAM.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ARQ-PAGAMENTO
               ASSIGN TO 'LIFECORE.DATA.INPUT.PAGAMENTO'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-PAG.
           SELECT ARQ-PAGTO-OK
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.PAGAMENTO'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-OK.

       DATA DIVISION.
       FILE SECTION.
       FD  ARQ-PAGAMENTO RECORD CONTAINS 200 CHARACTERS.
       01  FS-PAGAMENTO                  PIC X(200).
       FD  ARQ-PAGTO-OK  RECORD CONTAINS 200 CHARACTERS.
       01  FS-PAGTO-OK                   PIC X(200).

       WORKING-STORAGE SECTION.
       01  WS-FS-PAG                     PIC X(02).
       01  WS-FS-OK                      PIC X(02).
       01  WS-FIM                        PIC X(01) VALUE 'N'.
           88  WS-EOF                    VALUE 'S'.
       01  WS-CTR-PROCESSADOS            PIC 9(07) VALUE ZEROS.
       01  WS-CTR-ERROS                  PIC 9(07) VALUE ZEROS.

       COPY CPYSQLCA.
       COPY CPYPAGT.

       PROCEDURE DIVISION.
       0000-PRINCIPAL.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-PROCESSAR UNTIL WS-EOF
           PERFORM 3000-FINALIZAR
           STOP RUN.

       1000-INICIALIZAR.
           OPEN INPUT  ARQ-PAGAMENTO
           OPEN OUTPUT ARQ-PAGTO-OK
           PERFORM 9100-LER-PAGAMENTO.

       2000-PROCESSAR.
           IF PAG-TIPO-HEADER OR PAG-TIPO-TRAILER
               PERFORM 9100-LER-PAGAMENTO
           ELSE
               IF PAG-CONFIRMADO
                   PERFORM 2100-BAIXAR-FATURA
                   IF SQLCODE EQUAL ZEROS
                       ADD 1 TO WS-CTR-PROCESSADOS
                       WRITE FS-PAGTO-OK FROM REG-PAGAMENTO
                   ELSE
                       ADD 1 TO WS-CTR-ERROS
                   END-IF
               END-IF
               PERFORM 9100-LER-PAGAMENTO
           END-IF.

       2100-BAIXAR-FATURA.
      *    DB2 (z/OS): descomente apos BIND com LCPAGPL
      *        EXEC SQL
      *            UPDATE FATURA
      *               SET VL_PAGO = VL_PAGO + :PAG-VALOR,
      *                   CD_STATUS = 'PP',
      *                   DT_PAGAMENTO = :PAG-DATA-PAGAMENTO
      *             WHERE NR_FATURA = :PAG-FATURA-NUMERO
      *        END-EXEC
           DISPLAY 'PAGTO01 UPDATE FAT=' PAG-FATURA-NUMERO.

       3000-FINALIZAR.
      *        EXEC SQL COMMIT END-EXEC
           DISPLAY '*** PAGTO01 RELATORIO FINAL ***'
           DISPLAY 'PAGAMENTOS PROCESSADOS: ' WS-CTR-PROCESSADOS
           DISPLAY 'ERROS                 : ' WS-CTR-ERROS
           CLOSE ARQ-PAGAMENTO ARQ-PAGTO-OK
           IF WS-CTR-ERROS > ZEROS
               MOVE 8 TO RETURN-CODE
           END-IF.

       9100-LER-PAGAMENTO.
           READ ARQ-PAGAMENTO INTO REG-PAGAMENTO
           AT END MOVE 'S' TO WS-FIM
           END-READ.
