      *================================================================*
      * COPYBOOK : CPYFATU                                            *
      * DESCRICAO: Layout de Fatura por Estipulante                   *
      * PROJETO  : LifeCore-Mainframe                                 *
      * VERSAO   : 1.0.0                                              *
      * TAMANHO  : 250 bytes                                          *
      *================================================================*
       01  REG-FATURA.
           05  FAT-TIPO-REGISTRO         PIC X(02).
               88  FAT-TIPO-HEADER       VALUE 'H0'.
               88  FAT-TIPO-DETALHE      VALUE 'D1'.
               88  FAT-TIPO-TRAILER      VALUE 'T9'.
           05  FAT-NUMERO                PIC X(14).
           05  FAT-ESTIPULANTE-CNPJ      PIC X(14).
           05  FAT-ESTIPULANTE-NOME      PIC X(40).
           05  FAT-COMPETENCIA           PIC X(06).
           05  FAT-DATA-EMISSAO          PIC X(08).
           05  FAT-DATA-VENCIMENTO       PIC X(08).
           05  FAT-DATA-PAGAMENTO        PIC X(08).
           05  FAT-QTD-APOLICES          PIC 9(06)    COMP-3.
           05  FAT-VALOR-BRUTO           PIC S9(13)V99 COMP-3.
           05  FAT-VALOR-DESCONTO        PIC S9(11)V99 COMP-3.
           05  FAT-VALOR-LIQUIDO         PIC S9(13)V99 COMP-3.
           05  FAT-VALOR-PAGO            PIC S9(13)V99 COMP-3.
           05  FAT-VALOR-DIFERENCA       PIC S9(11)V99 COMP-3.
           05  FAT-STATUS                PIC X(02).
               88  FAT-PENDENTE          VALUE 'PE'.
               88  FAT-PAGO-OK           VALUE 'PG'.
               88  FAT-PAGO-PARCIAL      VALUE 'PP'.
               88  FAT-ATRASADO          VALUE 'AT'.
               88  FAT-CANCELADO         VALUE 'CA'.
           05  FAT-FORMA-PAGAMENTO       PIC X(02).
               88  FAT-PAGT-BOLETO       VALUE 'BO'.
               88  FAT-PAGT-CARTAO       VALUE 'CC'.
               88  FAT-PAGT-DEBITO       VALUE 'DB'.
           05  FAT-NOSSO-NUMERO          PIC X(20).
           05  FAT-LINHA-DIGITAVEL       PIC X(47).
           05  FAT-USUARIO-EMISSAO       PIC X(08).
           05  FAT-FILLER                PIC X(09).
