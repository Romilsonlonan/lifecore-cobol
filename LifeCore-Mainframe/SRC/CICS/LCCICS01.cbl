      *----------------------------------------------------------------*
      * LCCICS01 - LIFECORE IQ - PROGRAMA CICS: CONTROLE DE LOGIN    *
      * Autor  : LifeCore IQ                                          *
      * Data   : 2026-10-04                                           *
      * Versao : 1.0.0                                                *
      * Transacao : LCIN                                              *
      *                                                               *
      * Fluxo:                                                        *
      *   1. Exibe tela de login (LCMAPA01/LCTLOGIN)                  *
      *   2. Valida usuario/senha                                     *
      *   3. Se OK => XCTL para LCCICS02 (Menu Principal)            *
      *   4. Se Erro => reexibe com mensagem                          *
      *----------------------------------------------------------------*
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    LCCICS01.
       AUTHOR.        LIFECORE-IQ.

       ENVIRONMENT DIVISION.

       DATA DIVISION.

       WORKING-STORAGE SECTION.

      *----------------------------------------------------------------*
      * Copybook do mapa BMS gerado pelo assembler                     *
      *----------------------------------------------------------------*
           COPY LCMSET1.

      *----------------------------------------------------------------*
      * DFHCOMMAREA - area de comunicacao entre transacoes CICS        *
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
      * Credenciais admin (em producao: consultar tabela DB2)          *
      *----------------------------------------------------------------*
       01  WS-ADMIN-USER           PIC X(10) VALUE 'LCADMIN'.
       01  WS-ADMIN-PASS           PIC X(10) VALUE 'LC@2026'.

      *----------------------------------------------------------------*
      * Campos de trabalho                                             *
      *----------------------------------------------------------------*
       01  WS-EIBAID-SAVE          PIC X(01).
       01  WS-MAX-TENT             PIC 9(01) VALUE 3.
       01  WS-MSG                  PIC X(48) VALUE SPACES.
       01  WS-TIPO                 PIC X(01).
       01  WS-USER                 PIC X(10).
       01  WS-PASS                 PIC X(10).
       01  WS-APOL                 PIC X(10).

      *----------------------------------------------------------------*
      * Stub de usuario Estipulante (futuramente DB2 SELECT)           *
      *----------------------------------------------------------------*
       01  WS-ESTIP-USER           PIC X(10) VALUE 'TESTE     '.
       01  WS-ESTIP-PASS           PIC X(10) VALUE 'TESTE123  '.
       01  WS-ESTIP-APOL           PIC X(10) VALUE '0000000001'.

       PROCEDURE DIVISION.

      *----------------------------------------------------------------*
      * MAIN - ponto de entrada                                        *
      *----------------------------------------------------------------*
       0000-MAIN.

           EVALUATE TRUE
             WHEN EIBCALEN = ZERO
      *          Primeira vez: inicializa COMMAREA e exibe tela
               MOVE SPACES TO WS-COMMAREA
               MOVE 0      TO WS-CA-TENTATIVAS
               PERFORM 1000-EXIBIR-TELA

             WHEN EIBAID = DFHPF3
      *          PF3: encerrar transacao
               EXEC CICS SEND TEXT
                   FROM('Saindo do LifeCore IQ...')
                   LENGTH(24)
                   ERASE
               END-EXEC
               EXEC CICS RETURN END-EXEC

             WHEN EIBAID = DFHENTER
      *          ENTER: processar login
               PERFORM 2000-RECEBER-DADOS
               PERFORM 3000-VALIDAR-LOGIN

             WHEN OTHER
               PERFORM 1000-EXIBIR-TELA
           END-EVALUATE

           EXEC CICS RETURN
               TRANSID('LCIN')
               COMMAREA(WS-COMMAREA)
               LENGTH(LENGTH OF WS-COMMAREA)
           END-EXEC.

           STOP RUN.

      *----------------------------------------------------------------*
      * 1000-EXIBIR-TELA - envia mapa de login para o terminal         *
      *----------------------------------------------------------------*
       1000-EXIBIR-TELA.

           MOVE SPACES  TO LCTLOGINO
           MOVE WS-MSG  TO LCMSGO

           EXEC CICS SEND MAP('LCTLOGIN')
               MAPSET('LCMAPA01')
               FROM(LCTLOGINO)
               ERASE
               CURSOR
           END-EXEC.

      *----------------------------------------------------------------*
      * 2000-RECEBER-DADOS - le campos do mapa preenchido              *
      *----------------------------------------------------------------*
       2000-RECEBER-DADOS.

           EXEC CICS RECEIVE MAP('LCTLOGIN')
               MAPSET('LCMAPA01')
               INTO(LCTLOGINI)
           END-EXEC

           MOVE FUNCTION UPPER-CASE(LCTIPOI)  TO WS-TIPO
           MOVE FUNCTION TRIM(LCUSERI)         TO WS-USER
           MOVE FUNCTION TRIM(LCSENHALI)       TO WS-PASS
           MOVE FUNCTION TRIM(LCAPOLI)         TO WS-APOL.

      *----------------------------------------------------------------*
      * 3000-VALIDAR-LOGIN - autentica e decide proximo passo          *
      *----------------------------------------------------------------*
       3000-VALIDAR-LOGIN.

           MOVE SPACES TO WS-MSG

      *    Valida tipo de acesso
           IF WS-TIPO NOT = 'A' AND WS-TIPO NOT = 'E'
               MOVE 'Tipo invalido: A=Administrador E=Estipulante'
                   TO WS-MSG
               PERFORM 1000-EXIBIR-TELA
               GO TO 3000-FIM
           END-IF

      *    Valida usuario obrigatorio
           IF WS-USER = SPACES
               MOVE 'Informe o usuario.' TO WS-MSG
               PERFORM 1000-EXIBIR-TELA
               GO TO 3000-FIM
           END-IF

      *    Valida senha obrigatoria
           IF WS-PASS = SPACES
               MOVE 'Informe a senha.' TO WS-MSG
               PERFORM 1000-EXIBIR-TELA
               GO TO 3000-FIM
           END-IF

      *    Autenticacao ADMIN
           IF WS-TIPO = 'A'
               IF WS-USER = WS-ADMIN-USER
                  AND WS-PASS = WS-ADMIN-PASS
                   MOVE WS-USER TO WS-CA-USUARIO
                   MOVE 'A'     TO WS-CA-PERFIL
                   MOVE SPACES  TO WS-CA-APOLICE
                   EXEC CICS XCTL PROGRAM('LCCICS02')
                       COMMAREA(WS-COMMAREA)
                       LENGTH(LENGTH OF WS-COMMAREA)
                   END-EXEC
               ELSE
                   ADD 1 TO WS-CA-TENTATIVAS
                   IF WS-CA-TENTATIVAS >= WS-MAX-TENT
                       EXEC CICS SEND TEXT
                           FROM('ACESSO BLOQUEADO - Max tentativas.')
                           LENGTH(34)
                           ERASE
                       END-EXEC
                       EXEC CICS RETURN END-EXEC
                   END-IF
                   MOVE 'Usuario ou senha invalidos.' TO WS-MSG
                   PERFORM 1000-EXIBIR-TELA
               END-IF
               GO TO 3000-FIM
           END-IF

      *    Validacao ESTIPULANTE: apolice obrigatoria
           IF WS-TIPO = 'E' AND WS-APOL = SPACES
               MOVE 'Informe o numero da Apolice.' TO WS-MSG
               PERFORM 1000-EXIBIR-TELA
               GO TO 3000-FIM
           END-IF

      *    Autenticacao ESTIPULANTE (stub - futuramente DB2)
           IF WS-TIPO = 'E'
               IF WS-USER = WS-ESTIP-USER
                  AND WS-PASS = WS-ESTIP-PASS
                  AND WS-APOL = WS-ESTIP-APOL
                   MOVE WS-USER TO WS-CA-USUARIO
                   MOVE 'E'     TO WS-CA-PERFIL
                   MOVE WS-APOL TO WS-CA-APOLICE
                   EXEC CICS XCTL PROGRAM('LCCICS02')
                       COMMAREA(WS-COMMAREA)
                       LENGTH(LENGTH OF WS-COMMAREA)
                   END-EXEC
               ELSE
                   ADD 1 TO WS-CA-TENTATIVAS
                   IF WS-CA-TENTATIVAS >= WS-MAX-TENT
                       EXEC CICS SEND TEXT
                           FROM('ACESSO BLOQUEADO - Max tentativas.')
                           LENGTH(34)
                           ERASE
                       END-EXEC
                       EXEC CICS RETURN END-EXEC
                   END-IF
                   MOVE 'Apolice, usuario ou senha invalidos.' TO WS-MSG
                   PERFORM 1000-EXIBIR-TELA
               END-IF
           END-IF

       3000-FIM.
           EXIT.
