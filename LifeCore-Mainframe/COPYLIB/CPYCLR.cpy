      *================================================================*
      * COPYBOOK : CPYCLR                                             *
      * DESCRICAO: Layout do arquivo de Clearing da Bandeira           *
      *            Compartilhado entre CLEAR01 e SETTLE01             *
      * PROJETO  : LifeCore-Mainframe                                 *
      * VERSAO   : 1.0.0                                              *
      * TAMANHO  : 300 bytes                                          *
      *================================================================*
       01  REG-CLEARING.
           05  CLR-TIPO-REGISTRO         PIC X(02).
               88  CLR-HEADER            VALUE 'H0'.
               88  CLR-DETALHE           VALUE 'D1'.
               88  CLR-TRAILER           VALUE 'T9'.
           05  CLR-BANDEIRA              PIC X(04).
           05  CLR-CICLO                 PIC X(08).
           05  CLR-NSU                   PIC X(12).
           05  CLR-COD-AUTORIZACAO       PIC X(06).
           05  CLR-TOKEN-CARTAO          PIC X(32).
           05  CLR-CARTAO-ULTIMOS-4      PIC X(04).
           05  CLR-DATA-TRANSACAO        PIC X(08).
           05  CLR-DATA-CLEARING         PIC X(08).
           05  CLR-VALOR-BRUTO           PIC S9(13)V9 COMP-3.
           05  CLR-VALOR-TAXA            PIC S9(09)V9 COMP-3.
           05  CLR-VALOR-LIQUIDO         PIC S9(13)V9 COMP-3.
           05  CLR-TIPO-TRANSACAO        PIC X(04).
               88  CLR-VENDA             VALUE '0200'.
               88  CLR-ESTORNO           VALUE '0400'.
               88  CLR-CHARGEBACK        VALUE 'CB00'.
           05  CLR-PARCELAS              PIC 9(02)    COMP-3.
           05  CLR-ADQUIRENTE            PIC X(08).
           05  CLR-STATUS                PIC X(02).
               88  CLR-APROVADO          VALUE 'AP'.
               88  CLR-RECUSADO          VALUE 'RC'.
           05  CLR-FILLER                PIC X(179).
