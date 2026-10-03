      *================================================================*
      * PROGRAMA  : FATURA01                                          *
      * DESCRICAO : Geracao de Faturamento por Estipulante            *
      *             Agrupa apolices ativas por CNPJ e gera fatura     *
      * PROJETO   : LifeCore-Mainframe                                *
      * DB2 PLAN  : LCFATPL                                           *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. FATURA01.
       AUTHOR.     LIFECORE-TEAM.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ARQ-APOLICE
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.APOLICE'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-APO.
           SELECT ARQ-FATURA
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.FATURA'
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS  IS WS-FS-FAT.

       DATA DIVISION.
       FILE SECTION.
       FD  ARQ-APOLICE RECORD CONTAINS 300 CHARACTERS.
       01  FS-APOLICE                    PIC X(300).
       FD  ARQ-FATURA  RECORD CONTAINS 250 CHARACTERS.
       01  FS-FATURA                     PIC X(250).

       WORKING-STORAGE SECTION.
       01  WS-FS-APO                     PIC X(02).
       01  WS-FS-FAT                     PIC X(02).
       01  WS-FIM                        PIC X(01) VALUE 'N'.
           88  WS-EOF                    VALUE 'S'.
       01  WS-CNPJ-ANTERIOR              PIC X(14) VALUE SPACES.
       01  WS-CTR-APOLICES               PIC 9(06) VALUE ZEROS.
       01  WS-TOTAL-BRUTO                PIC S9(13)V9 COMP-3 VALUE 0
                                         .
       01  WS-TOTAL-LIQUIDO              PIC S9(13)V9 COMP-3 VALUE 0
                                         .
       01  WS-FATURA-SEQ                 PIC 9(10) VALUE ZEROS.
       01  WS-DATA-HOJE                  PIC X(08).
       01  WS-DATA-VENC                  PIC X(08).

       COPY CPYSQLCA.
       COPY CPYAPOL.
       COPY CPYFATU.

       PROCEDURE DIVISION.
       0000-PRINCIPAL.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-PROCESSAR UNTIL WS-EOF
           PERFORM 2900-GRAVAR-ULTIMA-FATURA
           PERFORM 3000-FINALIZAR
           STOP RUN.

       1000-INICIALIZAR.
           MOVE FUNCTION CURRENT-DATE(1:8) TO WS-DATA-HOJE
           OPEN INPUT  ARQ-APOLICE
           OPEN OUTPUT ARQ-FATURA
           PERFORM 9100-LER-APOLICE.

       2000-PROCESSAR.
           IF APO-TIPO-HEADER OR APO-TIPO-TRAILER
               PERFORM 9100-LER-APOLICE
           ELSE
               IF NOT APO-ATIVO
                   PERFORM 9100-LER-APOLICE
               ELSE
                   IF APO-ESTIPULANTE-CNPJ NOT EQUAL WS-CNPJ-ANTERIOR
                       IF WS-CNPJ-ANTERIOR NOT EQUAL SPACES
                           PERFORM 2800-GRAVAR-FATURA
                       END-IF
                       PERFORM 2100-INICIAR-FATURA
                   END-IF
                   PERFORM 2200-ACUMULAR-VALORES
                   PERFORM 9100-LER-APOLICE
               END-IF
           END-IF.

       2100-INICIAR-FATURA.
           INITIALIZE REG-FATURA
           ADD 1 TO WS-FATURA-SEQ
           MOVE 'D1'                   TO FAT-TIPO-REGISTRO
           MOVE APO-ESTIPULANTE-CNPJ   TO FAT-ESTIPULANTE-CNPJ
           MOVE WS-FATURA-SEQ          TO FAT-NUMERO
           MOVE WS-DATA-HOJE           TO FAT-DATA-EMISSAO
           MOVE 'PE'                   TO FAT-STATUS
           MOVE ZEROS                  TO WS-CTR-APOLICES
                                          WS-TOTAL-BRUTO
                                          WS-TOTAL-LIQUIDO
           MOVE APO-ESTIPULANTE-CNPJ   TO WS-CNPJ-ANTERIOR.

       2200-ACUMULAR-VALORES.
           ADD 1               TO WS-CTR-APOLICES
           ADD APO-PREMIO-BRUTO  TO WS-TOTAL-BRUTO
           ADD APO-PREMIO-LIQUIDO TO WS-TOTAL-LIQUIDO.

       2800-GRAVAR-FATURA.
           MOVE WS-CTR-APOLICES  TO FAT-QTD-APOLICES
           MOVE WS-TOTAL-BRUTO   TO FAT-VALOR-BRUTO
           MOVE WS-TOTAL-LIQUIDO TO FAT-VALOR-LIQUIDO
           PERFORM 9200-INSERT-FATURA-DB2
           WRITE FS-FATURA FROM REG-FATURA.

       2900-GRAVAR-ULTIMA-FATURA.
           IF WS-CNPJ-ANTERIOR NOT EQUAL SPACES
               PERFORM 2800-GRAVAR-FATURA.

       3000-FINALIZAR.
           CLOSE ARQ-APOLICE ARQ-FATURA.

       9100-LER-APOLICE.
           READ ARQ-APOLICE INTO REG-APOLICE
           AT END MOVE 'S' TO WS-FIM
           END-READ.

       9200-INSERT-FATURA-DB2.
      *    DB2 (z/OS): descomente o EXEC SQL apos BIND com LCFATPL
      *        EXEC SQL
      *            INSERT INTO FATURA (
      *                NR_FATURA, CD_CNPJ_ESTIPULANTE, DT_EMISSAO,
      *                VL_BRUTO, VL_LIQUIDO, QT_APOLICES, CD_STATUS
      *            ) VALUES (
      *                :FAT-NUMERO, :FAT-ESTIPULANTE-CNPJ,
      *                :FAT-DATA-EMISSAO, :FAT-VALOR-BRUTO,
      *                :FAT-VALOR-LIQUIDO, :FAT-QTD-APOLICES,
      *                :FAT-STATUS
      *            )
      *        END-EXEC
           DISPLAY 'FATURA01 INSERT FAT=' FAT-NUMERO.
