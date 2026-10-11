      *----------------------------------------------------------------*
      * LCCICS09 - CONSULTA DE LOTES DE CADASTRO INICIAL NO DB2       *
      * Le as mesmas tabelas gravadas pela API FastAPI.                *
      * Transacao CICS: LCIM                                           *
      *----------------------------------------------------------------*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LCCICS09.
       AUTHOR. LIFECORE-IQ.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY LCMSET9.

       01  WS-COMMAREA.
           05  WS-CA-USUARIO       PIC X(10).
           05  WS-CA-PERFIL        PIC X(01).
           05  WS-CA-APOLICE       PIC X(10).
           05  WS-CA-TENTATIVAS    PIC 9(01).
           05  WS-CA-RETURN-CODE   PIC X(02).
       01  WS-IMPORT-ID            PIC X(36).
       01  WS-STATUS               PIC X(02).
       01  WS-TOTAL                PIC S9(9) COMP.
       01  WS-LINHA                PIC S9(9) COMP.
       01  WS-LINHA-TEXT           PIC Z(8)9.
       01  WS-SUB                  PIC X(10).
       01  WS-MODULO               PIC X(10).
       01  WS-NOME                 PIC X(24).
       01  WS-CPF                  PIC X(20).
       01  WS-ITEM-STATUS          PIC X(02).
       01  WS-ROW                  PIC X(73).
       01  WS-ROWS.
           05 WS-ROW-ITEM OCCURS 5 TIMES PIC X(73).
       01  WS-IDX                  PIC 9(01) COMP VALUE 0.
       01  WS-COUNT-TEXT           PIC Z(8)9.
       01  WS-MSG                  PIC X(74) VALUE SPACES.
       01  WS-RESP                 PIC S9(8) COMP.
       01  WS-RESP2                PIC S9(8) COMP.
       01  WS-SQLCODE              PIC S9(9) COMP.

           EXEC SQL INCLUDE SQLCA END-EXEC.

           EXEC SQL
               DECLARE C-IMPORT-ITEMS CURSOR FOR
               SELECT NR_LINHA, CD_SUBESTIPULANTE, CD_MODULO,
                      NM_SEGURADO, CD_CPF, CD_STATUS
                 FROM LIFECORE.IMPORTACAO_INICIAL_ITEM
                WHERE ID_IMPORTACAO = :WS-IMPORT-ID
                ORDER BY NR_LINHA
           END-EXEC.

       LINKAGE SECTION.
           COPY DFHEIBLK.
       01  DFHCOMMAREA.
           05  WS-CA-USUARIO       PIC X(10).
           05  WS-CA-PERFIL        PIC X(01).
           05  WS-CA-APOLICE       PIC X(10).
           05  WS-CA-TENTATIVAS    PIC 9(01).
           05  WS-CA-RETURN-CODE   PIC X(02).

       PROCEDURE DIVISION USING DFHEIBLK DFHCOMMAREA.

       0000-MAIN.
           IF EIBCALEN = ZERO
               INITIALIZE WS-COMMAREA
           ELSE
               MOVE DFHCOMMAREA TO WS-COMMAREA
           END-IF

           IF WS-CA-PERFIL NOT = 'A'
               EXEC CICS SEND TEXT
                   FROM('Consulta restrita ao administrador.')
                   LENGTH(37)
                   ERASE
               END-EXEC
               EXEC CICS RETURN END-EXEC
           END-IF

           IF EIBAID = DFHPF3
               EXEC CICS XCTL PROGRAM('LCCICS02')
                   COMMAREA(WS-COMMAREA)
                   LENGTH(LENGTH OF WS-COMMAREA)
               END-EXEC
           END-IF

           MOVE SPACES TO LCTIMPAO
           MOVE WS-MSG TO IMPMSGO
           IF EIBAID = DFHENTER
               EXEC CICS RECEIVE MAP('LCTIMPA')
                   MAPSET('LCMAPA09')
                   INTO(LCTIMPAI)
               END-EXEC
               MOVE FUNCTION TRIM(IMPIDI) TO WS-IMPORT-ID
               PERFORM 1000-CONSULTAR-DB2
           END-IF

           MOVE WS-IMPORT-ID TO IMPIDO
           MOVE WS-STATUS TO IMPSTO
           MOVE WS-COUNT-TEXT TO IMPTOTO
           MOVE WS-ROW-ITEM(1) TO IMPR01O
           MOVE WS-ROW-ITEM(2) TO IMPR02O
           MOVE WS-ROW-ITEM(3) TO IMPR03O
           MOVE WS-ROW-ITEM(4) TO IMPR04O
           MOVE WS-ROW-ITEM(5) TO IMPR05O
           MOVE WS-MSG TO IMPMSGO

           EXEC CICS SEND MAP('LCTIMPA')
               MAPSET('LCMAPA09')
               FROM(LCTIMPAO)
               ERASE
               CURSOR
           END-EXEC
           EXEC CICS RETURN
               TRANSID('LCIM')
               COMMAREA(WS-COMMAREA)
               LENGTH(LENGTH OF WS-COMMAREA)
           END-EXEC.

       1000-CONSULTAR-DB2.
           MOVE SPACES TO WS-MSG WS-STATUS WS-ROWS
           MOVE ZERO TO WS-TOTAL WS-COUNT-TEXT WS-IDX
           IF WS-IMPORT-ID = SPACES
               MOVE 'Informe o ID da importacao.' TO WS-MSG
               EXIT PARAGRAPH
           END-IF

           EXEC SQL
               SELECT CD_STATUS, QT_REGISTROS
                 INTO :WS-STATUS, :WS-TOTAL
                 FROM LIFECORE.IMPORTACAO_INICIAL
                WHERE ID_IMPORTACAO = :WS-IMPORT-ID
           END-EXEC

           IF SQLCODE = 100
               MOVE 'Lote nao encontrado no DB2.' TO WS-MSG
               EXIT PARAGRAPH
           ELSE
               IF SQLCODE NOT = 0
                   MOVE 'Erro DB2. Consulte o suporte.' TO WS-MSG
                   EXIT PARAGRAPH
               END-IF
           END-IF

           MOVE WS-TOTAL TO WS-COUNT-TEXT
           EXEC SQL OPEN C-IMPORT-ITEMS END-EXEC
           IF SQLCODE NOT = 0
               MOVE 'Falha ao abrir consulta de itens no DB2.' TO WS-MSG
               EXIT PARAGRAPH
           END-IF

           PERFORM UNTIL WS-IDX >= 5
               MOVE SPACES TO WS-SUB WS-MODULO WS-NOME WS-CPF
               EXEC SQL
                   FETCH C-IMPORT-ITEMS
                    INTO :WS-LINHA, :WS-SUB, :WS-MODULO,
                         :WS-NOME, :WS-CPF, :WS-ITEM-STATUS
               END-EXEC
               IF SQLCODE = 100
                   EXIT PERFORM
               END-IF
               IF SQLCODE NOT = 0
                   MOVE 'Erro ao ler itens do lote no DB2.' TO WS-MSG
                   EXIT PERFORM
               END-IF
               ADD 1 TO WS-IDX
               MOVE WS-LINHA TO WS-LINHA-TEXT
               MOVE SPACES TO WS-ROW
               STRING
                   WS-LINHA-TEXT DELIMITED BY SIZE
                   ' ' DELIMITED BY SIZE
                   WS-SUB(1:8) DELIMITED BY SIZE
                   ' ' DELIMITED BY SIZE
                   WS-MODULO(1:8) DELIMITED BY SIZE
                   ' ' DELIMITED BY SIZE
                   WS-NOME(1:24) DELIMITED BY SIZE
                   ' ' DELIMITED BY SIZE
                   WS-CPF(1:11) DELIMITED BY SIZE
                   ' ' DELIMITED BY SIZE
                   WS-ITEM-STATUS DELIMITED BY SIZE
                   INTO WS-ROW
               END-STRING
               MOVE WS-ROW TO WS-ROW-ITEM(WS-IDX)
           END-PERFORM
           EXEC SQL CLOSE C-IMPORT-ITEMS END-EXEC
           IF WS-IDX = ZERO AND WS-MSG = SPACES
               MOVE 'Lote sem itens para exibir.' TO WS-MSG
           END-IF.
