      *================================================================*
      * PROGRAMA : LCCANCEL                                           *
      * SISTEMA  : LIFECORE IQ — Gestão de Seguros                   *
      * FUNÇÃO   : Lê PORTAL_EMPRESAS_UPD.dat e aplica cancelamentos/ *
      *            suspensões na tabela DB2 EMPRESA e no VSAM         *
      *            LIFECORE.VSAM.APOLICE.                             *
      *                                                               *
      * ENTRADAS :                                                    *
      *   DD UPDFILE  — PORTAL_EMPRESAS_UPD.dat (128 bytes/reg)       *
      *   DD VSAMIN   — LIFECORE.VSAM.APOLICE (KSDS — entrada/saída) *
      * SAÍDAS   :                                                    *
      *   DD SYSPRINT — Relatório de processamento                    *
      *   DB2         — UPDATE LIFECORE.EMPRESA                       *
      *                                                               *
      * LAYOUT UPDFILE (128 bytes):                                   *
      *   Col  1-10  : NR_APOLICE  (CHAR 10)                         *
      *   Col 11-40  : NM_CAMPO    (CHAR 30)                         *
      *   Col 41-120 : DS_VALOR    (CHAR 80)                         *
      *   Col 121-128: DT_REGISTRO (CHAR 8  — AAAAMMDD)              *
      *                                                               *
      * RETURN CODES:                                                 *
      *   0  — Sucesso total                                          *
      *   4  — Processado com avisos (registros ignorados)            *
      *   8  — Erro grave em DB2                                      *
      *  12  — Erro de I/O no arquivo de entrada                      *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LCCANCEL.
       AUTHOR.     LIFECORE-IQ.
       DATE-WRITTEN. 2025.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-ZOS.
       OBJECT-COMPUTER. IBM-ZOS.

       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT UPDFILE ASSIGN TO DD-UPDFILE
               ORGANIZATION IS SEQUENTIAL
               ACCESS MODE  IS SEQUENTIAL
               FILE STATUS  IS WS-FILE-STATUS.

           SELECT VSMFILE ASSIGN TO DD-VSAMIN
               ORGANIZATION IS INDEXED
               ACCESS MODE  IS DYNAMIC
               RECORD KEY   IS VSM-NR-APOLICE
               FILE STATUS  IS WS-VSM-STATUS.

       DATA DIVISION.
       FILE SECTION.

      *-- Arquivo de atualizações exportado pelo Portal --
       FD  UPDFILE
           RECORDING MODE IS F
           BLOCK CONTAINS 0 RECORDS
           RECORD CONTAINS 128 CHARACTERS.
       01  UPD-REGISTRO.
           05  UPD-NR-APOLICE   PIC X(10).
           05  UPD-NM-CAMPO     PIC X(30).
           05  UPD-DS-VALOR     PIC X(80).
           05  UPD-DT-REGISTRO  PIC X(8).

      *-- VSAM KSDS de apólices (layout CPYAPOL) --
       FD  VSMFILE.
       01  VSM-REGISTRO.
           COPY CPYAPOL.

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS       PIC X(2)  VALUE '00'.
       01  WS-VSM-STATUS        PIC X(2)  VALUE '00'.
       01  WS-EOF               PIC X     VALUE 'N'.
       01  WS-RC                PIC S9(4) COMP VALUE 0.

       01  WS-COUNTERS.
           05  WS-TOT-LIDOS     PIC 9(7)  VALUE 0.
           05  WS-TOT-CANCEL    PIC 9(7)  VALUE 0.
           05  WS-TOT-SUSPEN    PIC 9(7)  VALUE 0.
           05  WS-TOT-REAT      PIC 9(7)  VALUE 0.
           05  WS-TOT-ERROS     PIC 9(7)  VALUE 0.
           05  WS-TOT-IGNOR     PIC 9(7)  VALUE 0.

      *-- Campos SQL HOST VARIABLES --
       01  HV-CD-EMPRESA        PIC S9(9)  COMP.
       01  HV-CD-STATUS         PIC X(2).
       01  HV-DT-CANCEL         PIC X(8).
       01  HV-DS-MOTIVO         PIC X(200).
       01  HV-DT-INI-SUS        PIC X(8).
       01  HV-DT-FIM-SUS        PIC X(8).
       01  HV-ID-USUARIO        PIC X(8)   VALUE 'LCCANCEL'.
       01  HV-NR-APOLICE        PIC X(10).

           EXEC SQL
               INCLUDE SQLCA
           END-EXEC.

           EXEC SQL
               INCLUDE CPYSQLCA
           END-EXEC.

       PROCEDURE DIVISION.

      *================================================================
       0000-PRINCIPAL.
      *================================================================
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-PROCESSAR UNTIL WS-EOF = 'S'
           PERFORM 9000-FINALIZAR
           STOP RUN.

      *================================================================
       1000-INICIALIZAR.
      *================================================================
           OPEN INPUT  UPDFILE
           OPEN I-O    VSMFILE
           IF WS-FILE-STATUS NOT = '00'
               DISPLAY '*** LCCANCEL: ERRO AO ABRIR UPDFILE '
                        WS-FILE-STATUS
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF
           DISPLAY '*** LCCANCEL: INICIADO — PROCESSANDO CANCELAMENTOS'
           READ UPDFILE INTO UPD-REGISTRO
               AT END MOVE 'S' TO WS-EOF
           END-READ.

      *================================================================
       2000-PROCESSAR.
      *================================================================
           ADD 1 TO WS-TOT-LIDOS
           EVALUATE UPD-NM-CAMPO
               WHEN 'cd_status'
                   PERFORM 3000-ATUALIZAR-STATUS
               WHEN OTHER
                   ADD 1 TO WS-TOT-IGNOR
           END-EVALUATE
           READ UPDFILE INTO UPD-REGISTRO
               AT END MOVE 'S' TO WS-EOF
           END-READ.

      *================================================================
       3000-ATUALIZAR-STATUS.
      *================================================================
           MOVE FUNCTION TRIM(UPD-NR-APOLICE)
               TO HV-NR-APOLICE
           MOVE FUNCTION TRIM(UPD-DS-VALOR(1:2))
               TO HV-CD-STATUS

           PERFORM 3100-BUSCAR-EMPRESA-DB2
           IF HV-CD-EMPRESA = 0
               ADD 1 TO WS-TOT-ERROS
               DISPLAY '*** LCCANCEL: EMPRESA NAO ENCONTRADA — '
                        HV-NR-APOLICE
               EXIT PARAGRAPH
           END-IF

           EVALUATE HV-CD-STATUS
               WHEN 'CA'
                   PERFORM 3200-CANCELAR-EMPRESA
               WHEN 'SU'
                   PERFORM 3300-SUSPENDER-EMPRESA
               WHEN 'AT'
                   PERFORM 3400-REATIVAR-EMPRESA
               WHEN OTHER
                   ADD 1 TO WS-TOT-IGNOR
                   DISPLAY '*** LCCANCEL: STATUS DESCONHECIDO '
                            HV-CD-STATUS ' — ' HV-NR-APOLICE
           END-EVALUATE

           PERFORM 3500-ATUALIZAR-VSAM.

      *================================================================
       3100-BUSCAR-EMPRESA-DB2.
      *================================================================
           MOVE ZERO TO HV-CD-EMPRESA
           EXEC SQL
               SELECT CD_EMPRESA
               INTO   :HV-CD-EMPRESA
               FROM   LIFECORE.EMPRESA E
               INNER JOIN LIFECORE.APOLICE A
                   ON A.CD_ESTIPULANTE = E.CD_EMPRESA
               WHERE  A.NR_APOLICE = :HV-NR-APOLICE
               FETCH FIRST 1 ROW ONLY
           END-EXEC
           IF SQLCODE NOT = 0 AND SQLCODE NOT = 100
               DISPLAY '*** LCCANCEL: SQLCODE=' SQLCODE
                        ' NR_APOLICE=' HV-NR-APOLICE
               MOVE ZERO TO HV-CD-EMPRESA
           END-IF.

      *================================================================
       3200-CANCELAR-EMPRESA.
      *================================================================
           MOVE UPD-DT-REGISTRO TO HV-DT-CANCEL
           MOVE 'Cancelado via Portal LifeCore IQ'
               TO HV-DS-MOTIVO
           EXEC SQL
               UPDATE LIFECORE.EMPRESA
               SET    CD_STATUS              = 'CA',
                      DT_CANCELAMENTO        = :HV-DT-CANCEL,
                      DS_MOTIVO_CANCELAMENTO = :HV-DS-MOTIVO,
                      ID_USUARIO_CANCEL      = :HV-ID-USUARIO,
                      TS_ALTERACAO           = CURRENT TIMESTAMP
               WHERE  CD_EMPRESA = :HV-CD-EMPRESA
           END-EXEC
           EVALUATE TRUE
               WHEN SQLCODE = 0
                   ADD 1 TO WS-TOT-CANCEL
               WHEN OTHER
                   ADD 1 TO WS-TOT-ERROS
                   MOVE 8 TO WS-RC
                   DISPLAY '*** LCCANCEL: ERRO CANCEL SQLCODE='
                            SQLCODE ' EMPRESA=' HV-CD-EMPRESA
           END-EVALUATE.

      *================================================================
       3300-SUSPENDER-EMPRESA.
      *================================================================
           MOVE UPD-DT-REGISTRO TO HV-DT-INI-SUS
           MOVE SPACES           TO HV-DT-FIM-SUS
           MOVE 'Suspenso via Portal LifeCore IQ'
               TO HV-DS-MOTIVO
           EXEC SQL
               UPDATE LIFECORE.EMPRESA
               SET    CD_STATUS          = 'SU',
                      DT_INICIO_SUSPENSAO = :HV-DT-INI-SUS,
                      DT_FIM_SUSPENSAO    = :HV-DT-FIM-SUS,
                      DS_MOTIVO_SUSPENSAO = :HV-DS-MOTIVO,
                      ID_USUARIO_CANCEL   = :HV-ID-USUARIO,
                      TS_ALTERACAO        = CURRENT TIMESTAMP
               WHERE  CD_EMPRESA = :HV-CD-EMPRESA
           END-EXEC
           EVALUATE TRUE
               WHEN SQLCODE = 0
                   ADD 1 TO WS-TOT-SUSPEN
               WHEN OTHER
                   ADD 1 TO WS-TOT-ERROS
                   MOVE 8 TO WS-RC
                   DISPLAY '*** LCCANCEL: ERRO SUSPEN SQLCODE='
                            SQLCODE ' EMPRESA=' HV-CD-EMPRESA
           END-EVALUATE.

      *================================================================
       3400-REATIVAR-EMPRESA.
      *================================================================
           EXEC SQL
               UPDATE LIFECORE.EMPRESA
               SET    CD_STATUS           = 'AT',
                      DT_FIM_SUSPENSAO    = CURRENT DATE,
                      ID_USUARIO_CANCEL   = :HV-ID-USUARIO,
                      TS_ALTERACAO        = CURRENT TIMESTAMP
               WHERE  CD_EMPRESA = :HV-CD-EMPRESA
               AND    CD_STATUS   = 'SU'
           END-EXEC
           EVALUATE TRUE
               WHEN SQLCODE = 0
                   ADD 1 TO WS-TOT-REAT
               WHEN SQLCODE = 100
                   ADD 1 TO WS-TOT-IGNOR  *> não estava suspensa
               WHEN OTHER
                   ADD 1 TO WS-TOT-ERROS
                   MOVE 8 TO WS-RC
                   DISPLAY '*** LCCANCEL: ERRO REATIV SQLCODE='
                            SQLCODE ' EMPRESA=' HV-CD-EMPRESA
           END-EVALUATE.

      *================================================================
       3500-ATUALIZAR-VSAM.
      *================================================================
      *    Atualiza o campo APO-STATUS no VSAM KSDS correspondente.
           MOVE HV-NR-APOLICE TO VSM-NR-APOLICE
           READ VSMFILE INTO VSM-REGISTRO KEY IS VSM-NR-APOLICE
               INVALID KEY
                   DISPLAY '*** LCCANCEL: VSAM NAO ENCONTRADO — '
                            HV-NR-APOLICE
                   EXIT PARAGRAPH
           END-READ
           MOVE HV-CD-STATUS TO APO-STATUS
           REWRITE VSM-REGISTRO FROM VSM-REGISTRO
           IF WS-VSM-STATUS NOT = '00'
               DISPLAY '*** LCCANCEL: ERRO REWRITE VSAM '
                        WS-VSM-STATUS ' APO=' HV-NR-APOLICE
           END-IF.

      *================================================================
       9000-FINALIZAR.
      *================================================================
           CLOSE UPDFILE
           CLOSE VSMFILE
           DISPLAY '*** LCCANCEL: PROCESSAMENTO CONCLUIDO'
           DISPLAY '    REGISTROS LIDOS    : ' WS-TOT-LIDOS
           DISPLAY '    CANCELAMENTOS      : ' WS-TOT-CANCEL
           DISPLAY '    SUSPENSOES         : ' WS-TOT-SUSPEN
           DISPLAY '    REATIVACOES        : ' WS-TOT-REAT
           DISPLAY '    IGNORADOS          : ' WS-TOT-IGNOR
           DISPLAY '    ERROS              : ' WS-TOT-ERROS
           MOVE WS-RC TO RETURN-CODE.
