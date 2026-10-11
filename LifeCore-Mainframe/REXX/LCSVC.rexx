/* REXX ----------------------------------------------------------------*
 * LCSVC    - LifeCore IQ - Menu de Servicos                            *
 *            Acesso restrito: Estipulante / Corretor                    *
 *            Visao limitada a UMA apolice                               *
 *                                                                       *
 * Mapeado sobre API REST:                                               *
 *   GET  /api/emissao/apolices/{nr}                                     *
 *   GET  /api/emissao/apolices/{nr}/coberturas                          *
 *   GET  /api/emissao/apolices/{nr}/faturamento                         *
 *   GET  /api/emissao/apolices/{nr}/subestipulantes                     *
 *   POST /api/emissao/apolices/{nr}/movimentacao/importar               *
 *   POST /api/sinistro                                                   *
 *   GET  /api/sinistro                                                   *
 *   GET  /api/corretagem/empresas/{cd}/corretora                        *
 *                                                                       *
 * Autor  : LifeCore IQ                                                  *
 * Data   : 2026-10-04                                                   *
 * Versao : 1.0.0                                                        *
 * ------------------------------------------------------------------  */

ARG lc_usuario lc_apolice .

IF lc_usuario = '' THEN lc_usuario = 'USUARIO'
IF lc_apolice = '' THEN DO
  SAY 'LCSVC: Nr Apolice nao informado.'
  EXIT 8
END

CALL IMPORT FSSAPI
ADDRESS FSS
CALL FSSINIT

/* ------- loop principal de servicos --------------------------------- */
DO forever

  opcao  = ''
  ZERRSM = ''

  CALL FSSTITLE  'LIFECORE IQ  -  SERVICOS  ['lc_usuario']'

  /* barra de status */
  CALL FSSTEXT  'Usuario : 'lc_usuario    ,2,2,,#PROT+#WHITE
  CALL FSSTEXT  'Apolice : 'lc_apolice    ,2,30,,#PROT+#GREEN+#HI
  CALL FSSTEXT  DATE('E')' 'TIME()        ,2,60,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  /* titulo menu */
  CALL FSSTEXT  'Selecione o servico desejado:' ,5,25,,#PROT+#YELLOW+#HI

  /* secao: APOLICE */
  CALL FSSTEXT  '── MINHA APOLICE ───────────────────────────────────' ,6,12,,#PROT+#BLUE
  CALL FSSTEXT  ' 1  -  CONSULTAR    Ver dados gerais da apolice'      ,7,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 2  -  SUBESTIPUL   Consultar subestipulantes'        ,8,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 3  -  CONTATOS     Consultar contatos cadastrados'   ,9,12,,#PROT+#GREEN

  /* secao: SEGURADOS */
  CALL FSSTEXT  '── SEGURADOS ───────────────────────────────────────' ,10,12,,#PROT+#BLUE
  CALL FSSTEXT  ' 4  -  COBERTURAS   Listar segurados e coberturas'    ,11,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 5  -  MOVIMENTAR   Incluir / Excluir / Alterar'      ,12,12,,#PROT+#GREEN

  /* secao: FINANCEIRO */
  CALL FSSTEXT  '── FINANCEIRO ──────────────────────────────────────' ,13,12,,#PROT+#BLUE
  CALL FSSTEXT  ' 6  -  FATURAS      Consultar faturas e vencimentos'  ,14,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 7  -  IPCA         Consultar taxa de reajuste IPCA'  ,15,12,,#PROT+#GREEN

  /* secao: SINISTROS */
  CALL FSSTEXT  '── SINISTROS ───────────────────────────────────────' ,16,12,,#PROT+#BLUE
  CALL FSSTEXT  ' 8  -  ABRIR        Abrir novo sinistro'              ,17,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 9  -  ACOMPANHAR   Acompanhar sinistros em aberto'   ,18,12,,#PROT+#GREEN

  CALL FSSTEXT  COPIES('─',50)  ,19,12,,#PROT+#BLUE
  CALL FSSTEXT  ' X  -  LOGOFF       Encerrar sessao'                  ,20,12,,#PROT+#RED

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE

  CALL FSSTEXT   'Opcao ===>'  ,23,12,,#PROT+#WHITE+#HI
  CALL FSSFIELD  'opcao'       ,23,23,2,#YELLOW+#HI+#USCORE

  CALL FSSTEXT  'PF1=Ajuda   PF3=Logoff   PF12=Cancelar'  ,24,18,,#PROT+#WHITE

  CALL FSSCURSOR 'opcao'
  CALL FSSDISPLAY

  key = FSSKEY(CHAR)

  IF key = 'PF03' | key = 'PF12' THEN DO
    CALL FSSTERM
    SAY 'Sessao encerrada. Ate logo, 'lc_usuario'!'
    EXIT 0
  END
  IF key <> 'ENTER' THEN ITERATE

  CALL FSSFGETALL
  opcao = STRIP(opcao)

  SELECT
    WHEN opcao = '1' THEN CALL SVC_APOLICE_DETALHE
    WHEN opcao = '2' THEN CALL SVC_SUBESTIPULANTES
    WHEN opcao = '3' THEN CALL SVC_CONTATOS
    WHEN opcao = '4' THEN CALL SVC_COBERTURAS
    WHEN opcao = '5' THEN CALL SVC_MOVIMENTACAO
    WHEN opcao = '6' THEN CALL SVC_FATURAS
    WHEN opcao = '7' THEN CALL SVC_IPCA
    WHEN opcao = '8' THEN CALL SVC_ABRIR_SINISTRO
    WHEN opcao = '9' THEN CALL SVC_SINISTROS
    WHEN opcao = 'X' | opcao = 'x' THEN DO
      CALL FSSTERM
      SAY 'Sessao encerrada. Ate logo, 'lc_usuario'!'
      EXIT 0
    END
    WHEN opcao = '' THEN CALL FSSZERRSM 'Selecione uma opcao'
    OTHERWISE CALL FSSZERRSM 'Opcao invalida: 'opcao
  END

  CALL FSSINIT

END

CALL FSSTERM
EXIT 0

/* ==================================================================== */
/* SVC_APOLICE_DETALHE                                                   */
/* GET /api/emissao/apolices/{nr_apolice}                                */
/* ==================================================================== */
SVC_APOLICE_DETALHE:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  DADOS DA APOLICE 'lc_apolice

  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE
  CALL FSSTEXT  'Consultando API...'  ,5,30,,#PROT+#TURQ+#HI
  CALL FSSDISPLAY

  /* API: GET /api/emissao/apolices/{nr_apolice} */
  ADDRESS TSO
  "ALLOC FI(APIOUT) DUMMY REUSE"
  resp = LCAPIGET('/api/emissao/apolices/'lc_apolice)
  ADDRESS FSS

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  DADOS DA APOLICE 'lc_apolice
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  /* exibe dados retornados (ou simulados) */
  CALL FSSTEXT  'Nr Apolice      : 'lc_apolice         ,5,10,,#PROT+#WHITE
  CALL FSSTEXT  'Estipulante     : 'LCAPI.NM_RAZAO       ,6,10,,#PROT+#GREEN
  CALL FSSTEXT  'CNPJ            : 'LCAPI.CD_CNPJ        ,7,10,,#PROT+#GREEN
  CALL FSSTEXT  'Produto         : 'LCAPI.CD_PRODUTO     ,8,10,,#PROT+#WHITE
  CALL FSSTEXT  'Status          : 'LCAPI.CD_STATUS      ,9,10,,#PROT+#WHITE
  CALL FSSTEXT  'Vigencia Inicio : 'LCAPI.DT_INI         ,10,10,,#PROT+#WHITE
  CALL FSSTEXT  'Vigencia Fim    : 'LCAPI.DT_FIM         ,11,10,,#PROT+#WHITE
  CALL FSSTEXT  'Forma Cobranca  : 'LCAPI.FORMA_COB      ,12,10,,#PROT+#WHITE
  CALL FSSTEXT  'Nr Segurados    : 'LCAPI.QT_SEGURADOS   ,13,10,,#PROT+#TURQ+#HI
  CALL FSSTEXT  'Vl Premio Total : R$ 'LCAPI.VL_PREMIO  ,14,10,,#PROT+#TURQ+#HI

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Voltar'  ,24,35,,#PROT+#WHITE

  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* SVC_SUBESTIPULANTES                                                   */
/* GET /api/emissao/apolices/{nr}/subestipulantes                        */
/* ==================================================================== */
SVC_SUBESTIPULANTES:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  SUBESTIPULANTES  Apolice: 'lc_apolice
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Cd  CNPJ              Razao Social                    Sit  Desde' ,5,2,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',76)  ,6,2,,#PROT+#BLUE

  /* API: GET /api/emissao/apolices/{nr}/subestipulantes */
  /* dados simulados ate integracao DB2 */
  CALL FSSTEXT  ' 1  44555666000195    FILIAL SAO PAULO                 AT   01/2026' ,7,2,,#PROT+#GREEN
  CALL FSSTEXT  ' 2  77888999000112    FILIAL RIO DE JANEIRO            AT   03/2026' ,8,2,,#PROT+#GREEN
  CALL FSSTEXT  ' 3  22111333000174    FILIAL BELO HORIZONTE            SU   06/2026' ,9,2,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('─',76)  ,10,2,,#PROT+#BLUE
  CALL FSSTEXT  '3 subestipulantes  |  Sit: AT=Ativo  SU=Suspenso  CA=Cancelado' ,11,2,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Voltar   PF7=Anterior   PF8=Proximo'  ,24,19,,#PROT+#WHITE

  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* SVC_CONTATOS                                                          */
/* GET /api/emissao/apolices/{nr}/config/contatos                        */
/* ==================================================================== */
SVC_CONTATOS:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  CONTATOS  Apolice: 'lc_apolice
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Tipo  Nome                       E-mail                  Fat' ,5,4,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',72)  ,6,4,,#PROT+#BLUE

  CALL FSSTEXT  'ADM   ROMILSON ASSUMPCAO        romilson@empresa.com     S'  ,7,4,,#PROT+#GREEN
  CALL FSSTEXT  'FIN   MARIA FINANCEIRO           maria.fin@empresa.com    S'  ,8,4,,#PROT+#GREEN
  CALL FSSTEXT  'RH    JOSE RECURSOS HUMANOS      jose.rh@empresa.com      N'  ,9,4,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('─',72)  ,10,4,,#PROT+#BLUE
  CALL FSSTEXT  '3 contatos  |  Fat=Recebe Fatura (S/N)'  ,11,4,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Voltar'  ,24,35,,#PROT+#WHITE

  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* SVC_COBERTURAS                                                        */
/* GET /api/emissao/apolices/{nr}/coberturas                             */
/* ==================================================================== */
SVC_COBERTURAS:
  cb_cpf    = ''
  cb_status = 'AT'

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  COBERTURAS  Apolice: 'lc_apolice
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Filtros (deixe em branco para listar todos):' ,5,16,,#PROT+#YELLOW

  CALL FSSTEXT   'CPF Segurado  :'  ,7,16,,#PROT+#WHITE
  CALL FSSFIELD  'cb_cpf'           ,7,32,11,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'Status        :'  ,8,16,,#PROT+#WHITE
  CALL FSSFIELD  'cb_status'        ,8,32,2,#GREEN+#USCORE,'AT'
  CALL FSSTEXT   'AT=Ativo  EX=Excluido  SU=Suspenso'  ,8,35,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Pesquisar   PF3=Voltar'  ,24,25,,#PROT+#WHITE

  CALL FSSCURSOR 'cb_cpf'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      cb_cpf    = STRIP(cb_cpf)
      cb_status = STRIP(TRANSLATE(cb_status))

      /* API: GET /api/emissao/apolices/{nr}/coberturas?cd_status=AT */
      CALL FSSTERM
      CALL FSSINIT
      CALL FSSTITLE  'LIFECORE IQ  -  COBERTURAS  Apolice: 'lc_apolice

      CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE
      CALL FSSTEXT  'CPF          Nome                       Cap.Seg.      Sit  Inclusao' ,5,2,,#PROT+#YELLOW+#HI
      CALL FSSTEXT  COPIES('─',76)  ,6,2,,#PROT+#BLUE

      /* dados simulados */
      CALL FSSTEXT  '11144477735  JOAO DA SILVA               R$ 120.000   AT   01/03/2026' ,7,2,,#PROT+#GREEN
      CALL FSSTEXT  '52998224725  MARIA OLIVEIRA              R$  80.000   AT   15/03/2026' ,8,2,,#PROT+#GREEN
      CALL FSSTEXT  '12345678577  PEDRO SANTOS                R$ 100.000   AT   01/04/2026' ,9,2,,#PROT+#GREEN
      CALL FSSTEXT  '98765432100  ANA COSTA                   R$  60.000   SU   01/02/2026' ,10,2,,#PROT+#WHITE

      CALL FSSTEXT  COPIES('─',76)  ,11,2,,#PROT+#BLUE
      CALL FSSTEXT  '4 coberturas encontradas  |  Status: 'cb_status  ,12,2,,#PROT+#TURQ

      CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
      CALL FSSTEXT  'PF3=Voltar   PF7=Anterior   PF8=Proximo'  ,24,19,,#PROT+#WHITE

      CALL FSSDISPLAY
      DO FOREVER
        key = FSSKEY(CHAR)
        IF key = 'PF03' | key = 'ENTER' THEN LEAVE
      END
      CALL FSSTERM
      LEAVE
    END
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* SVC_MOVIMENTACAO                                                      */
/* POST /api/emissao/apolices/{nr}/movimentacao/importar                 */
/* ==================================================================== */
SVC_MOVIMENTACAO:
  mv_tipo = ''
  mv_cpf  = ''
  mv_nome = ''
  mv_dtnc = ''
  mv_dtin = DATE('E')
  mv_cap  = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  MOVIMENTACAO  Apolice: 'lc_apolice
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Registrar movimentacao de segurado:' ,5,22,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',55)  ,6,12,,#PROT+#BLUE

  CALL FSSTEXT   'Tipo Movim.    :'  ,7,12,,#PROT+#WHITE
  CALL FSSFIELD  'mv_tipo'           ,7,28,3,#GREEN+#USCORE
  CALL FSSTEXT   'INC=Incluir  EXC=Excluir  CAP=Alt.Capital  SUS=Suspender  REA=Reativar' ,8,12,,#PROT+#TURQ

  CALL FSSTEXT   'CPF Segurado   :'  ,10,12,,#PROT+#WHITE
  CALL FSSFIELD  'mv_cpf'            ,10,28,11,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'Nome           :'  ,11,12,,#PROT+#WHITE
  CALL FSSFIELD  'mv_nome'           ,11,28,40,#GREEN+#USCORE

  CALL FSSTEXT   'Data Nasc.     :'  ,12,12,,#PROT+#WHITE
  CALL FSSFIELD  'mv_dtnc'           ,12,28,10,#GREEN+#USCORE
  CALL FSSTEXT   '(DD/MM/AAAA)'      ,12,39,,#PROT+#TURQ

  CALL FSSTEXT   'Data Inclusao  :'  ,13,12,,#PROT+#WHITE
  CALL FSSFIELD  'mv_dtin'           ,13,28,10,#GREEN+#USCORE,DATE('E')

  CALL FSSTEXT   'Capital Seg.   :'  ,14,12,,#PROT+#WHITE
  CALL FSSFIELD  'mv_cap'            ,14,28,12,#GREEN+#USCORE+#NUM
  CALL FSSTEXT   '(somente para INC e CAP)'  ,14,41,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('─',55)  ,15,12,,#PROT+#BLUE
  CALL FSSTEXT  'ATENCAO: Inclusao retroativa > 30 dias gera critica W042' ,16,12,,#PROT+#RED

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Confirmar   PF3=Cancelar'  ,24,24,,#PROT+#WHITE

  CALL FSSCURSOR 'mv_tipo'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      mv_tipo = STRIP(TRANSLATE(mv_tipo))
      mv_cpf  = STRIP(mv_cpf)
      mv_nome = STRIP(mv_nome)

      /* validacoes */
      IF mv_tipo = '' THEN DO
        CALL FSSZERRSM 'Tipo de movimentacao obrigatorio'
        CALL FSSCURSOR 'mv_tipo'; ITERATE
      END
      IF WORDPOS(mv_tipo,'INC EXC CAP SUS REA') = 0 THEN DO
        CALL FSSZERRSM 'Tipo invalido: INC EXC CAP SUS REA'
        CALL FSSCURSOR 'mv_tipo'; ITERATE
      END
      IF mv_cpf = '' THEN DO
        CALL FSSZERRSM 'CPF obrigatorio'
        CALL FSSCURSOR 'mv_cpf'; ITERATE
      END
      IF LENGTH(mv_cpf) <> 11 THEN DO
        CALL FSSZERRSM 'CPF deve ter 11 digitos'
        CALL FSSCURSOR 'mv_cpf'; ITERATE
      END
      IF mv_tipo = 'INC' & mv_nome = '' THEN DO
        CALL FSSZERRSM 'Nome obrigatorio para inclusao'
        CALL FSSCURSOR 'mv_nome'; ITERATE
      END

      /* API: POST /api/emissao/apolices/{nr}/movimentacao/importar */
      CALL FSSZERRSM mv_tipo' registrado: CPF 'mv_cpf' (simulacao)'
    END
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* SVC_FATURAS                                                           */
/* GET /api/emissao/apolices/{nr}/faturamento                            */
/* ==================================================================== */
SVC_FATURAS:
  ft_compet = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  FATURAS  Apolice: 'lc_apolice
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT   'Competencia (AAAAMM) ou branco p/ listar todas:'  ,5,12,,#PROT+#YELLOW
  CALL FSSFIELD  'ft_compet'  ,6,30,6,#GREEN+#USCORE+#NUM

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Pesquisar   PF3=Voltar'  ,24,25,,#PROT+#WHITE

  CALL FSSCURSOR 'ft_compet'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      ft_compet = STRIP(ft_compet)

      CALL FSSTERM
      CALL FSSINIT
      CALL FSSTITLE  'LIFECORE IQ  -  FATURAS  Apolice: 'lc_apolice

      CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE
      CALL FSSTEXT  'Nr  Competencia  Valor          Vencimento   Situacao  Cobranca' ,5,2,,#PROT+#YELLOW+#HI
      CALL FSSTEXT  COPIES('─',76)  ,6,2,,#PROT+#BLUE

      /* API: GET /api/emissao/apolices/{nr}/faturamento */
      CALL FSSTEXT  ' 1  202609        R$ 45.890,00   10/10/2026   PAGO      BOLETO' ,7,2,,#PROT+#GREEN
      CALL FSSTEXT  ' 2  202608        R$ 45.460,00   10/09/2026   PAGO      BOLETO' ,8,2,,#PROT+#GREEN
      CALL FSSTEXT  ' 3  202607        R$ 45.050,00   10/08/2026   PAGO      BOLETO' ,9,2,,#PROT+#GREEN
      CALL FSSTEXT  ' 4  202606        R$ 44.850,00   10/07/2026   PAGO      PIX'    ,10,2,,#PROT+#GREEN

      CALL FSSTEXT  COPIES('─',76)  ,11,2,,#PROT+#BLUE
      CALL FSSTEXT  '4 faturas | Coloque X na linha para ver detalhes'  ,12,2,,#PROT+#TURQ

      CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
      CALL FSSTEXT  'PF3=Voltar   PF7=Anterior   PF8=Proximo'  ,24,19,,#PROT+#WHITE

      CALL FSSDISPLAY
      DO FOREVER
        key = FSSKEY(CHAR)
        IF key = 'PF03' | key = 'ENTER' THEN LEAVE
      END
      CALL FSSTERM
      LEAVE
    END
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* SVC_IPCA                                                              */
/* GET /api/emissao/taxas-ipca/{cd_competencia}                          */
/* ==================================================================== */
SVC_IPCA:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  TAXA IPCA SUSEP  Apolice: 'lc_apolice
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Historico de reajustes aplicados a sua apolice:' ,5,16,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',50)  ,6,14,,#PROT+#BLUE

  CALL FSSTEXT  'Competencia  Indice  Acum.12m  Premio Antes    Premio Apos' ,7,8,,#PROT+#YELLOW
  CALL FSSTEXT  COPIES('─',68)  ,8,6,,#PROT+#BLUE

  /* API: GET /api/emissao/taxas-ipca */
  CALL FSSTEXT  '202610        0,44%    4,83%    R$ 45.688,00   R$ 45.890,00' ,9,6,,#PROT+#GREEN
  CALL FSSTEXT  '202609        0,44%    4,42%    R$ 45.287,00   R$ 45.688,00' ,10,6,,#PROT+#WHITE
  CALL FSSTEXT  '202608        0,44%    4,50%    R$ 44.888,00   R$ 45.287,00' ,11,6,,#PROT+#WHITE
  CALL FSSTEXT  '202607        0,38%    4,40%    R$ 44.718,00   R$ 44.888,00' ,12,6,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('─',68)  ,13,6,,#PROT+#BLUE
  CALL FSSTEXT  'Reajuste mensal pelo IPCA SUSEP conforme contrato'  ,14,16,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Voltar'  ,24,35,,#PROT+#WHITE

  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* SVC_ABRIR_SINISTRO                                                    */
/* POST /api/sinistro                                                    */
/* ==================================================================== */
SVC_ABRIR_SINISTRO:
  sn_cpf      = ''
  sn_evento   = ''
  sn_dt_ocor  = DATE('E')
  sn_ds_ocor  = ''
  sn_benef    = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  ABRIR SINISTRO  Apolice: 'lc_apolice
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Dados do evento para abertura de sinistro:' ,5,18,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',55)  ,6,12,,#PROT+#BLUE

  CALL FSSTEXT   'CPF Segurado     :'  ,7,12,,#PROT+#WHITE
  CALL FSSFIELD  'sn_cpf'              ,7,31,11,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'Tipo Evento      :'  ,8,12,,#PROT+#WHITE
  CALL FSSFIELD  'sn_evento'           ,8,31,3,#GREEN+#USCORE
  CALL FSSTEXT   'OBI=Obito  INV=Invalidez  DIT=Doenca'  ,8,35,,#PROT+#TURQ

  CALL FSSTEXT   'Data Ocorrencia  :'  ,9,12,,#PROT+#WHITE
  CALL FSSFIELD  'sn_dt_ocor'          ,9,31,10,#GREEN+#USCORE,DATE('E')

  CALL FSSTEXT   'Descricao        :'  ,11,12,,#PROT+#WHITE
  CALL FSSFIELD  'sn_ds_ocor'          ,11,31,46,#GREEN+#USCORE

  CALL FSSTEXT   'Nome Beneficiario :'  ,13,12,,#PROT+#WHITE
  CALL FSSFIELD  'sn_benef'             ,13,31,40,#GREEN+#USCORE

  CALL FSSTEXT  COPIES('─',55)  ,15,12,,#PROT+#BLUE
  CALL FSSTEXT  'Documentacao sera solicitada apos abertura.' ,16,14,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Abrir Sinistro   PF3=Cancelar'  ,24,21,,#PROT+#WHITE

  CALL FSSCURSOR 'sn_cpf'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      sn_cpf    = STRIP(sn_cpf)
      sn_evento = STRIP(TRANSLATE(sn_evento))
      sn_ds_ocor = STRIP(sn_ds_ocor)

      IF sn_cpf = '' THEN DO
        CALL FSSZERRSM 'CPF do segurado obrigatorio'
        CALL FSSCURSOR 'sn_cpf'; ITERATE
      END
      IF LENGTH(sn_cpf) <> 11 THEN DO
        CALL FSSZERRSM 'CPF deve ter 11 digitos'
        CALL FSSCURSOR 'sn_cpf'; ITERATE
      END
      IF WORDPOS(sn_evento,'OBI INV DIT') = 0 THEN DO
        CALL FSSZERRSM 'Tipo de evento invalido: OBI INV DIT'
        CALL FSSCURSOR 'sn_evento'; ITERATE
      END
      IF sn_ds_ocor = '' THEN DO
        CALL FSSZERRSM 'Descricao do evento obrigatoria'
        CALL FSSCURSOR 'sn_ds_ocor'; ITERATE
      END

      /* API: POST /api/sinistro */
      CALL FSSZERRSM 'Sinistro aberto! Nr: SN-'RIGHT(RANDOM(1,9999),4,'0')
    END
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* SVC_SINISTROS                                                         */
/* GET /api/sinistro?cd_empresa=...                                      */
/* ==================================================================== */
SVC_SINISTROS:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  SINISTROS  Apolice: 'lc_apolice
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Nr Sinistro  CPF           Evento  Data Aber.  Status     Indenizacao' ,5,2,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',76)  ,6,2,,#PROT+#BLUE

  /* API: GET /api/sinistro?cd_empresa=... */
  CALL FSSTEXT  'SN-0042     11144477735   OBI     01/08/2026  ANALISE    -'            ,7,2,,#PROT+#YELLOW
  CALL FSSTEXT  'SN-0031     52998224725   INV     15/06/2026  PAGO       R$ 80.000'    ,8,2,,#PROT+#GREEN
  CALL FSSTEXT  'SN-0028     12345678577   DIT     03/05/2026  ENCERRADO  R$ 12.000'    ,9,2,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('─',76)  ,10,2,,#PROT+#BLUE
  CALL FSSTEXT  '3 sinistros  |  OBI=Obito  INV=Invalidez  DIT=Doenca/Internacao'  ,11,2,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Voltar   PF7=Anterior   PF8=Proximo'  ,24,19,,#PROT+#WHITE

  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* LCAPIGET - Stub para chamada GET a API REST                           */
/* Futuramente usa BREXX ADDRESS HTTP ou TSO pipe                        */
/* ==================================================================== */
LCAPIGET:
  ARG endpoint .
  /* inicializa campos simulados ate integracao real */
  LCAPI.NM_RAZAO    = 'LIFECORE SEGUROS DE VIDA S.A.'
  LCAPI.CD_CNPJ     = '11.222.333/0001-81'
  LCAPI.CD_PRODUTO  = 'VGC'
  LCAPI.CD_STATUS   = 'AT - ATIVA'
  LCAPI.DT_INI      = '01/01/2026'
  LCAPI.DT_FIM      = '31/12/2026'
  LCAPI.FORMA_COB   = 'BO - BOLETO'
  LCAPI.QT_SEGURADOS = '247'
  LCAPI.VL_PREMIO   = '45.890,00'
RETURN 'OK'
