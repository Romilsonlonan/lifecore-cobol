      *----------------------------------------------------------------*
      * LCCICS02 - LIFECORE IQ - PROGRAMA CICS: MENU PRINCIPAL        *
      * Autor  : LifeCore IQ                                          *
      * Data   : 2026-10-04                                           *
      * Versao : 1.0.0                                                *
      * Transacao : LCMN                                              *
      *                                                               *
      * Recebe COMMAREA de LCCICS01 com perfil e usuario logado.      *
      * Roteia para o subsistema escolhido via XCTL.                  *
      *----------------------------------------------------------------*
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    LCCICS02.
       AUTHOR.        LIFECORE-IQ.

       ENVIRONMENT DIVISION.

       DATA DIVISION.

       WORKING-STORAGE SECTION.

           COPY LCMSET2.

      *----------------------------------------------------------------*
      * DFHCOMMAREA recebida de LCCICS01                               *
      *----------------------------------------------------------------*
       01  WS-COMMAREA.
           05  WS-CA-USUARIO       PIC X(10).
           05  WS-CA-PERFIL        PIC X(01).
               88 CA-ADMIN         VALUE 'A'.
               88 CA-ESTIP         VALUE 'E'.
           05  WS-CA-APOLICE       PIC X(10).
           05  WS-CA-TENTATIVAS    PIC 9(01).
           05  WS-CA-RETURN-CODE   PIC X(02).

       01  WS-OPCAO                PIC X(01).
       01  WS-MSG                  PIC X(48) VALUE SPACES.

      *----------------------------------------------------------------*
      * Tabela de opcoes x programa CICS destino                       *
      *----------------------------------------------------------------*
       01  WS-OPCOES.
           05 WS-OPC OCCURS 7 TIMES INDEXED BY WS-IDX.
               10  WS-OPC-KEY      PIC X(01).
               10  WS-OPC-PGM      PIC X(08).

       PROCEDURE DIVISION.

       0000-MAIN.

           PERFORM 9000-INIT-OPCOES

           EVALUATE TRUE
             WHEN EIBCALEN = ZERO
               MOVE SPACES TO WS-COMMAREA
               PERFORM 1000-EXIBIR-MENU

             WHEN EIBAID = DFHPF3
               EXEC CICS XCTL PROGRAM('LCCICS01') END-EXEC

             WHEN EIBAID = DFHENTER
               PERFORM 2000-RECEBER-OPCAO
               PERFORM 3000-ROTEAR-OPCAO

             WHEN OTHER
               PERFORM 1000-EXIBIR-MENU
           END-EVALUATE

           EXEC CICS RETURN
               TRANSID('LCMN')
               COMMAREA(WS-COMMAREA)
               LENGTH(LENGTH OF WS-COMMAREA)
           END-EXEC.

           STOP RUN.

      *----------------------------------------------------------------*
      * 1000-EXIBIR-MENU                                               *
      *----------------------------------------------------------------*
       1000-EXIBIR-MENU.

           MOVE SPACES        TO LCTMENUO
           MOVE WS-CA-USUARIO TO LCUNOMEO
           MOVE WS-MSG        TO LCMSGO

           EXEC CICS SEND MAP('LCTMENU')
               MAPSET('LCMAPA02')
               FROM(LCTMENUO)
               ERASE
               CURSOR
           END-EXEC.

      *----------------------------------------------------------------*
      * 2000-RECEBER-OPCAO                                             *
      *----------------------------------------------------------------*
       2000-RECEBER-OPCAO.

           EXEC CICS RECEIVE MAP('LCTMENU')
               MAPSET('LCMAPA02')
               INTO(LCTMENUI)
           END-EXEC

           MOVE FUNCTION UPPER-CASE(LCOPCI) TO WS-OPCAO.

      *----------------------------------------------------------------*
      * 3000-ROTEAR-OPCAO - XCTL para o subsistema escolhido           *
      *----------------------------------------------------------------*
       3000-ROTEAR-OPCAO.

           MOVE SPACES TO WS-MSG

           EVALUATE WS-OPCAO
             WHEN '1'
               EXEC CICS XCTL PROGRAM('LCCICS03')
                   COMMAREA(WS-COMMAREA)
                   LENGTH(LENGTH OF WS-COMMAREA)
               END-EXEC

             WHEN '2'
               EXEC CICS XCTL PROGRAM('LCCICS04')
                   COMMAREA(WS-COMMAREA)
                   LENGTH(LENGTH OF WS-COMMAREA)
               END-EXEC

             WHEN '3'
               EXEC CICS XCTL PROGRAM('LCCICS05')
                   COMMAREA(WS-COMMAREA)
                   LENGTH(LENGTH OF WS-COMMAREA)
               END-EXEC

             WHEN '4'
               EXEC CICS XCTL PROGRAM('LCCICS06')
                   COMMAREA(WS-COMMAREA)
                   LENGTH(LENGTH OF WS-COMMAREA)
               END-EXEC

             WHEN '5'
               EXEC CICS XCTL PROGRAM('LCCICS07')
                   COMMAREA(WS-COMMAREA)
                   LENGTH(LENGTH OF WS-COMMAREA)
               END-EXEC

             WHEN '6'
               EXEC CICS XCTL PROGRAM('LCCICS08')
                   COMMAREA(WS-COMMAREA)
                   LENGTH(LENGTH OF WS-COMMAREA)
               END-EXEC

             WHEN '7'
               EXEC CICS XCTL PROGRAM('LCCICS09')
                   COMMAREA(WS-COMMAREA)
                   LENGTH(LENGTH OF WS-COMMAREA)
               END-EXEC

             WHEN 'X'
               EXEC CICS SEND TEXT
                   FROM('Sessao encerrada. Ate logo.')
                   LENGTH(27)
                   ERASE
               END-EXEC
               EXEC CICS RETURN END-EXEC

             WHEN OTHER
               MOVE 'Opcao invalida. Digite 1 a 6 ou X.' TO WS-MSG
               PERFORM 1000-EXIBIR-MENU
           END-EVALUATE.

      *----------------------------------------------------------------*
      * 9000-INIT-OPCOES - carrega tabela opcao x programa             *
      *----------------------------------------------------------------*
       9000-INIT-OPCOES.

           MOVE '1' TO WS-OPC-KEY(1)
           MOVE 'LCCICS03' TO WS-OPC-PGM(1)
           MOVE '2' TO WS-OPC-KEY(2)
           MOVE 'LCCICS04' TO WS-OPC-PGM(2)
           MOVE '3' TO WS-OPC-KEY(3)
           MOVE 'LCCICS05' TO WS-OPC-PGM(3)
           MOVE '4' TO WS-OPC-KEY(4)
           MOVE 'LCCICS06' TO WS-OPC-PGM(4)
           MOVE '5' TO WS-OPC-KEY(5)
           MOVE 'LCCICS07' TO WS-OPC-PGM(5)
           MOVE '6' TO WS-OPC-KEY(6)
           MOVE 'LCCICS08' TO WS-OPC-PGM(6)
           MOVE '7' TO WS-OPC-KEY(7)
           MOVE 'LCCICS09' TO WS-OPC-PGM(7).
