      *================================================================*
      * PROGRAMA  : CLEAR01                                           *
      * DESCRICAO : Leitura do Arquivo de Clearing da Bandeira        *
      *             Gera base para liquidacao e conciliacao de cartao *
      * PROJETO   : LifeCore-Mainframe                                *
      * FLUXO     : CAPTURA → COMPENSACAO (clearing) → LIQUIDACAO     *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLEAR01.
       AUTHOR.     LIFECORE-TEAM.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ARQ-CLEARING
               ASSIGN TO 'LIFECORE.DATA.INPUT.CLEARING'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-CLR.
           SELECT ARQ-CLEARING-OUT
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.CLEARING'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-OUT.

       DATA DIVISION.
       FILE SECTION.
       FD  ARQ-CLEARING     RECORD CONTAINS 300 CHARACTERS.
       01  FS-CLEARING                   PIC X(300).
       FD  ARQ-CLEARING-OUT RECORD CONTAINS 300 CHARACTERS.
       01  FS-CLEARING-OUT               PIC X(300).

       WORKING-STORAGE SECTION.
       01  WS-FS-CLR                     PIC X(02).
       01  WS-FS-OUT                     PIC X(02).
       01  WS-FIM                        PIC X(01) VALUE 'N'.
           88  WS-EOF                    VALUE 'S'.
       01  WS-CTR-LIDOS                  PIC 9(07) VALUE ZEROS.
       01  WS-CTR-ACEITOS                PIC 9(07) VALUE ZEROS.
       01  WS-CTR-REJEITADOS             PIC 9(07) VALUE ZEROS.

       COPY CPYCLR.

       PROCEDURE DIVISION.
       0000-PRINCIPAL.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-PROCESSAR UNTIL WS-EOF
           PERFORM 3000-FINALIZAR
           STOP RUN.

       1000-INICIALIZAR.
           OPEN INPUT  ARQ-CLEARING
           OPEN OUTPUT ARQ-CLEARING-OUT
           PERFORM 9100-LER.

       2000-PROCESSAR.
           IF CLR-HEADER OR CLR-TRAILER
               PERFORM 9100-LER
           ELSE
               ADD 1 TO WS-CTR-LIDOS
               IF CLR-APROVADO AND (CLR-VENDA OR CLR-ESTORNO)
                   ADD 1 TO WS-CTR-ACEITOS
                   WRITE FS-CLEARING-OUT FROM REG-CLEARING
               ELSE
                   ADD 1 TO WS-CTR-REJEITADOS
                   DISPLAY 'CLEAR01 REGISTRO REJEITADO NSU='
                            CLR-NSU ' STATUS=' CLR-STATUS
               END-IF
               PERFORM 9100-LER
           END-IF.

       3000-FINALIZAR.
           DISPLAY '*** CLEAR01 RELATORIO FINAL ***'
           DISPLAY 'LIDOS     : ' WS-CTR-LIDOS
           DISPLAY 'ACEITOS   : ' WS-CTR-ACEITOS
           DISPLAY 'REJEITADOS: ' WS-CTR-REJEITADOS
           CLOSE ARQ-CLEARING ARQ-CLEARING-OUT.

       9100-LER.
           READ ARQ-CLEARING INTO REG-CLEARING
           AT END MOVE 'S' TO WS-FIM
           END-READ.
