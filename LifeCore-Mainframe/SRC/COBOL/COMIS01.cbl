      *================================================================*
      * PROGRAMA  : COMIS01                                           *
      * DESCRICAO : Calculo de Comissoes por Corretora/Estipulante    *
      *             Calcula sobre faturamento conciliado como OK      *
      * PROJETO   : LifeCore-Mainframe                                *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. COMIS01.
       AUTHOR.     LIFECORE-TEAM.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ARQ-CONCILIACAO
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.CONCILIACAO'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-CON.
           SELECT ARQ-COMISSAO
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.COMISSAO'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-COM.

       DATA DIVISION.
       FILE SECTION.
       FD  ARQ-CONCILIACAO RECORD CONTAINS 220 CHARACTERS.
       01  FS-CONCILIACAO                PIC X(220).
       FD  ARQ-COMISSAO    RECORD CONTAINS 200 CHARACTERS.
       01  FS-COMISSAO                   PIC X(200).

       WORKING-STORAGE SECTION.
       01  WS-FS-CON                     PIC X(02).
       01  WS-FS-COM                     PIC X(02).
       01  WS-FIM                        PIC X(01) VALUE 'N'.
           88  WS-EOF                    VALUE 'S'.

       01  WS-TAXA-COMISSAO              PIC S9(03)V99 COMP-3.
       01  WS-COMISSAO-CALC              PIC S9(13)V99 COMP-3.
       01  WS-CTR-PROCESSADOS            PIC 9(07) VALUE ZEROS.
       01  WS-TOTAL-COMISSAO             PIC S9(15)V99 COMP-3 VALUE ZEROS
                                         .

      *  Layout simplificado de saida de comissao
       01  REG-COMISSAO.
           05  COM-FATURA-NUMERO         PIC X(14).
           05  COM-ESTIPULANTE-CNPJ      PIC X(14).
           05  COM-TAXA                  PIC S9(03)V9 COMP-3.
           05  COM-BASE-CALCULO          PIC S9(13)V9 COMP-3.
           05  COM-VALOR                 PIC S9(13)V9 COMP-3.
           05  COM-DATA                  PIC X(08).
           05  COM-STATUS                PIC X(02).
           05  COM-FILLER                PIC X(121).

       COPY CPYCONC.

       PROCEDURE DIVISION.
       0000-PRINCIPAL.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-PROCESSAR UNTIL WS-EOF
           PERFORM 3000-FINALIZAR
           STOP RUN.

       1000-INICIALIZAR.
      *    Taxa de comissao: normalmente viria de tabela DB2 por produto
           MOVE 0.05 TO WS-TAXA-COMISSAO
           OPEN INPUT  ARQ-CONCILIACAO
           OPEN OUTPUT ARQ-COMISSAO
           PERFORM 9100-LER-CONCILIACAO.

       2000-PROCESSAR.
           IF CON-TIPO-HEADER OR CON-TIPO-TRAILER
               PERFORM 9100-LER-CONCILIACAO
           ELSE
               IF CON-OK
                   PERFORM 2100-CALCULAR-COMISSAO
                   ADD 1 TO WS-CTR-PROCESSADOS
                   ADD WS-COMISSAO-CALC TO WS-TOTAL-COMISSAO
               END-IF
               PERFORM 9100-LER-CONCILIACAO
           END-IF.

       2100-CALCULAR-COMISSAO.
           MULTIPLY CON-VALOR-PAGO BY WS-TAXA-COMISSAO
               GIVING WS-COMISSAO-CALC
           MOVE CON-FATURA-NUMERO          TO COM-FATURA-NUMERO
           MOVE WS-TAXA-COMISSAO           TO COM-TAXA
           MOVE CON-VALOR-PAGO             TO COM-BASE-CALCULO
           MOVE WS-COMISSAO-CALC           TO COM-VALOR
           MOVE FUNCTION CURRENT-DATE(1:8) TO COM-DATA
           MOVE 'CA'                       TO COM-STATUS
           WRITE FS-COMISSAO FROM REG-COMISSAO.

       3000-FINALIZAR.
           DISPLAY '*** COMIS01 RELATORIO FINAL ***'
           DISPLAY 'COMISSOES CALCULADAS: ' WS-CTR-PROCESSADOS
           DISPLAY 'TOTAL COMISSAO (R$) : ' WS-TOTAL-COMISSAO
           CLOSE ARQ-CONCILIACAO ARQ-COMISSAO.

       9100-LER-CONCILIACAO.
           READ ARQ-CONCILIACAO INTO REG-CONCILIACAO
           AT END MOVE 'S' TO WS-FIM
           END-READ.
