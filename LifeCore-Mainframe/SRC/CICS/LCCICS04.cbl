      *----------------------------------------------------------------*
      * LCCICS04 - CADASTRO DE ESTIPULANTE NA TABELA DB2 COMPARTILHADA *
      * Transacao LCES. A API web grava na mesma LIFECORE.EMPRESA.    *
      *----------------------------------------------------------------*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LCCICS04.
       AUTHOR. LIFECORE-IQ.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY LCMSET4.

       01  WS-DB2-CODIGO           PIC X(06).
       01  WS-DB2-RAZAO            PIC X(80).
       01  WS-DB2-REDUZIDO         PIC X(30).
       01  WS-DB2-CNPJ             PIC X(14).
       01  WS-DB2-STATUS           PIC X(02).
       01  WS-DB2-INCLUSAO         PIC X(08).
       01  WS-DB2-USUARIO          PIC X(08).
       01  WS-MSG                  PIC X(70) VALUE SPACES.
       01  WS-CURRENT-DATE         PIC X(21).
       01  WS-RESP                 PIC S9(8) COMP.
       01  WS-RESP2                PIC S9(8) COMP.
       01  WS-SQLCODE              PIC S9(9) COMP.

           EXEC SQL INCLUDE SQLCA END-EXEC.

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
           IF EIBCALEN < LENGTH OF DFHCOMMAREA
               EXEC CICS SEND TEXT
                   FROM('Sessao invalida. Acesse pelo menu LifeCore.')
                   LENGTH(49)
                   ERASE
               END-EXEC
               EXEC CICS RETURN END-EXEC
           END-IF

           IF WS-CA-PERFIL NOT = 'A'
               EXEC CICS SEND TEXT
                   FROM('Acesso restrito ao administrador.')
                   LENGTH(34)
                   ERASE
               END-EXEC
               EXEC CICS RETURN END-EXEC
           END-IF

           IF EIBAID = DFHPF3
               EXEC CICS XCTL PROGRAM('LCCICS02')
                   COMMAREA(DFHCOMMAREA)
                   LENGTH(LENGTH OF DFHCOMMAREA)
               END-EXEC
           END-IF

           MOVE SPACES TO LCTESTIPO
           MOVE WS-MSG TO LEMSGO
           IF EIBAID = DFHENTER
               AND WS-CA-RETURN-CODE = 'Y'
               EXEC CICS RECEIVE MAP('LCTESTIP')
                   MAPSET('LCMAPA04')
                   INTO(LCTESTIPI)
               END-EXEC
               MOVE FUNCTION TRIM(LECODI) TO WS-DB2-CODIGO
               MOVE FUNCTION TRIM(LERAZAOI) TO WS-DB2-RAZAO
               MOVE FUNCTION TRIM(LEREDUZI) TO WS-DB2-REDUZIDO
               MOVE FUNCTION TRIM(LECNPJI) TO WS-DB2-CNPJ
               MOVE FUNCTION UPPER-CASE(FUNCTION TRIM(LETIPOI))
                   TO WS-DB2-STATUS
               PERFORM 1000-GRAVAR-DB2
           END-IF

           MOVE 'Y' TO WS-CA-RETURN-CODE
           MOVE WS-MSG TO LEMSGO
           EXEC CICS SEND MAP('LCTESTIP')
               MAPSET('LCMAPA04')
               FROM(LCTESTIPO)
               ERASE
               CURSOR
           END-EXEC
           EXEC CICS RETURN
               TRANSID('LCES')
               COMMAREA(DFHCOMMAREA)
               LENGTH(LENGTH OF DFHCOMMAREA)
           END-EXEC.

       1000-GRAVAR-DB2.
           MOVE SPACES TO WS-MSG
           IF WS-DB2-CODIGO = SPACES
               MOVE 'Informe o codigo da empresa.' TO WS-MSG
               EXIT PARAGRAPH
           END-IF
           IF WS-DB2-RAZAO = SPACES
               MOVE 'Informe a razao social.' TO WS-MSG
               EXIT PARAGRAPH
           END-IF
           IF WS-DB2-CNPJ IS NOT NUMERIC
               OR WS-DB2-STATUS NOT = 'ES'
               MOVE 'Informe CNPJ e tipo ES para estipulante.' TO WS-MSG
               EXIT PARAGRAPH
           END-IF

           MOVE WS-DB2-CODIGO TO LECODO
           MOVE WS-DB2-RAZAO TO LERAZAO
           MOVE WS-DB2-REDUZIDO TO LEREDUZ
           MOVE WS-DB2-CNPJ TO LECNPJ
           MOVE 'ES' TO LETIPO
           MOVE 'AT' TO WS-DB2-STATUS
           MOVE FUNCTION CURRENT-DATE TO WS-CURRENT-DATE
           MOVE WS-CURRENT-DATE(1:8) TO WS-DB2-INCLUSAO
           MOVE WS-CA-USUARIO(1:8) TO WS-DB2-USUARIO

           EXEC SQL
               INSERT INTO LIFECORE.EMPRESA
                   (NR_CODIGO, NM_RAZAO_SOCIAL, NM_NOME_REDUZIDO,
                    CD_CNPJ, TP_EMPRESA, CD_STATUS, DT_INCLUSAO,
                    ID_USUARIO_INCL)
               VALUES
                   (:WS-DB2-CODIGO, :WS-DB2-RAZAO,
                    :WS-DB2-REDUZIDO, :WS-DB2-CNPJ, 'ES',
                    :WS-DB2-STATUS, :WS-DB2-INCLUSAO,
                    :WS-DB2-USUARIO)
           END-EXEC

           IF SQLCODE = 0
               EXEC CICS SYNCPOINT
                   RESP(WS-RESP)
                   RESP2(WS-RESP2)
               END-EXEC
               IF WS-RESP = DFHRESP(NORMAL)
                   MOVE 'Estipulante gravado no DB2 compartilhado.'
                       TO WS-MSG
               ELSE
                   MOVE SQLCODE TO WS-SQLCODE
                   EXEC CICS SYNCPOINT ROLLBACK
                       RESP(WS-RESP)
                       RESP2(WS-RESP2)
                   END-EXEC
                   MOVE 'Falha no COMMIT DB2; cadastro nao confirmado.'
                       TO WS-MSG
               END-IF
           ELSE
               MOVE SQLCODE TO WS-SQLCODE
               EXEC CICS SYNCPOINT ROLLBACK
                   RESP(WS-RESP)
                   RESP2(WS-RESP2)
               END-EXEC
               IF WS-SQLCODE = -803
                   MOVE 'Codigo ou CNPJ ja cadastrado no DB2.'
                       TO WS-MSG
               ELSE
                   MOVE 'Falha DB2 ao gravar. Consulte o suporte.'
                       TO WS-MSG
               END-IF
           END-IF.
