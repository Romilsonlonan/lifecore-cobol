      *================================================================*
      * COPYBOOK : CPYPAGT                                            *
      * DESCRICAO: Layout de Pagamento                                *
      * PROJETO  : LifeCore-Mainframe                                 *
      * VERSAO   : 1.0.0                                              *
      * TAMANHO  : 200 bytes                                          *
      * NOTA PCI : PAN nao armazenado. Apenas token + 4 ultimos digs  *
      *================================================================*
       01  REG-PAGAMENTO.
           05  PAG-TIPO-REGISTRO         PIC X(02).
               88  PAG-TIPO-HEADER       VALUE 'H0'.
               88  PAG-TIPO-DETALHE      VALUE 'D1'.
               88  PAG-TIPO-TRAILER      VALUE 'T9'.
           05  PAG-NUMERO                PIC X(16).
           05  PAG-FATURA-NUMERO         PIC X(14).
           05  PAG-APOLICE-NUMERO        PIC X(12).
           05  PAG-DATA-PAGAMENTO        PIC X(08).
           05  PAG-HORA-PAGAMENTO        PIC X(06).
           05  PAG-VALOR                 PIC S9(13)V99 COMP-3.
           05  PAG-FORMA                 PIC X(02).
               88  PAG-FORMA-BOLETO      VALUE 'BO'.
               88  PAG-FORMA-CARTAO      VALUE 'CC'.
               88  PAG-FORMA-DEBITO      VALUE 'DB'.
           05  PAG-STATUS                PIC X(02).
               88  PAG-CONFIRMADO        VALUE 'CF'.
               88  PAG-CANCELADO         VALUE 'CA'.
               88  PAG-ESTORNADO         VALUE 'ES'.
               88  PAG-CHARGEBACK        VALUE 'CB'.
           05  PAG-BANDEIRA              PIC X(04).
               88  PAG-VISA              VALUE 'VISA'.
               88  PAG-MASTER            VALUE 'MCRD'.
               88  PAG-ELO               VALUE 'ELOC'.
           05  PAG-TOKEN-CARTAO          PIC X(32).
           05  PAG-CARTAO-ULTIMOS-4      PIC X(04).
           05  PAG-NSU                   PIC X(12).
           05  PAG-COD-AUTORIZACAO       PIC X(06).
           05  PAG-ADQUIRENTE            PIC X(08).
           05  PAG-PARCELAS              PIC 9(02)    COMP-3.
           05  PAG-CODIGO-ISO8583        PIC X(04).
           05  PAG-FILLER                PIC X(49).
