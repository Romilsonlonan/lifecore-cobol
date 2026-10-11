      *----------------------------------------------------------------*
      * LCCICS01 - LIFECORE IQ - PROGRAMA INTERCOMM: LOGIN           *
      * Autor  : LifeCore IQ                                          *
      * Data   : 2026-10-11                                           *
      * Versao : 2.0.0 (adaptado para INTERCOMM Version 9.0)         *
      * Transacao  : LCIN (Subsystem LC, Code IN)                    *
      *                                                               *
      * Fluxo INTERCOMM:                                              *
      *   1. Usuario digita LCIN no terminal 3270                     *
      *   2. INTERCOMM roteia para LCCICS01 (via SYCTTBL)            *
      *   3. Programa exibe tela de login formatada                   *
      *   4. Valida usuario/senha contra tabela interna               *
      *   5. Envia resposta via COBPUT                                *
      *                                                               *
      * Diferenca CICS -> INTERCOMM:                                  *
      *   EXEC CICS SEND/RECEIVE -> COBPUT/INPUT-MESSAGE              *
      *   DFHCOMMAREA           -> SPA-ADDR                           *
      *   EIBAID/EIBCALEN       -> IMESSG-HDR campos                  *
      *----------------------------------------------------------------*
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    LCCICS01.
       AUTHOR.        LIFECORE-IQ.

       ENVIRONMENT DIVISION.

       DATA DIVISION.

       WORKING-STORAGE SECTION.

      *----------------------------------------------------------------*
      * Copybooks INTERCOMM obrigatorios                               *
      *----------------------------------------------------------------*
       01  HEXCODES     COPY ICOMHEXC.
       01  COBREENT-CODES COPY ICOMSBS.

      *----------------------------------------------------------------*
      * Credenciais admin (em producao: consultar tabela DB2)          *
      *----------------------------------------------------------------*
       01  WS-ADMIN-USER           PIC X(10) VALUE 'LCADMIN   '.
       01  WS-ADMIN-PASS           PIC X(10) VALUE 'LC@2026   '.
       01  WS-ESTIP-USER           PIC X(10) VALUE 'TESTE     '.
       01  WS-ESTIP-PASS           PIC X(10) VALUE 'TESTE123  '.

      *----------------------------------------------------------------*
      * Campos de trabalho                                             *
      *----------------------------------------------------------------*
       01  WS-USUARIO              PIC X(10).
       01  WS-SENHA                PIC X(10).
       01  WS-TIPO                 PIC X(01).
       01  WS-MSG                  PIC X(48) VALUE SPACES.
       01  WS-MAX-TENT             PIC 9(01) VALUE 3.

      *----------------------------------------------------------------*
      * Tela de login formatada (80 cols x 24 linhas)                  *
      * O INTERCOMM transmite texto simples ao terminal 3270           *
      *----------------------------------------------------------------*
       01  WS-TELA.
           05  WS-LIN01  PIC X(79)
               VALUE '===========================================================
      -        '=============='           .
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN02  PIC X(44)
               VALUE '   LIFECORE IQ  V2.0  -  LOGIN DO SISTEMA  '            .
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN03  PIC X(79)
               VALUE '-----------------------------------------------------------
      -        '--------------'           .
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN04  PIC X(79) VALUE SPACES.
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN05  PIC X(79) VALUE SPACES.
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN06  PIC X(36)
               VALUE '   Tipo: A=Administrador  E=Estipul '                    .
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN07  PIC X(79) VALUE SPACES.
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN08  PIC X(24) VALUE '   Usuario  : '.
           05  WS-USR-OUT PIC X(10) VALUE SPACES.
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN09  PIC X(14) VALUE '   Senha    : '.
           05  WS-PSW-OUT PIC X(10) VALUE '**********'.
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN10  PIC X(79) VALUE SPACES.
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-MSGOUT PIC X(48) VALUE SPACES.
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN12  PIC X(79) VALUE SPACES.
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN13  PIC X(50)
               VALUE '   Formato: LCIN <TIPO> <USUARIO> <SENHA>'              .
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN14  PIC X(40)
               VALUE '   Exemplo: LCIN A LCADMIN LC@2026     '                .
           05  FILLER    PIC X(01) VALUE X'15'.
           05  WS-LIN15  PIC X(79)
               VALUE '===========================================================
      -        '=============='           .

      *----------------------------------------------------------------*
      * Mensagens de resposta                                          *
      *----------------------------------------------------------------*
       01  WS-MSG-OK      PIC X(48)
           VALUE 'LOGIN OK - BEM-VINDO AO LIFECORE IQ V2.0    '.
       01  WS-MSG-ERR     PIC X(48)
           VALUE 'USUARIO OU SENHA INVALIDOS. TENTE NOVAMENTE.'.
       01  WS-MSG-FMT     PIC X(48)
           VALUE 'FORMATO: LCIN <TIPO> <USUARIO> <SENHA>      '.
       01  WS-MSG-ADMIN   PIC X(48)
           VALUE 'ACESSO ADMIN CONCEDIDO. MODULO PRINCIPAL.   '.
       01  WS-MSG-ESTIP   PIC X(48)
           VALUE 'ACESSO ESTIPULANTE CONCEDIDO. APOLICE:      '.

      *----------------------------------------------------------------*
      * Work area para parsing do input                                *
      *----------------------------------------------------------------*
       01  WS-INPUT-WORK  PIC X(80).
       01  WS-PARSE.
           05  WS-P-VERB  PIC X(04).
           05  FILLER     PIC X(01).
           05  WS-P-TIPO  PIC X(01).
           05  FILLER     PIC X(01).
           05  WS-P-USER  PIC X(10).
           05  FILLER     PIC X(01).
           05  WS-P-PASS  PIC X(10).

       LINKAGE SECTION.

      *----------------------------------------------------------------*
      * INTERCOMM: parametros de entrada obrigatorios                  *
      *----------------------------------------------------------------*
       01  INPUT-MESSAGE COPY ICOMINMG.
           02  INPUT-TEXT.
               05  MSG-INPUT     PIC X(80).

       01  SPA-ADDR      PIC X(04).
       01  SCT-ADDR      PIC X(04).
       01  ICOM-RETURN   PIC S9(07) COMP.

       01  DYNAMIC-WORK-SPACE COPY ICOMDWS.
           02  OUTPUT-TEXT       PIC X(400).

       PROCEDURE DIVISION USING INPUT-MESSAGE
                                SPA-ADDR
                                SCT-ADDR
                                ICOM-RETURN
                                DYNAMIC-WORK-SPACE.

      *----------------------------------------------------------------*
      * 0000-MAIN - ponto de entrada                                   *
      *----------------------------------------------------------------*
       0000-MAIN.
           MOVE +0         TO ICOM-RETURN
           MOVE MSG-INPUT  TO WS-INPUT-WORK
           MOVE WS-INPUT-WORK TO WS-PARSE

      *    Verificar se vieram argumentos (LCIN A USER PASS)
           IF WS-P-USER = SPACES
              PERFORM 1000-EXIBIR-TELA
           ELSE
              PERFORM 2000-VALIDAR-LOGIN
           END-IF

           GOBACK.

      *----------------------------------------------------------------*
      * 1000-EXIBIR-TELA - envia tela de login formatada               *
      *----------------------------------------------------------------*
       1000-EXIBIR-TELA.
           MOVE WS-MSG TO WS-MSGOUT
           MOVE WS-TELA TO OUTPUT-TEXT
           PERFORM 9000-COBPUT-ENVIAR.

      *----------------------------------------------------------------*
      * 2000-VALIDAR-LOGIN - valida usuario e senha                    *
      *----------------------------------------------------------------*
       2000-VALIDAR-LOGIN.
           MOVE FUNCTION UPPER-CASE(WS-P-TIPO)  TO WS-TIPO
           MOVE FUNCTION UPPER-CASE(WS-P-USER)  TO WS-USUARIO
           MOVE FUNCTION UPPER-CASE(WS-P-PASS)  TO WS-SENHA

           EVALUATE WS-TIPO
             WHEN 'A'
               PERFORM 2100-VALIDAR-ADMIN
             WHEN 'E'
               PERFORM 2200-VALIDAR-ESTIP
             WHEN OTHER
               MOVE WS-MSG-FMT  TO WS-MSG
               PERFORM 1000-EXIBIR-TELA
           END-EVALUATE.

      *----------------------------------------------------------------*
      * 2100-VALIDAR-ADMIN                                             *
      *----------------------------------------------------------------*
       2100-VALIDAR-ADMIN.
           IF WS-USUARIO(1:7) = 'LCADMIN'
              AND WS-SENHA(1:7)   = 'LC@2026'
              MOVE WS-MSG-ADMIN  TO OUTPUT-TEXT
              MOVE +0            TO ICOM-RETURN
           ELSE
              MOVE WS-MSG-ERR    TO OUTPUT-TEXT
              MOVE +4            TO ICOM-RETURN
           END-IF
           PERFORM 9000-COBPUT-ENVIAR.

      *----------------------------------------------------------------*
      * 2200-VALIDAR-ESTIP                                             *
      *----------------------------------------------------------------*
       2200-VALIDAR-ESTIP.
           IF WS-USUARIO(1:5) = 'TESTE'
              AND WS-SENHA(1:8)   = 'TESTE123'
              MOVE WS-MSG-ESTIP  TO OUTPUT-TEXT
              MOVE +0            TO ICOM-RETURN
           ELSE
              MOVE WS-MSG-ERR    TO OUTPUT-TEXT
              MOVE +4            TO ICOM-RETURN
           END-IF
           PERFORM 9000-COBPUT-ENVIAR.

      *----------------------------------------------------------------*
      * 9000-COBPUT-ENVIAR - envia mensagem de volta ao terminal       *
      * Equivalente ao EXEC CICS SEND do CICS                         *
      *----------------------------------------------------------------*
       9000-COBPUT-ENVIAR.
           MOVE MESSG-HDR TO OMESSG-HDR
           MOVE OMSGH-RSCH TO OMSGH-SSCH
           MOVE OMSGH-RSC  TO OMSGH-SSC
           CALL 'COBPUT' USING DYNAMIC-WORK-SPACE.
