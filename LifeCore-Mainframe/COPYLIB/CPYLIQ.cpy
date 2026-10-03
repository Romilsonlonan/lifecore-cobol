      *================================================================*
      * COPYBOOK : CPYLIQ                                             *
      * DESCRICAO: Layout do registro de Liquidacao                   *
      *            Compartilhado entre SETTLE01 e DISPUT01            *
      * PROJETO  : LifeCore-Mainframe                                 *
      * VERSAO   : 1.0.0                                              *
      * TAMANHO  : 300 bytes                                          *
      *================================================================*
       01  REG-LIQUIDACAO.
           05  LIQ-NSU                   PIC X(12).
           05  LIQ-DATA-CLEARING         PIC X(08).
           05  LIQ-DATA-CREDITO          PIC X(08).
           05  LIQ-VALOR-CLEARING        PIC S9(13)V9 COMP-3.
           05  LIQ-VALOR-AGENDA          PIC S9(13)V9 COMP-3.
           05  LIQ-DIFERENCA             PIC S9(11)V9 COMP-3.
           05  LIQ-STATUS                PIC X(02).
               88  LIQ-LIQUIDADO         VALUE 'LQ'.
               88  LIQ-DIVERGENCIA       VALUE 'DV'.
               88  LIQ-NAO-ENCONTRADO    VALUE 'NE'.
           05  LIQ-BANCO                 PIC X(08).
           05  LIQ-FILLER                PIC X(221).
