      *----------------------------------------------------------------*
      * LCCICS10 - CONSULTA DE VIDAS IMPORTADAS POR APOLICE         *
      * Lê IMPORTACAO_VIDAS + IMPORTACAO_VIDAS_ITEM gravados pela   *
      * API FastAPI após importação da planilha.                     *
      * Transacao CICS: LCVD                                        *
      *                                                              *
      * Navegação:                                                  *
      *   ENTER = Consultar por apólice                             *
      *   PF5   = Detalhar lote (informar ID)                       *
      *   PF3   = Voltar ao menu (LCCICS02)                         *
      *----------------------------------------------------------------*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LCCICS10.
       AUTHOR. LIFECORE-IQ.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY LCMSET10.

       01  WS-COMMAREA.
           05  WS-CA-USUARIO       PIC X(10).
           05  WS-CA-PERFIL        PIC X(01).
           05  WS-CA-APOLICE       PIC X(14).
           05  WS-CA-TENTATIVAS    PIC 9(01).
           05  WS-CA-RETURN-CODE   PIC X(02).

       01  WS-NR-APOLICE           PIC X(14).
       01  WS-ID-IMPORTACAO        PIC X(36).
       01  WS-QT-TOTAL             PIC S9(9) COMP.
       01  WS-QT-GRAVADOS          PIC S9(9) COMP.
       01  WS-CD-STATUS            PIC X(02).
       01  WS-DT-IMPORT            PIC X(08).
       01  WS-ID-USUARIO           PIC X(08).
       01  WS-MSG                  PIC X(74) VALUE SPACES.
       01  WS-COUNT-TEXT           PIC Z(8)9.
       01  WS-GRAV-TEXT            PIC Z(8)9.
       01  WS-RESP                 PIC S9(8) COMP.
       01  WS-IDX                  PIC 9(02) COMP VALUE 0.

      *  Item de detalhe (5 linhas na tela)
       01  WS-ROWS.
           05  WS-ROW-ITEM OCCURS 5 TIMES PIC X(73).
       01  WS-ROW                  PIC X(73).
       01  WS-CPF-DISP             PIC X(11).
       01  WS-NOME-DISP            PIC X(24).
       01  WS-SUB-DISP             PIC X(04).
       01  WS-CAP-DISP             PIC X(14).
       01  WS-CAP-NUM              PIC S9(15)V9(2) COMP-3.
       01  WS-CAP-EDIT             PIC ZZZ.ZZZ.ZZZ.ZZ9,99.

           EXEC SQL INCLUDE SQLCA END-EXEC.

      * Cursor: último lote da apólice
           EXEC SQL
               DECLARE C-LOTES CURSOR FOR
               SELECT ID_IMPORTACAO, CD_STATUS, QT_REGISTROS,
                      QT_GRAVADOS, DT_IMPORTACAO, ID_USUARIO
                 FROM LIFECORE.IMPORTACAO_VIDAS
                WHERE NR_APOLICE = :WS-NR-APOLICE
                ORDER BY TS_INCLUSAO DESC
                FETCH FIRST 1 ROWS ONLY
           END-EXEC.

      * Cursor: itens do lote
           EXEC SQL
               DECLARE C-ITENS CURSOR FOR
               SELECT CD_CPF, NM_SEGURADO, CD_SUBESTIPULANTE,
                      VL_CAPITAL
                 FROM LIFECORE.IMPORTACAO_VIDAS_ITEM
                WHERE ID_IMPORTACAO = :WS-ID-IMPORTACAO
                  AND CD_STATUS = 'OK'
                ORDER BY NR_LINHA
                FETCH FIRST 5 ROWS ONLY
           END-EXEC.

       LINKAGE SECTION.
           COPY DFHEIBLK.
       01  DFHCOMMAREA.
           05  WS-CA-USUARIO       PIC X(10).
           05  WS-CA-PERFIL        PIC X(01).
           05  WS-CA-APOLICE       PIC X(14).
           05  WS-CA-TENTATIVAS    PIC 9(01).
           05  WS-CA-RETURN-CODE   PIC X(02).

       PROCEDURE DIVISION USING DFHEIBLK DFHCOMMAREA.

       0000-MAIN.
           IF EIBCALEN = ZERO
               INITIALIZE WS-COMMAREA
               MOVE WS-CA-APOLICE TO WS-NR-APOLICE
           ELSE
               MOVE DFHCOMMAREA TO WS-COMMAREA
               MOVE WS-CA-APOLICE TO WS-NR-APOLICE
           END-IF

           IF EIBAID = DFHPF3
               EXEC CICS XCTL PROGRAM('LCCICS02')
                   COMMAREA(WS-COMMAREA)
                   LENGTH(LENGTH OF WS-COMMAREA)
               END-EXEC
           END-IF

           MOVE SPACES TO LCVDMPAO
           MOVE WS-MSG TO VDMSGO

           IF EIBAID = DFHENTER
               EXEC CICS RECEIVE MAP('LCVDMPA')
                   MAPSET('LCMAPA10')
                   INTO(LCVDMPAI)
               END-EXEC
               IF VDAPOI NOT = SPACES
                   MOVE FUNCTION TRIM(VDAPOI) TO WS-NR-APOLICE
               END-IF
               PERFORM 1000-CONSULTAR-LOTE
           END-IF

           MOVE WS-NR-APOLICE    TO VDAPOO
           MOVE WS-CD-STATUS     TO VDSTO
           MOVE WS-COUNT-TEXT    TO VDTOTO
           MOVE WS-GRAV-TEXT     TO VDGRVO
           MOVE WS-DT-IMPORT     TO VDDATO
           MOVE WS-ROW-ITEM(1)   TO VDROW1O
           MOVE WS-ROW-ITEM(2)   TO VDROW2O
           MOVE WS-ROW-ITEM(3)   TO VDROW3O
           MOVE WS-ROW-ITEM(4)   TO VDROW4O
           MOVE WS-ROW-ITEM(5)   TO VDROW5O
           MOVE WS-MSG           TO VDMSGO

           EXEC CICS SEND MAP('LCVDMPA')
               MAPSET('LCMAPA10')
               FROM(LCVDMPAO)
               ERASE
               CURSOR
           END-EXEC
           EXEC CICS RETURN
               TRANSID('LCVD')
               COMMAREA(WS-COMMAREA)
               LENGTH(LENGTH OF WS-COMMAREA)
           END-EXEC.

       1000-CONSULTAR-LOTE.
           MOVE SPACES TO WS-MSG WS-ROWS WS-CD-STATUS
           MOVE ZERO   TO WS-QT-TOTAL WS-QT-GRAVADOS
                          WS-COUNT-TEXT WS-GRAV-TEXT WS-IDX

           IF WS-NR-APOLICE = SPACES
               MOVE 'Informe o numero da Apolice.' TO WS-MSG
               EXIT PARAGRAPH
           END-IF

           EXEC SQL OPEN C-LOTES END-EXEC
           IF SQLCODE NOT = 0
               MOVE 'Erro ao consultar lotes de importacao.' TO WS-MSG
               EXIT PARAGRAPH
           END-IF

           EXEC SQL
               FETCH C-LOTES
                INTO :WS-ID-IMPORTACAO, :WS-CD-STATUS,
                     :WS-QT-TOTAL, :WS-QT-GRAVADOS,
                     :WS-DT-IMPORT, :WS-ID-USUARIO
           END-EXEC

           EXEC SQL CLOSE C-LOTES END-EXEC

           IF SQLCODE = 100
               MOVE 'Nenhuma importacao encontrada para esta apolice.'
                   TO WS-MSG
               EXIT PARAGRAPH
           END-IF

           IF SQLCODE NOT = 0
               MOVE 'Erro DB2 ao ler lote. Consulte suporte.' TO WS-MSG
               EXIT PARAGRAPH
           END-IF

           MOVE WS-QT-TOTAL    TO WS-COUNT-TEXT
           MOVE WS-QT-GRAVADOS TO WS-GRAV-TEXT

           EXEC SQL OPEN C-ITENS END-EXEC
           IF SQLCODE NOT = 0
               MOVE 'Erro ao abrir itens do lote.' TO WS-MSG
               EXIT PARAGRAPH
           END-IF

           PERFORM UNTIL WS-IDX >= 5
               MOVE SPACES TO WS-CPF-DISP WS-NOME-DISP
                              WS-SUB-DISP WS-CAP-DISP WS-ROW
               EXEC SQL
                   FETCH C-ITENS
                    INTO :WS-CPF-DISP, :WS-NOME-DISP,
                         :WS-SUB-DISP, :WS-CAP-NUM
               END-EXEC
               IF SQLCODE = 100
                   EXIT PERFORM
               END-IF
               IF SQLCODE NOT = 0
                   MOVE 'Erro ao ler itens.' TO WS-MSG
                   EXIT PERFORM
               END-IF
               ADD 1 TO WS-IDX
               MOVE WS-CAP-NUM TO WS-CAP-EDIT
               STRING
                   WS-CPF-DISP  DELIMITED BY SIZE
                   ' '          DELIMITED BY SIZE
                   WS-NOME-DISP(1:24) DELIMITED BY SIZE
                   ' '          DELIMITED BY SIZE
                   WS-SUB-DISP  DELIMITED BY SIZE
                   ' '          DELIMITED BY SIZE
                   WS-CAP-EDIT  DELIMITED BY SIZE
                   INTO WS-ROW
               END-STRING
               MOVE WS-ROW TO WS-ROW-ITEM(WS-IDX)
           END-PERFORM

           EXEC SQL CLOSE C-ITENS END-EXEC

           IF WS-IDX = ZERO AND WS-MSG = SPACES
               MOVE 'Lote sem itens gravados para exibir.' TO WS-MSG
           END-IF.
