      *================================================================*
      * PROGRAMA  : SETTLE01                                          *
      * DESCRICAO : Conciliacao da Liquidacao com Agenda de Recebiveis*
      *             Match entre clearing da bandeira e agenda bancos  *
      * PROJETO   : LifeCore-Mainframe                                *
      * FLUXO     : CLEARING → LIQUIDACAO → CONCILIACAO FINANCEIRA    *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SETTLE01.
       AUTHOR.     LIFECORE-TEAM.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ARQ-CLEARING
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.CLEARING'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-CLR.
           SELECT ARQ-AGENDA
               ASSIGN TO 'LIFECORE.DATA.INPUT.AGENDA'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-AGD.
           SELECT ARQ-LIQUIDACAO
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.LIQUIDACAO'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-LIQ.

       DATA DIVISION.
       FILE SECTION.
       FD  ARQ-CLEARING   RECORD CONTAINS 300 CHARACTERS.
       01  FS-CLEARING                   PIC X(300).
       FD  ARQ-AGENDA     RECORD CONTAINS 300 CHARACTERS.
       01  FS-AGENDA                     PIC X(300).
       FD  ARQ-LIQUIDACAO  RECORD CONTAINS 300 CHARACTERS.
       01  FS-LIQUIDACAO                 PIC X(300).

       WORKING-STORAGE SECTION.
       01  WS-FS-CLR                     PIC X(02).
       01  WS-FS-AGD                     PIC X(02).
       01  WS-FS-LIQ                     PIC X(02).
       01  WS-FIM-CLR                    PIC X(01) VALUE 'N'.
           88  WS-EOF-CLR                VALUE 'S'.
       01  WS-FIM-AGD                    PIC X(01) VALUE 'N'.
           88  WS-EOF-AGD                VALUE 'S'.
       01  WS-CTR-CONCILIADOS            PIC 9(07) VALUE ZEROS.
       01  WS-CTR-NAO-ENCONTRADO         PIC 9(07) VALUE ZEROS.
       01  WS-TOLERANCIA                 PIC S9(09)V9 COMP-3 VALUE 0
                                         .

       COPY CPYCLR.

      *    Layout da agenda de recebiveis (banco / adquirente)
       01  REG-AGENDA.
           05  AGD-TIPO-REGISTRO         PIC X(02).
           05  AGD-NSU                   PIC X(12).
           05  AGD-DATA-CREDITO          PIC X(08).
           05  AGD-VALOR                 PIC S9(13)V9 COMP-3.
           05  AGD-BANCO                 PIC X(08).
           05  AGD-ADQUIRENTE            PIC X(08).
           05  AGD-STATUS                PIC X(02).
               88  AGD-CREDITO-OK        VALUE 'CR'.
               88  AGD-PENDENTE          VALUE 'PE'.
           05  AGD-FILLER                PIC X(259).

       COPY CPYLIQ.

       PROCEDURE DIVISION.
       0000-PRINCIPAL.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-PROCESSAR
           PERFORM 3000-FINALIZAR
           STOP RUN.

       1000-INICIALIZAR.
           OPEN INPUT  ARQ-CLEARING
           OPEN INPUT  ARQ-AGENDA
           OPEN OUTPUT ARQ-LIQUIDACAO
           PERFORM 9100-LER-CLEARING
           PERFORM 9200-LER-AGENDA.

       2000-PROCESSAR.
           PERFORM UNTIL WS-EOF-CLR
               INITIALIZE REG-LIQUIDACAO
               MOVE CLR-NSU          TO LIQ-NSU
               MOVE CLR-DATA-CLEARING TO LIQ-DATA-CLEARING
               MOVE CLR-VALOR-LIQUIDO TO LIQ-VALOR-CLEARING
               PERFORM 2100-BUSCAR-AGENDA
               WRITE FS-LIQUIDACAO FROM REG-LIQUIDACAO
               PERFORM 9100-LER-CLEARING
           END-PERFORM.

       2100-BUSCAR-AGENDA.
           PERFORM UNTIL WS-EOF-AGD OR AGD-NSU >= CLR-NSU
               PERFORM 9200-LER-AGENDA
           END-PERFORM
           IF NOT WS-EOF-AGD AND AGD-NSU EQUAL CLR-NSU
               MOVE AGD-DATA-CREDITO  TO LIQ-DATA-CREDITO
               MOVE AGD-VALOR         TO LIQ-VALOR-AGENDA
               MOVE AGD-BANCO         TO LIQ-BANCO
               SUBTRACT CLR-VALOR-LIQUIDO FROM AGD-VALOR
                   GIVING LIQ-DIFERENCA
               IF LIQ-DIFERENCA >= -1
                   AND LIQ-DIFERENCA <= 1
                   MOVE 'LQ' TO LIQ-STATUS
                   ADD 1 TO WS-CTR-CONCILIADOS
               ELSE
                   MOVE 'DV' TO LIQ-STATUS
               END-IF
           ELSE
               MOVE 'NE' TO LIQ-STATUS
               ADD 1 TO WS-CTR-NAO-ENCONTRADO
           END-IF.

       3000-FINALIZAR.
           DISPLAY '*** SETTLE01 RELATORIO FINAL ***'
           DISPLAY 'LIQUIDADOS   : ' WS-CTR-CONCILIADOS
           DISPLAY 'NAO ENCONTR  : ' WS-CTR-NAO-ENCONTRADO
           CLOSE ARQ-CLEARING ARQ-AGENDA ARQ-LIQUIDACAO.

       9100-LER-CLEARING.
           READ ARQ-CLEARING INTO REG-CLEARING
           AT END MOVE 'S' TO WS-FIM-CLR
           NOT AT END
               IF CLR-HEADER OR CLR-TRAILER
                   PERFORM 9100-LER-CLEARING
               END-IF
           END-READ.

       9200-LER-AGENDA.
           READ ARQ-AGENDA INTO REG-AGENDA
           AT END MOVE 'S' TO WS-FIM-AGD
           NOT AT END
               IF AGD-TIPO-REGISTRO EQUAL 'H0'
                   OR AGD-TIPO-REGISTRO EQUAL 'T9'
                   PERFORM 9200-LER-AGENDA
               END-IF
           END-READ.
