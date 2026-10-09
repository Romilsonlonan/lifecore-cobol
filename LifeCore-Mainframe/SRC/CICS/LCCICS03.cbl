      *----------------------------------------------------------------*
      * LCCICS03 - LIFECORE IQ - PROGRAMA CICS: CONSULTA DE APOLICES  *
      * Autor  : LifeCore IQ                                          *
      * Data   : 2026-10-04                                           *
      * Versao : 1.0.0                                                *
      * Transacao : LCAP                                              *
      *                                                               *
      * Funcionalidades:                                               *
      *   - Pesquisa por Nr. Apolice ou CNPJ                          *
      *   - Exibe dados da apolice + lista de segurados                *
      *   - PF7/PF8: paginacao de segurados                           *
      *   - PF3: retorna ao menu                                       *
      *                                                               *
      * Nota: usa EXEC CICS READ/STARTBR para acessar VSAM KSDS       *
      *       Dataset: LIFECORE.VSAM.APOLICE  Key: NR_APOLICE(10)     *
      *----------------------------------------------------------------*
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    LCCICS03.
       AUTHOR.        LIFECORE-IQ.

       ENVIRONMENT DIVISION.

       DATA DIVISION.

       WORKING-STORAGE SECTION.

           COPY LCMSET3.

      *----------------------------------------------------------------*
      * COMMAREA recebida do menu                                      *
      *----------------------------------------------------------------*
       01  WS-COMMAREA.
           05  WS-CA-USUARIO       PIC X(10).
           05  WS-CA-PERFIL        PIC X(01).
               88 CA-ADMIN         VALUE 'A'.
               88 CA-ESTIP         VALUE 'E'.
           05  WS-CA-APOLICE       PIC X(10).
           05  WS-CA-TENTATIVAS    PIC 9(01).
           05  WS-CA-RETURN-CODE   PIC X(02).

      *----------------------------------------------------------------*
      * Layout do registro VSAM de APOLICE (CPYAPOL)                  *
      *----------------------------------------------------------------*
       01  WS-APOLICE-REC.
           05  WS-NR-APOLICE       PIC X(10).
           05  WS-NM-EMPRESA       PIC X(40).
           05  WS-NR-CNPJ          PIC X(14).
           05  WS-CD-PRODUTO       PIC X(30).
           05  WS-DT-INI-VIG       PIC X(10).
           05  WS-DT-FIM-VIG       PIC X(10).
           05  WS-VL-CAPITAL       PIC S9(13)V99 COMP-3.
           05  WS-VL-PREMIO        PIC S9(13)V99 COMP-3.
           05  WS-CD-STATUS        PIC X(02).

      *----------------------------------------------------------------*
      * Layout do registro VSAM de SEGURADO (CPYCOBT)                 *
      *----------------------------------------------------------------*
       01  WS-SEGURADO-REC.
           05  WS-SG-APOLICE       PIC X(10).
           05  WS-SG-CPF           PIC X(11).
           05  WS-SG-NOME          PIC X(30).
           05  WS-SG-COBERTURA     PIC X(06).
           05  WS-SG-STATUS        PIC X(02).

      *----------------------------------------------------------------*
      * Campos de trabalho                                             *
      *----------------------------------------------------------------*
       01  WS-MSG                  PIC X(70) VALUE SPACES.
       01  WS-NR-APOL-PESQ         PIC X(10).
       01  WS-CNPJ-PESQ            PIC X(14).
       01  WS-VL-CAP-ED            PIC ZZ,ZZZ,ZZZ,ZZ9.99.
       01  WS-VL-PREM-ED           PIC ZZ,ZZZ,ZZZ,ZZ9.99.
       01  WS-QTD                  PIC ZZZ99.
       01  WS-CTR                  PIC 9(03) VALUE 0.
       01  WS-LINHA-WRK            PIC X(70).

      *----------------------------------------------------------------*
      * Condicao de fim de arquivo VSAM                                *
      *----------------------------------------------------------------*
       01  WS-VSAM-RESP            PIC S9(08) COMP.
       88  VSAM-OK                 VALUE 0.
       88  VSAM-NOTFND             VALUE 13.
       88  VSAM-ENDFILE            VALUE 10.

       PROCEDURE DIVISION.

       0000-MAIN.

           EVALUATE TRUE
             WHEN EIBCALEN = ZERO
               MOVE SPACES TO WS-COMMAREA
               MOVE SPACES TO WS-NR-APOL-PESQ
               PERFORM 1000-EXIBIR-TELA

             WHEN EIBAID = DFHPF3
               EXEC CICS XCTL PROGRAM('LCCICS02')
                   COMMAREA(WS-COMMAREA)
                   LENGTH(LENGTH OF WS-COMMAREA)
               END-EXEC

             WHEN EIBAID = DFHENTER
               PERFORM 2000-RECEBER-PESQUISA
               PERFORM 3000-CONSULTAR-APOLICE

             WHEN OTHER
               PERFORM 1000-EXIBIR-TELA
           END-EVALUATE

           EXEC CICS RETURN
               TRANSID('LCAP')
               COMMAREA(WS-COMMAREA)
               LENGTH(LENGTH OF WS-COMMAREA)
           END-EXEC.

           STOP RUN.

      *----------------------------------------------------------------*
      * 1000-EXIBIR-TELA                                               *
      *----------------------------------------------------------------*
       1000-EXIBIR-TELA.

           MOVE SPACES  TO LCTAPOLO
           MOVE WS-MSG  TO LCMSGO

           EXEC CICS SEND MAP('LCTAPOL')
               MAPSET('LCMAPA03')
               FROM(LCTAPOLO)
               ERASE
               CURSOR
           END-EXEC.

      *----------------------------------------------------------------*
      * 2000-RECEBER-PESQUISA                                          *
      *----------------------------------------------------------------*
       2000-RECEBER-PESQUISA.

           EXEC CICS RECEIVE MAP('LCTAPOL')
               MAPSET('LCMAPA03')
               INTO(LCTAPOLI)
           END-EXEC

           MOVE FUNCTION TRIM(LCNRAPOI) TO WS-NR-APOL-PESQ
           MOVE FUNCTION TRIM(LCCNPJI)  TO WS-CNPJ-PESQ.

      *----------------------------------------------------------------*
      * 3000-CONSULTAR-APOLICE - le VSAM e popula o mapa               *
      *----------------------------------------------------------------*
       3000-CONSULTAR-APOLICE.

           MOVE SPACES TO WS-MSG

           IF WS-NR-APOL-PESQ = SPACES AND WS-CNPJ-PESQ = SPACES
               MOVE 'Informe o Nr. da Apolice ou o CNPJ.' TO WS-MSG
               PERFORM 1000-EXIBIR-TELA
               GO TO 3000-FIM
           END-IF

      *    Leitura direta por chave no VSAM KSDS
           EXEC CICS READ
               FILE('LCAPOLVC')
               INTO(WS-APOLICE-REC)
               RIDFLD(WS-NR-APOL-PESQ)
               RESP(WS-VSAM-RESP)
           END-EXEC

           IF VSAM-NOTFND
               MOVE 'Apolice nao encontrada.' TO WS-MSG
               PERFORM 1000-EXIBIR-TELA
               GO TO 3000-FIM
           END-IF

           IF NOT VSAM-OK
               MOVE 'Erro ao acessar base de dados.' TO WS-MSG
               PERFORM 1000-EXIBIR-TELA
               GO TO 3000-FIM
           END-IF

      *    Popula campos do mapa com dados da apolice
           MOVE WS-NR-APOLICE   TO LCNRAPOO
           MOVE WS-NM-EMPRESA   TO LCEMPNMO
           MOVE WS-NR-CNPJ      TO LCCNPJO
           MOVE WS-CD-PRODUTO   TO LCPRODO
           MOVE WS-DT-INI-VIG   TO LCDTINIO
           MOVE WS-DT-FIM-VIG   TO LCDTFIMO
           MOVE WS-CD-STATUS    TO LCSTATUSO

           MOVE WS-VL-CAPITAL TO WS-VL-CAP-ED
           MOVE WS-VL-CAP-ED  TO LCCAPO
           MOVE WS-VL-PREMIO  TO WS-VL-PREM-ED
           MOVE WS-VL-PREM-ED TO LCPREMIO

      *    Leitura de segurados (Browse por prefixo de chave)
           MOVE 0 TO WS-CTR
           PERFORM 4000-LER-SEGURADOS

           MOVE WS-CTR TO WS-QTD
           MOVE WS-QTD TO LCQTDO
           MOVE WS-MSG TO LCMSGO

           EXEC CICS SEND MAP('LCTAPOL')
               MAPSET('LCMAPA03')
               FROM(LCTAPOLO)
               ERASE
           END-EXEC.

       3000-FIM.
           EXIT.

      *----------------------------------------------------------------*
      * 4000-LER-SEGURADOS - browse no VSAM de coberturas              *
      *----------------------------------------------------------------*
       4000-LER-SEGURADOS.

           MOVE WS-NR-APOL-PESQ TO WS-SG-APOLICE

           EXEC CICS STARTBR
               FILE('LCCOBTVC')
               RIDFLD(WS-SG-APOLICE)
               RESP(WS-VSAM-RESP)
           END-EXEC

           IF NOT VSAM-OK
               MOVE 'Nenhum segurado encontrado.' TO WS-MSG
               GO TO 4000-FIM
           END-IF

           PERFORM UNTIL VSAM-ENDFILE OR WS-CTR > 5

               EXEC CICS READNEXT
                   FILE('LCCOBTVC')
                   INTO(WS-SEGURADO-REC)
                   RIDFLD(WS-SG-APOLICE)
                   RESP(WS-VSAM-RESP)
               END-EXEC

               IF VSAM-ENDFILE
                   GO TO 4000-ENDBR
               END-IF

               IF WS-SG-APOLICE NOT = WS-NR-APOL-PESQ
                   GO TO 4000-ENDBR
               END-IF

               ADD 1 TO WS-CTR

               STRING
                   WS-SG-CPF       DELIMITED SIZE
                   ' '             DELIMITED SIZE
                   WS-SG-NOME      DELIMITED SIZE
                   ' '             DELIMITED SIZE
                   WS-SG-COBERTURA DELIMITED SIZE
                   ' '             DELIMITED SIZE
                   WS-SG-STATUS    DELIMITED SIZE
                   INTO WS-LINHA-WRK
               END-STRING

               EVALUATE WS-CTR
                 WHEN 1  MOVE WS-LINHA-WRK TO LCLINHA1O
                 WHEN 2  MOVE WS-LINHA-WRK TO LCLINHA2O
                 WHEN 3  MOVE WS-LINHA-WRK TO LCLINHA3O
                 WHEN 4  MOVE WS-LINHA-WRK TO LCLINHA4O
                 WHEN 5  MOVE WS-LINHA-WRK TO LCLINHA5O
               END-EVALUATE

           END-PERFORM.

       4000-ENDBR.
           EXEC CICS ENDBR FILE('LCCOBTVC') END-EXEC.

       4000-FIM.
           EXIT.
