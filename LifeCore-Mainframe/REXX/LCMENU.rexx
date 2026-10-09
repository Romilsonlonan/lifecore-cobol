/* REXX ----------------------------------------------------------------*
 * LCMENU   - LifeCore IQ - Menu Principal                              *
 *            Sistema de Gestao de Seguros de Vida em Grupo             *
 * Autor  : LifeCore IQ                                                 *
 * Data   : 2026-10-04                                                  *
 * Versao : 1.1.0                                                       *
 * Chamado por LCLOGIN apos autenticacao bem-sucedida                   *
 * ARG: lc_userid perfil (ADMIN)                                        *
 * ------------------------------------------------------------------  */

ARG lc_userid lc_perfil .

IF lc_userid = '' THEN lc_userid = 'USUARIO'

CALL IMPORT FSSAPI
ADDRESS FSS
CALL FSSINIT

/* ------- loop do menu principal ------------------------------------- */
DO forever

  opcao  = ''
  ZERRSM = ''

  /* data e hora atual */
  dt = DATE('E')
  hr = TIME()

  /* ---- definicao da tela ------------------------------------------ */
  CALL FSSTITLE  'LIFECORE IQ  V1.0  -  MENU PRINCIPAL  ['lc_userid']'

  /* barra de status */
  CALL FSSTEXT  'Usuario: '             ,2,2,,#PROT+#WHITE
  CALL FSSTEXT  lc_userid               ,2,11,10,#PROT+#GREEN+#HI
  CALL FSSTEXT  'Perfil: ADMINISTRADOR' ,2,25,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  'Data: 'dt              ,2,50,,#PROT+#WHITE
  CALL FSSTEXT  'Hora: 'hr              ,2,65,,#PROT+#WHITE

  /* linha separadora */
  CALL FSSTEXT  COPIES('═',78)          ,3,1,78,#PROT+#BLUE

  /* cabecalho do menu */
  CALL FSSTEXT  'Selecione uma opcao e pressione ENTER' ,5,22,,#PROT+#YELLOW+#HI

  /* linha separadora secao - OPERACIONAL */
  CALL FSSTEXT  '── OPERACIONAL ──────────────────────────────────────' ,6,12,,#PROT+#BLUE

  CALL FSSTEXT  ' 1  -  APOLICES     Cadastro e consulta de apolices'    ,7,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 2  -  ESTIPULANTES Gestao de empresas contratantes'    ,8,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 3  -  SEGURADOS    Inclusao, exclusao, movimentacao'   ,9,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 4  -  FATURAMENTO  Geracao de faturas e IPCA'          ,10,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 5  -  SINISTROS    Abertura e acompanhamento'          ,11,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 6  -  COMISSOES    Calculo e conferencia'              ,12,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 7  -  CONCILIACAO  Faturado x pago'                   ,13,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 8  -  CORRETAGEM   Corretores e vinculos'              ,14,12,,#PROT+#GREEN

  /* linha separadora secao - ADMINISTRACAO */
  CALL FSSTEXT  '── ADMINISTRACAO ────────────────────────────────────' ,15,12,,#PROT+#YELLOW

  CALL FSSTEXT  ' A  -  ACESSOS      Cadastrar logins Estipulante/Corretor' ,16,12,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  ' 9  -  RELATORIOS   Relatorios gerenciais e BI'            ,17,12,,#PROT+#TURQ
  CALL FSSTEXT  '10  -  AUDITORIA    Log de acesso e rastreabilidade'        ,18,12,,#PROT+#TURQ
  CALL FSSTEXT  '11  -  BATCH        Submeter jobs de processamento'         ,19,12,,#PROT+#TURQ

  /* linha separadora secao */
  CALL FSSTEXT  COPIES('─',50)          ,20,14,,#PROT+#BLUE

  CALL FSSTEXT  ' X  -  LOGOFF       Encerrar sessao'                       ,21,12,,#PROT+#RED

  /* linha separadora */
  CALL FSSTEXT  COPIES('═',78)          ,22,1,78,#PROT+#BLUE

  /* campo de opcao */
  CALL FSSTEXT    'Opcao ===>'          ,23,12,,#PROT+#WHITE+#HI
  CALL FSSFIELD   'opcao'               ,23,23,3,#YELLOW+#HI+#USCORE

  /* pf keys */
  CALL FSSTEXT  'PF1=Ajuda   PF3=Logoff   PF12=Cancelar' ,24,15,,#PROT+#WHITE

  CALL FSSCURSOR 'opcao'
  CALL FSSDISPLAY

  key = FSSKEY(CHAR)

  /* PF3 ou PF12 = logoff */
  IF key = 'PF03' | key = 'PF12' THEN DO
    CALL FSSTERM
    SAY 'Sessao encerrada. Ate logo, 'lc_userid'!'
    EXIT 0
  END

  IF key <> 'ENTER' THEN ITERATE

  CALL FSSFGETALL
  opcao = STRIP(opcao)

  SELECT
    WHEN opcao = '1'  THEN CALL LC_NAO_IMPL 'APOLICES'
    WHEN opcao = '2'  THEN CALL LCESTIP lc_userid
    WHEN opcao = '3'  THEN CALL LC_NAO_IMPL 'SEGURADOS'
    WHEN opcao = '4'  THEN CALL LCFATUR lc_userid
    WHEN opcao = '5'  THEN CALL LC_NAO_IMPL 'SINISTROS'
    WHEN opcao = '6'  THEN CALL LC_NAO_IMPL 'COMISSOES'
    WHEN opcao = '7'  THEN CALL LC_NAO_IMPL 'CONCILIACAO'
    WHEN opcao = '8'  THEN CALL LC_NAO_IMPL 'CORRETAGEM'
    WHEN opcao = 'A' | opcao = 'a' THEN CALL LCACESSO lc_userid
    WHEN opcao = '9'  THEN CALL LC_NAO_IMPL 'RELATORIOS'
    WHEN opcao = '10' THEN CALL LC_NAO_IMPL 'AUDITORIA'
    WHEN opcao = '11' THEN CALL LCBATCH lc_userid
    WHEN opcao = 'X' | opcao = 'x' THEN DO
      CALL FSSTERM
      SAY 'Sessao encerrada. Ate logo, 'lc_userid'!'
      EXIT 0
    END
    WHEN opcao = '' THEN
      CALL FSSZERRSM 'Selecione uma opcao'
    OTHERWISE
      CALL FSSZERRSM 'Opcao invalida: 'opcao
  END

  /* reabrir FSS apos retorno de sub-tela */
  CALL FSSINIT

END

CALL FSSTERM
EXIT 0

/* -------------------------------------------------------------------- */
/* LC_NAO_IMPL - Modulo ainda nao implementado                           */
/* -------------------------------------------------------------------- */
LC_NAO_IMPL:
  ARG modulo .
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  'modulo
  CALL FSSTEXT   COPIES('─',60) ,5,10,,#PROT+#BLUE
  CALL FSSTEXT   'Modulo em desenvolvimento...' ,8,26,,#PROT+#YELLOW+#HI
  CALL FSSTEXT   'Previsao: Sprint 2'           ,10,31,,#PROT+#WHITE
  CALL FSSTEXT   COPIES('─',60) ,12,10,,#PROT+#BLUE
  CALL FSSTEXT   'PF3=Voltar ao Menu'           ,14,30,,#PROT+#GREEN
  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN
