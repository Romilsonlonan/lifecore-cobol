      *================================================================*
      * COPYBOOK : CPYERRO                                            *
      * DESCRICAO: Layout de Registro de Quarentena / Erro            *
      * PROJETO  : LifeCore-Mainframe                                 *
      * VERSAO   : 1.0.0                                              *
      * TAMANHO  : 180 bytes                                          *
      *================================================================*
       01  REG-ERRO.
           05  ERR-TIPO-REGISTRO         PIC X(02).
               88  ERR-TIPO-HEADER       VALUE 'H0'.
               88  ERR-TIPO-DETALHE      VALUE 'D1'.
               88  ERR-TIPO-TRAILER      VALUE 'T9'.
           05  ERR-NUMERO-SEQUENCIAL     PIC 9(08)    COMP-3.
           05  ERR-PROGRAMA-ORIGEM       PIC X(08).
           05  ERR-STEP-JCL              PIC X(08).
           05  ERR-DATA-HORA             PIC X(26).
           05  ERR-CODIGO-ERRO           PIC X(07).
      *       Codigos: E00001=CPF invalido, E00002=CNPJ invalido
      *                E00003=Capital zero, E00004=Vigencia invalida
      *                E00005=COMP-3 corrompido, E00006=Duplicado
      *                E00007=Apolice inexistente, E00008=Fatura inexist
           05  ERR-SEVERIDADE            PIC X(01).
               88  ERR-AVISO             VALUE 'W'.
               88  ERR-ERRO              VALUE 'E'.
               88  ERR-CRITICO           VALUE 'C'.
           05  ERR-DESCRICAO             PIC X(80).
           05  ERR-CHAVE-REGISTRO        PIC X(20).
           05  ERR-FILLER                PIC X(10).
