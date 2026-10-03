      *================================================================*
      * PROGRAMA  : ARQVAL01                                          *
      * DESCRICAO : Validacao do Arquivo de Apolices                  *
      *             Registros invalidos → arquivo de quarentena        *
      * PROJETO   : LifeCore-Mainframe                                *
      * RC  0 = sucesso sem erros                                     *
      * RC  4 = avisos (erros nao criticos encontrados)               *
      * RC  8 = erros criticos encontrados                            *
      * RC 12 = erro de I/O ou arquivo ausente                        *
      *================================================================*
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ARQVAL01.
       AUTHOR.     LIFECORE-TEAM.
       DATE-WRITTEN. 2025-01-01.

       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ARQ-ENTRADA
               ASSIGN TO 'LIFECORE.DATA.INPUT.APOLICE'
               ORGANIZATION IS SEQUENTIAL
               ACCESS MODE  IS SEQUENTIAL
               FILE STATUS  IS WS-FS-ENTRADA.

           SELECT ARQ-SAIDA-OK
               ASSIGN TO 'LIFECORE.DATA.OUTPUT.APOLICE'
               ORGANIZATION IS SEQUENTIAL
               ACCESS MODE  IS SEQUENTIAL
               FILE STATUS  IS WS-FS-SAIDA-OK.

           SELECT ARQ-QUARENTENA
               ASSIGN TO 'LIFECORE.DATA.QUARANTINE.APOLICE'
               ORGANIZATION IS SEQUENTIAL
               ACCESS MODE  IS SEQUENTIAL
               FILE STATUS  IS WS-FS-QUARENTENA.

       DATA DIVISION.
       FILE SECTION.
       FD  ARQ-ENTRADA
           RECORD CONTAINS 300 CHARACTERS
           BLOCK CONTAINS 0 RECORDS
           RECORDING MODE IS F.
       01  FS-ENTRADA                    PIC X(300).

       FD  ARQ-SAIDA-OK
           RECORD CONTAINS 300 CHARACTERS
           RECORDING MODE IS F.
       01  FS-SAIDA-OK                   PIC X(300).

       FD  ARQ-QUARENTENA
           RECORD CONTAINS 180 CHARACTERS
           RECORDING MODE IS F.
       01  FS-QUARENTENA                 PIC X(180).

       WORKING-STORAGE SECTION.
       01  WS-FILE-STATUS.
           05  WS-FS-ENTRADA             PIC X(02).
           05  WS-FS-SAIDA-OK            PIC X(02).
           05  WS-FS-QUARENTENA          PIC X(02).

       01  WS-CONTADORES.
           05  WS-CTR-LIDOS              PIC 9(07) VALUE ZEROS.
           05  WS-CTR-VALIDOS            PIC 9(07) VALUE ZEROS.
           05  WS-CTR-ERROS              PIC 9(07) VALUE ZEROS.
           05  WS-CTR-AVISOS             PIC 9(07) VALUE ZEROS.

       01  WS-FLAGS.
           05  WS-FIM-ARQUIVO            PIC X(01) VALUE 'N'.
               88  WS-EOF                VALUE 'S'.
           05  WS-REG-INVALIDO           PIC X(01) VALUE 'N'.
               88  WS-INVALIDO           VALUE 'S'.
           05  WS-RETURN-CODE            PIC 9(02) VALUE ZEROS.

       01  WS-VALIDACAO.
           05  WS-CPF-CALC               PIC 9(11) VALUE ZEROS.
           05  WS-CPF-DIGIT1             PIC 9(02) VALUE ZEROS.
           05  WS-CPF-DIGIT2             PIC 9(02) VALUE ZEROS.
           05  WS-CPF-SOMA               PIC 9(05) VALUE ZEROS.
           05  WS-CPF-RESTO              PIC 9(02) VALUE ZEROS.
           05  WS-IDX                    PIC 9(02) VALUE ZEROS.

       01  WS-CPF-TAB.
           05  WS-CPF-DIG  OCCURS 11 TIMES PIC 9(01).

       COPY CPYAPOL.
       COPY CPYERRO.

       PROCEDURE DIVISION.
       0000-PRINCIPAL.
           PERFORM 1000-INICIALIZAR
           PERFORM 2000-PROCESSAR UNTIL WS-EOF
           PERFORM 3000-FINALIZAR
           STOP RUN.

       1000-INICIALIZAR.
           OPEN INPUT  ARQ-ENTRADA
           OPEN OUTPUT ARQ-SAIDA-OK
           OPEN OUTPUT ARQ-QUARENTENA
           IF WS-FS-ENTRADA NOT EQUAL '00'
               DISPLAY 'ARQVAL01 E00001-IO ERRO ABERTURA ENTRADA: '
                        WS-FS-ENTRADA
               MOVE 12 TO RETURN-CODE
               STOP RUN
           END-IF
           PERFORM 2100-LER-REGISTRO.

       2000-PROCESSAR.
           IF APO-TIPO-HEADER
               PERFORM 2100-LER-REGISTRO
           ELSE IF APO-TIPO-TRAILER
               MOVE 'S' TO WS-FIM-ARQUIVO
           ELSE
               PERFORM 2200-VALIDAR-REGISTRO
               IF WS-INVALIDO
                   ADD 1 TO WS-CTR-ERROS
                   PERFORM 2400-GRAVAR-QUARENTENA
               ELSE
                   ADD 1 TO WS-CTR-VALIDOS
                   WRITE FS-SAIDA-OK FROM FS-ENTRADA
               END-IF
               PERFORM 2100-LER-REGISTRO
           END-IF.

       2100-LER-REGISTRO.
           READ ARQ-ENTRADA INTO REG-APOLICE
           AT END MOVE 'S' TO WS-FIM-ARQUIVO
           END-READ
           IF WS-FS-ENTRADA EQUAL '00'
               ADD 1 TO WS-CTR-LIDOS.

       2200-VALIDAR-REGISTRO.
           MOVE 'N' TO WS-REG-INVALIDO
           PERFORM 2210-VALIDAR-CPF
           PERFORM 2220-VALIDAR-PRODUTO
           PERFORM 2230-VALIDAR-CAPITAL
           PERFORM 2240-VALIDAR-VIGENCIA.

       2210-VALIDAR-CPF.
           IF APO-SEGURADO-CPF EQUAL SPACES OR LOW-VALUES
               MOVE 'S' TO WS-REG-INVALIDO
               MOVE 'E00001' TO ERR-CODIGO-ERRO
               MOVE 'CPF DO SEGURADO AUSENTE OU INVALIDO'
                   TO ERR-DESCRICAO
           END-IF.

       2220-VALIDAR-PRODUTO.
           IF NOT (APO-PRODUTO-VGC OR APO-PRODUTO-GLB)
               MOVE 'S' TO WS-REG-INVALIDO
               MOVE 'E00003' TO ERR-CODIGO-ERRO
               MOVE 'PRODUTO INVALIDO - ESPERADO VGC OU GLB'
                   TO ERR-DESCRICAO
           END-IF.

       2230-VALIDAR-CAPITAL.
           IF APO-CAPITAL-SEGURADO EQUAL ZEROS
               MOVE 'S' TO WS-REG-INVALIDO
               MOVE 'E00003' TO ERR-CODIGO-ERRO
               MOVE 'CAPITAL SEGURADO ZERO OU AUSENTE'
                   TO ERR-DESCRICAO
           END-IF.

       2240-VALIDAR-VIGENCIA.
           IF APO-VIGENCIA-INI EQUAL SPACES
               OR APO-VIGENCIA-FIM EQUAL SPACES
               MOVE 'S' TO WS-REG-INVALIDO
               MOVE 'E00004' TO ERR-CODIGO-ERRO
               MOVE 'VIGENCIA INVALIDA OU AUSENTE'
                   TO ERR-DESCRICAO
           END-IF.

       2400-GRAVAR-QUARENTENA.
           MOVE 'D1'        TO ERR-TIPO-REGISTRO
           MOVE 'ARQVAL01'  TO ERR-PROGRAMA-ORIGEM
           MOVE APO-NUMERO  TO ERR-CHAVE-REGISTRO
           MOVE 'E'         TO ERR-SEVERIDADE
           WRITE FS-QUARENTENA FROM REG-ERRO.

       3000-FINALIZAR.
      *----------------------------------------------------------------*
      * Relatorio JSON emitido via DISPLAY — consumido pela            *
      * Integration Layer (FastAPI/resultados.py) que parseia o        *
      * SYSOUT do programa. Padrao adaptado do FOLHA.CBL/MONTA-JSON.   *
      *----------------------------------------------------------------*
           DISPLAY '{'
           DISPLAY '  "programa": "ARQVAL01",'
           DISPLAY '  "dataHora": "'
                   FUNCTION CURRENT-DATE(1:8)
                   '",'
           DISPLAY '  "totalLidos"  : ' WS-CTR-LIDOS   ','
           DISPLAY '  "totalValidos": ' WS-CTR-VALIDOS  ','
           DISPLAY '  "totalErros"  : ' WS-CTR-ERROS    ','
           DISPLAY '  "totalAvisos" : ' WS-CTR-AVISOS   ','
           IF WS-CTR-ERROS > ZEROS
               DISPLAY '  "status": "ERRO"'
               MOVE 8 TO RETURN-CODE
           ELSE IF WS-CTR-AVISOS > ZEROS
               DISPLAY '  "status": "AVISO"'
               MOVE 4 TO RETURN-CODE
           ELSE
               DISPLAY '  "status": "OK"'
               MOVE 0 TO RETURN-CODE
           END-IF
           DISPLAY '}'
           CLOSE ARQ-ENTRADA ARQ-SAIDA-OK ARQ-QUARENTENA.
