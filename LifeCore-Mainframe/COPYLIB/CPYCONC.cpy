      *================================================================*
      * COPYBOOK : CPYCONC                                            *
      * DESCRICAO: Layout de Resultado de Conciliacao                 *
      * PROJETO  : LifeCore-Mainframe                                 *
      * VERSAO   : 1.0.0                                              *
      * TAMANHO  : 220 bytes                                          *
      *================================================================*
       01  REG-CONCILIACAO.
           05  CON-TIPO-REGISTRO         PIC X(02).
               88  CON-TIPO-HEADER       VALUE 'H0'.
               88  CON-TIPO-DETALHE      VALUE 'D1'.
               88  CON-TIPO-TRAILER      VALUE 'T9'.
           05  CON-NUMERO                PIC X(16).
           05  CON-FATURA-NUMERO         PIC X(14).
           05  CON-PAGAMENTO-NUMERO      PIC X(16).
           05  CON-APOLICE-NUMERO        PIC X(12).
           05  CON-DATA-CONCILIACAO      PIC X(08).
           05  CON-VALOR-FATURADO        PIC S9(13)V99 COMP-3.
           05  CON-VALOR-PAGO            PIC S9(13)V99 COMP-3.
           05  CON-VALOR-DIFERENCA       PIC S9(11)V99 COMP-3.
           05  CON-STATUS                PIC X(02).
               88  CON-OK                VALUE 'OK'.
               88  CON-DIV-VALOR         VALUE 'DV'.
               88  CON-SEM-PAGAMENTO     VALUE 'SP'.
               88  CON-SEM-FATURA        VALUE 'SF'.
               88  CON-DUPLICADO         VALUE 'DU'.
               88  CON-CHARGEBACK        VALUE 'CB'.
           05  CON-TIPO-CANAL            PIC X(02).
               88  CON-CANAL-BOLETO      VALUE 'BO'.
               88  CON-CANAL-CARTAO      VALUE 'CC'.
               88  CON-CANAL-DEBITO      VALUE 'DB'.
           05  CON-NSU                   PIC X(12).
           05  CON-COD-AUTORIZACAO       PIC X(06).
           05  CON-CICLO-CLEARING        PIC X(08).
           05  CON-USUARIO               PIC X(08).
           05  CON-OBSERVACAO            PIC X(60).
           05  CON-FILLER                PIC X(17).
