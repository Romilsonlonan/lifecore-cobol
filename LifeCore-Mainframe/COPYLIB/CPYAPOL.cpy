      *================================================================*
      * COPYBOOK : CPYAPOL                                            *
      * DESCRICAO: Layout de Apolice e Segurado                       *
      * PROJETO  : LifeCore-Mainframe                                 *
      * VERSAO   : 1.0.0                                              *
      * TAMANHO  : 300 bytes                                          *
      *================================================================*
       01  REG-APOLICE.
           05  APO-TIPO-REGISTRO         PIC X(02).
               88  APO-TIPO-HEADER       VALUE 'H0'.
               88  APO-TIPO-DETALHE      VALUE 'D1'.
               88  APO-TIPO-TRAILER      VALUE 'T9'.
           05  APO-NUMERO                PIC X(12).
           05  APO-PRODUTO               PIC X(03).
               88  APO-PRODUTO-VGC       VALUE 'VGC'.
               88  APO-PRODUTO-GLB       VALUE 'GLB'.
           05  APO-ESTIPULANTE-CNPJ      PIC X(14).
           05  APO-SEGURADO-CPF          PIC X(11).
           05  APO-SEGURADO-NOME         PIC X(40).
           05  APO-VIGENCIA-INI          PIC X(08).
           05  APO-VIGENCIA-FIM          PIC X(08).
           05  APO-STATUS                PIC X(02).
               88  APO-ATIVO             VALUE 'AT'.
               88  APO-CANCELADO         VALUE 'CA'.
               88  APO-SUSPESO           VALUE 'SU'.
           05  APO-TIPO-CAPITAL          PIC X(01).
               88  APO-CAP-FIXO          VALUE 'F'.
               88  APO-CAP-ESCALONADO    VALUE 'E'.
               88  APO-CAP-MULT-SALARIAL VALUE 'M'.
               88  APO-CAP-POR-FAIXA     VALUE 'B'.
               88  APO-CAP-PARAMETRICO   VALUE 'P'.
           05  APO-CAPITAL-SEGURADO      PIC S9(13)V99 COMP-3.
           05  APO-SALARIO-BASE          PIC S9(11)V99 COMP-3.
           05  APO-FATOR-MULTIPLICADOR   PIC S9(03)V99 COMP-3.
           05  APO-PREMIO-LIQUIDO        PIC S9(11)V99 COMP-3.
           05  APO-PREMIO-BRUTO          PIC S9(11)V99 COMP-3.
           05  APO-IOF                   PIC S9(09)V99 COMP-3.
           05  APO-FORMA-PAGAMENTO       PIC X(02).
               88  APO-PAGT-BOLETO       VALUE 'BO'.
               88  APO-PAGT-CARTAO       VALUE 'CC'.
               88  APO-PAGT-DEBITO       VALUE 'DB'.
           05  APO-PERIODICIDADE         PIC X(02).
               88  APO-PERI-MENSAL       VALUE 'MN'.
               88  APO-PERI-ANUAL        VALUE 'AN'.
               88  APO-PERI-UNICO        VALUE 'UN'.
           05  APO-DATA-EMISSAO          PIC X(08).
           05  APO-USUARIO-INCLUSAO      PIC X(08).
           05  APO-TIMESTAMP             PIC X(26).
           05  APO-FILLER                PIC X(63).
