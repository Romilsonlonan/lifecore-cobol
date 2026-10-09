//LCUPLOAD JOB (LIFECORE),'UPLOAD REXX',CLASS=A,MSGCLASS=X,
//             NOTIFY=&SYSUID,MSGLEVEL=(1,1)
//*
//ALLOC    EXEC PGM=IEFBR14
//RXLIB    DD  DSN=HERC01.LIFECORE.REXX,
//             DISP=(MOD,CATLG,DELETE),
//             SPACE=(TRK,(5,5,20)),
//             RECFM=FB,LRECL=80,BLKSIZE=3120,
//             UNIT=SYSDA
//*
//LOADREXX EXEC PGM=IEBUPDTE,PARM=NEW
//SYSPRINT DD  SYSOUT=*
//SYSUT2   DD  DSN=HERC01.LIFECORE.REXX,DISP=SHR
//SYSIN    DD  DATA,DLM=@@
./ ADD NAME=LCLOGIN
/* REXX ----------------------------------------------------------------*
 * LCLOGIN  - LifeCore IQ - Tela de Login                               *
 *            Suporta dois perfis:                                       *
 *              ADMIN      - acesso global (todas as empresas)           *
 *              ESTIP/COR  - acesso de servicos (por apolice)            *
 * Autor  : LifeCore IQ                                                 *
 * Data   : 2026-10-04                                                  *
 * Versao : 1.1.0                                                       *
 * Uso    : TSO EXEC 'HERC01.LIFECORE.REXX(LCLOGIN)'                   *
 * ------------------------------------------------------------------  */

CALL IMPORT FSSAPI
ADDRESS FSS
CALL FSSINIT

/* ------- credenciais admin (fixas por ora ? futuramente DB2) -------- */
ADMIN_USR  = 'LCADMIN'
ADMIN_PWD  = 'LC@2026'
MAX_TENT   = 3
tentativas = 0

/* ------- loop de login --------------------------------------------- */
DO forever

  lc_tipo   = 'A'       /* A=Admin  E=Estipulante/Corretor */
  lc_user   = ''
  lc_apolice= ''
  lc_pass   = ''
  ZERRSM    = ''

  /* ---- cabecalho --------------------------------------------------- */
  CALL FSSTITLE 'LIFECORE IQ  V1.0  -  SISTEMA DE GESTAO VGC/GLB'

  CALL FSSTEXT COPIES('?',78)  ,3,1,78,#PROT+#BLUE

  /* logo compacto */
  CALL FSSTEXT '   ???     ??????????????????? ??????? ??????? ??????? ????????'
  CALL FSSTEXT '   ???     ????????????????????????????????????????????????????'
  CALL FSSTEXT '   ???     ?????????  ??????  ???     ???   ?????????????????  '
  CALL FSSTEXT '   ??????????????     ????????????????????????????  ???????????'
  CALL FSSTEXT '   Gestao de Apolices  /  Segurados  /  Faturamento  /  Sinistro

  CALL FSSTEXT COPIES('?',78)  ,10,1,78,#PROT+#BLUE

  /* ---- tipo de acesso ---------------------------------------------- */
  CALL FSSTEXT 'Tipo de Acesso :'                 ,12,16,,#PROT+#YELLOW+#HI
  CALL FSSTEXT 'A=Administrador  E=Estipulante/Corretor' ,12,34,,#PROT+#WHITE
  CALL FSSFIELD 'lc_tipo'                         ,12,33,1,#GREEN+#HI+#USCORE,'A

  CALL FSSTEXT COPIES('?',46)  ,13,16,,#PROT+#BLUE

  /* ---- campos de login --------------------------------------------- */
  CALL FSSTEXT  'Usuario        :'  ,15,16,,#PROT+#WHITE
  CALL FSSFIELD 'lc_user'           ,15,33,10,#GREEN+#USCORE

  CALL FSSTEXT  'Ap?lice        :'  ,16,16,,#PROT+#WHITE
  CALL FSSTEXT  '(somente para Estipulante/Corretor)' ,16,46,,#PROT+#TURQ
  CALL FSSFIELD 'lc_apolice'        ,16,33,10,#GREEN+#USCORE

  CALL FSSTEXT  'Senha          :'  ,18,16,,#PROT+#WHITE
  CALL FSSFIELD 'lc_pass'           ,18,33,10,#GREEN+#NON+#USCORE

  /* tentativas restantes */
  IF tentativas > 0 THEN DO
    rest = MAX_TENT - tentativas
    CALL FSSTEXT 'Tentativas restantes: 'rest  ,20,26,,#PROT+#RED+#HI
  END

  CALL FSSTEXT COPIES('?',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT 'PF1=Ajuda   PF3=Sair   ENTER=Entrar'  ,24,21,,#PROT+#YELLOW

  CALL FSSCURSOR 'lc_tipo'
  CALL FSSDISPLAY

  key = FSSKEY(CHAR)

  IF key = 'PF03' THEN DO
    CALL FSSTERM
    SAY 'Saindo do LifeCore IQ...'
    EXIT 0
  END

  IF key <> 'ENTER' THEN ITERATE

  CALL FSSFGETALL
  lc_tipo    = STRIP(TRANSLATE(lc_tipo))
  lc_user    = STRIP(TRANSLATE(lc_user))
  lc_apolice = STRIP(lc_apolice)
  lc_pass    = STRIP(lc_pass)

  /* ---- validacoes basicas ----------------------------------------- */
  IF lc_tipo <> 'A' & lc_tipo <> 'E' THEN DO
    CALL FSSZERRSM 'Tipo invalido: A ou E'
    CALL FSSCURSOR 'lc_tipo'
    ITERATE
  END
  IF lc_user = '' THEN DO
    CALL FSSZERRSM 'Informe o usuario'
    CALL FSSCURSOR 'lc_user'
    ITERATE
  END
  IF lc_pass = '' THEN DO
    CALL FSSZERRSM 'Informe a senha'
    CALL FSSCURSOR 'lc_pass'
    ITERATE
  END
  IF lc_tipo = 'E' & lc_apolice = '' THEN DO
    CALL FSSZERRSM 'Informe a Apolice para acesso Estipulante/Corretor'
    CALL FSSCURSOR 'lc_apolice'
    ITERATE
  END

  /* ---- autenticacao ADMIN ----------------------------------------- */
  IF lc_tipo = 'A' THEN DO
    IF lc_user = ADMIN_USR & lc_pass = ADMIN_PWD THEN DO
      CALL FSSTERM
      CALL LCMENU lc_user 'ADMIN'
      EXIT 0
    END
    tentativas = tentativas + 1
    IF tentativas >= MAX_TENT THEN DO
      CALL FSSTERM
      SAY 'ACESSO BLOQUEADO - Numero maximo de tentativas atingido.'
      EXIT 8
    END
    CALL FSSZERRSM 'Usuario ou senha invalidos'
    ITERATE
  END

  /* ---- autenticacao ESTIPULANTE/CORRETOR (stub ? futuramente DB2) -- */
  IF lc_tipo = 'E' THEN DO
    /* por ora valida dummy: qualquer usuario cadastrado retorna OK */
    /* futuramente: SELECT FROM USUARIOS_ACESSO WHERE
         CD_APOLICE=lc_apolice AND DS_LOGIN=lc_user
         AND DS_SENHA=ENCRYPT(lc_pass) */
    IF lc_apolice = '0000000001' & lc_user = 'TESTE' & lc_pass = 'TESTE123' THEN
      CALL FSSTERM
      CALL LCSVC lc_user lc_apolice
      EXIT 0
    END
    tentativas = tentativas + 1
    IF tentativas >= MAX_TENT THEN DO
      CALL FSSTERM
      SAY 'ACESSO BLOQUEADO - Numero maximo de tentativas atingido.'
      EXIT 8
    END
    CALL FSSZERRSM 'Apolice, usuario ou senha invalidos'
    ITERATE
  END

END

CALL FSSTERM
EXIT 0
./ ADD NAME=LCMENU
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
  CALL FSSTEXT  COPIES('?',78)          ,3,1,78,#PROT+#BLUE

  /* cabecalho do menu */
  CALL FSSTEXT  'Selecione uma opcao e pressione ENTER' ,5,22,,#PROT+#YELLOW+#HI

  /* linha separadora secao - OPERACIONAL */
  CALL FSSTEXT  '?? OPERACIONAL ??????????????????????????????????????' ,6,12,,#

  CALL FSSTEXT  ' 1  -  APOLICES     Cadastro e consulta de apolices'    ,7,12,,
  CALL FSSTEXT  ' 2  -  ESTIPULANTES Gestao de empresas contratantes'    ,8,12,,
  CALL FSSTEXT  ' 3  -  SEGURADOS    Inclusao, exclusao, movimentacao'   ,9,12,,
  CALL FSSTEXT  ' 4  -  FATURAMENTO  Geracao de faturas e IPCA'          ,10,12,
  CALL FSSTEXT  ' 5  -  SINISTROS    Abertura e acompanhamento'          ,11,12,
  CALL FSSTEXT  ' 6  -  COMISSOES    Calculo e conferencia'              ,12,12,
  CALL FSSTEXT  ' 7  -  CONCILIACAO  Faturado x pago'                   ,13,12,,
  CALL FSSTEXT  ' 8  -  CORRETAGEM   Corretores e vinculos'              ,14,12,

  /* linha separadora secao - ADMINISTRACAO */
  CALL FSSTEXT  '?? ADMINISTRACAO ????????????????????????????????????' ,15,12,,

  CALL FSSTEXT  ' A  -  ACESSOS      Cadastrar logins Estipulante/Corretor' ,16,
  CALL FSSTEXT  ' 9  -  RELATORIOS   Relatorios gerenciais e BI'            ,17,
  CALL FSSTEXT  '10  -  AUDITORIA    Log de acesso e rastreabilidade'        ,18
  CALL FSSTEXT  '11  -  BATCH        Submeter jobs de processamento'         ,19

  /* linha separadora secao */
  CALL FSSTEXT  COPIES('?',50)          ,20,14,,#PROT+#BLUE

  CALL FSSTEXT  ' X  -  LOGOFF       Encerrar sessao'                       ,21,

  /* linha separadora */
  CALL FSSTEXT  COPIES('?',78)          ,22,1,78,#PROT+#BLUE

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
  CALL FSSTEXT   COPIES('?',60) ,5,10,,#PROT+#BLUE
  CALL FSSTEXT   'Modulo em desenvolvimento...' ,8,26,,#PROT+#YELLOW+#HI
  CALL FSSTEXT   'Previsao: Sprint 2'           ,10,31,,#PROT+#WHITE
  CALL FSSTEXT   COPIES('?',60) ,12,10,,#PROT+#BLUE
  CALL FSSTEXT   'PF3=Voltar ao Menu'           ,14,30,,#PROT+#GREEN
  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN
./ ADD NAME=LCESTIP
/* REXX ----------------------------------------------------------------*
 * LCESTIP  - LifeCore IQ - Gestao de Estipulantes                     *
 *            Consulta, inclusao e manutencao de estipulantes           *
 * Autor  : LifeCore IQ                                                 *
 * Data   : 2026-10-04                                                  *
 * Versao : 1.0.0                                                       *
 * ------------------------------------------------------------------  */

ARG lc_userid .

CALL IMPORT FSSAPI
ADDRESS FSS
CALL FSSINIT

DO forever

  opcao  = ''
  ZERRSM = ''

  CALL FSSTITLE  'LIFECORE IQ  -  GESTAO DE ESTIPULANTES'

  /* barra de status */
  CALL FSSTEXT  'Usuario: 'lc_userid   ,2,2,,#PROT+#WHITE
  CALL FSSTEXT  COPIES('?',78)         ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Selecione a operacao desejada:' ,5,24,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('?',50)                   ,6,14,,#PROT+#BLUE

  CALL FSSTEXT  ' 1  -  CONSULTAR    Consulta de estipulante por CNPJ/Nome' ,8,1
  CALL FSSTEXT  ' 2  -  INCLUIR      Incluir novo estipulante'               ,9,
  CALL FSSTEXT  ' 3  -  ALTERAR      Alterar dados cadastrais'               ,10
  CALL FSSTEXT  ' 4  -  SUBSTIPUL    Gestao de subestipulantes'              ,11
  CALL FSSTEXT  ' 5  -  PLANOS       Vincular planos VGC/GLB'                ,12
  CALL FSSTEXT  ' 6  -  LISTAR       Listar todos os estipulantes'           ,13

  CALL FSSTEXT  COPIES('?',50)  ,14,14,,#PROT+#BLUE

  CALL FSSTEXT   'Opcao ===>'   ,16,12,,#PROT+#WHITE+#HI
  CALL FSSFIELD  'opcao'        ,16,23,2,#YELLOW+#HI+#USCORE

  CALL FSSTEXT  COPIES('?',78) ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Menu Principal   PF12=Cancelar' ,24,20,,#PROT+#WHITE

  CALL FSSCURSOR 'opcao'
  CALL FSSDISPLAY

  key = FSSKEY(CHAR)

  IF key = 'PF03' | key = 'PF12' THEN DO
    CALL FSSTERM
    RETURN
  END
  IF key <> 'ENTER' THEN ITERATE

  CALL FSSFGETALL
  opcao = STRIP(opcao)

  SELECT
    WHEN opcao = '1' THEN CALL LC_CONSULTAR_ESTIP
    WHEN opcao = '2' THEN CALL LC_INCLUIR_ESTIP
    WHEN opcao = '3' THEN CALL LC_ALTERAR_ESTIP
    WHEN opcao = '4' THEN CALL LC_SUBSTIPUL
    WHEN opcao = '5' THEN CALL LC_PLANOS_ESTIP
    WHEN opcao = '6' THEN CALL LC_LISTAR_ESTIP
    WHEN opcao = '' THEN CALL FSSZERRSM 'Selecione uma opcao'
    OTHERWISE CALL FSSZERRSM 'Opcao invalida'
  END

  CALL FSSINIT

END

CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_CONSULTAR_ESTIP - Tela de consulta por CNPJ ou Nome               */
/* -------------------------------------------------------------------- */
LC_CONSULTAR_ESTIP:
  cnpj_est = ''
  nome_est = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  CONSULTA DE ESTIPULANTE'
  CALL FSSTEXT  COPIES('?',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Informe o criterio de consulta:' ,5,24,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('?',50)                    ,6,14,,#PROT+#BLUE

  CALL FSSTEXT   'CNPJ         : '  ,9,14,,#PROT+#WHITE
  CALL FSSFIELD  'cnpj_est'         ,9,29,18,#GREEN+#USCORE

  CALL FSSTEXT   'Nome Empresa : '  ,11,14,,#PROT+#WHITE
  CALL FSSFIELD  'nome_est'         ,11,29,40,#GREEN+#USCORE

  CALL FSSTEXT  '(Informe CNPJ ou parte do nome para pesquisar)' ,13,16,,#PROT+#

  CALL FSSTEXT  COPIES('?',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Pesquisar   PF3=Voltar   PF12=Cancelar'  ,24,16,,#PROT+#W

  CALL FSSCURSOR 'cnpj_est'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      cnpj_est = STRIP(cnpj_est)
      nome_est = STRIP(nome_est)
      IF cnpj_est = '' & nome_est = '' THEN DO
        CALL FSSZERRSM 'Informe CNPJ ou Nome'
        ITERATE
      END
      /* aqui chamaria a rotina de busca no DB2 */
      /* por ora exibe mensagem de desenvolvimento */
      CALL FSSZERRSM 'Consulta DB2: em desenvolvimento'
    END
  END
  CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_INCLUIR_ESTIP - Tela de inclusao de novo estipulante              */
/* -------------------------------------------------------------------- */
LC_INCLUIR_ESTIP:
  est_codigo = ''
  est_cnpj = ''
  est_nome = ''
  est_reduz = ''
  est_uf = ''
  est_cid = ''
  est_cont = ''
  est_email = ''
  est_tel = ''
  est_plano = ''
  est_segur = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  INCLUSAO DE ESTIPULANTE'
  CALL FSSTEXT  COPIES('?',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Cadastro estipulante e vinculos:' ,5,20,,#PROT+#YELLOW+#H
  CALL FSSTEXT  COPIES('?',60)                    ,6,10,,#PROT+#BLUE

  CALL FSSTEXT  'Codigo (6 digitos) : ' ,7,3,,#PROT+#WHITE
  CALL FSSFIELD 'est_codigo' ,7,25,6,#GREEN+#USCORE+#NUM

  CALL FSSTEXT  'CNPJ (14 digitos) : ' ,8,3,,#PROT+#WHITE
  CALL FSSFIELD 'est_cnpj' ,8,25,14,#GREEN+#USCORE+#NUM

  CALL FSSTEXT  'Razao Social : ' ,9,3,,#PROT+#WHITE
  CALL FSSFIELD 'est_nome' ,9,25,54,#GREEN+#USCORE

  CALL FSSTEXT  'Nome reduzido : ' ,10,3,,#PROT+#WHITE
  CALL FSSFIELD 'est_reduz' ,10,25,30,#GREEN+#USCORE

  CALL FSSTEXT  'UF : ' ,11,3,,#PROT+#WHITE
  CALL FSSFIELD 'est_uf' ,11,8,2,#GREEN+#USCORE
  CALL FSSTEXT  'Cidade : ' ,11,12,,#PROT+#WHITE
  CALL FSSFIELD 'est_cid' ,11,21,25,#GREEN+#USCORE

  CALL FSSTEXT  'Contato principal : ' ,12,3,,#PROT+#WHITE
  CALL FSSFIELD 'est_cont' ,12,25,30,#GREEN+#USCORE

  CALL FSSTEXT  'E-mail : ' ,13,3,,#PROT+#WHITE
  CALL FSSFIELD 'est_email' ,13,25,45,#GREEN+#USCORE
  CALL FSSTEXT  'Telefone : ' ,14,3,,#PROT+#WHITE
  CALL FSSFIELD 'est_tel' ,14,25,20,#GREEN+#USCORE
  CALL FSSTEXT  'Produto VGC/GLB : ' ,15,3,,#PROT+#WHITE
  CALL FSSFIELD 'est_plano' ,15,25,3,#GREEN+#USCORE
  CALL FSSTEXT  'Codigo seguradora : ' ,16,3,,#PROT+#WHITE
  CALL FSSFIELD 'est_segur' ,16,25,6,#GREEN+#USCORE+#NUM
  CALL FSSTEXT  'ES=Estipulante; 1 seguradora por cadastro.' ,18,3,,#PROT+#TURQ
  CALL FSSTEXT  'Corretores: vinculo em rotina propria.' ,19,3,,#PROT+#TURQ
  CALL FSSTEXT  'Prototipo sem gravacao no MVS/API.' ,20,3,,#PROT+#YELLOW+#H

  CALL FSSTEXT  COPIES('?',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Validar PF3=Cancelar PF12=Voltar' ,24,18,,#PROT+#WHIT

  CALL FSSCURSOR 'est_codigo'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      est_codigo = STRIP(est_codigo)
      est_cnpj = STRIP(est_cnpj)
      est_nome = STRIP(est_nome)
      est_cont = STRIP(est_cont)
      est_email = STRIP(est_email)
      est_plano = TRANSLATE(STRIP(est_plano))
      est_segur = STRIP(est_segur)

      invalido = (LENGTH(est_codigo) <> 6) | ,
                 (VERIFY(est_codigo,'0123456789') <> 0)
      IF invalido THEN DO
        CALL FSSZERRSM 'Codigo deve conter 6 digitos'
        CALL FSSCURSOR 'est_codigo'
        ITERATE
      END
      IF est_cnpj = '' THEN DO
        CALL FSSZERRSM 'CNPJ obrigatorio'
        CALL FSSCURSOR 'est_cnpj'
        ITERATE
      END
      invalido = (LENGTH(est_cnpj) <> 14) | ,
                 (VERIFY(est_cnpj,'0123456789') <> 0)
      IF invalido THEN DO
        CALL FSSZERRSM 'CNPJ deve conter 14 digitos'
        CALL FSSCURSOR 'est_cnpj'
        ITERATE
      END
      IF est_nome = '' THEN DO
        CALL FSSZERRSM 'Razao Social obrigatoria'
        CALL FSSCURSOR 'est_nome'
        ITERATE
      END
      IF est_cont = '' THEN DO
        CALL FSSZERRSM 'Contato principal obrigatorio'
        CALL FSSCURSOR 'est_cont'
        ITERATE
      END
      at_pos = POS('@',est_email)
      IF at_pos < 2 | at_pos = LENGTH(est_email) THEN DO
        CALL FSSZERRSM 'Informe um e-mail valido'
        CALL FSSCURSOR 'est_email'
        ITERATE
      END
      IF POS('.',est_email,at_pos + 2) = 0 THEN DO
        CALL FSSZERRSM 'Informe um e-mail valido'
        CALL FSSCURSOR 'est_email'
        ITERATE
      END
      IF est_plano <> 'VGC' & est_plano <> 'GLB' THEN DO
        CALL FSSZERRSM 'Produto deve ser VGC ou GLB'
        CALL FSSCURSOR 'est_plano'
        ITERATE
      END
      invalido = (LENGTH(est_segur) <> 6) | ,
                 (VERIFY(est_segur,'0123456789') <> 0)
      IF invalido THEN DO
        CALL FSSZERRSM 'Informe o codigo de uma seguradora'
        CALL FSSCURSOR 'est_segur'
        ITERATE
      END
      CALL FSSZERRSM 'Dados validados; prototipo sem gravacao'
    END
  END
  CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_ALTERAR_ESTIP - stub                                               */
/* -------------------------------------------------------------------- */
LC_ALTERAR_ESTIP:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE 'LIFECORE IQ  -  ALTERACAO DE ESTIPULANTE'
  CALL FSSTEXT  'Em desenvolvimento - Sprint 2' ,12,25,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  'PF3=Voltar' ,14,35,,#PROT+#WHITE
  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_SUBSTIPUL - stub                                                   */
/* -------------------------------------------------------------------- */
LC_SUBSTIPUL:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE 'LIFECORE IQ  -  SUBESTIPULANTES'
  CALL FSSTEXT  'Em desenvolvimento - Sprint 2' ,12,25,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  'PF3=Voltar' ,14,35,,#PROT+#WHITE
  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_PLANOS_ESTIP - stub                                                */
/* -------------------------------------------------------------------- */
LC_PLANOS_ESTIP:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE 'LIFECORE IQ  -  PLANOS VGC/GLB'
  CALL FSSTEXT  'Em desenvolvimento - Sprint 2' ,12,25,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  'PF3=Voltar' ,14,35,,#PROT+#WHITE
  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_LISTAR_ESTIP - Lista estipulantes (simulacao)                      */
/* -------------------------------------------------------------------- */
LC_LISTAR_ESTIP:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE 'LIFECORE IQ  -  LISTA DE ESTIPULANTES'
  CALL FSSTEXT  COPIES('?',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Nr  CNPJ              Razao Social                    UF  Sit' 
  CALL FSSTEXT  COPIES('?',76)  ,6,2,,#PROT+#BLUE

  /* dados de exemplo */
  CALL FSSTEXT  ' 1  11222333000181    LIFECORE SEGUROS DE VIDA S.A.   SP  AT' ,
  CALL FSSTEXT  ' 2  44555666000195    GRUPO ALPHA SAUDE COLETIVA       RJ  AT' 
  CALL FSSTEXT  ' 3  77888999000112    BETA SERVICOS EMPRESARIAIS       MG  AT' 
  CALL FSSTEXT  ' 4  22111333000174    CONSTRUTORA OMEGA LTDA           RS  SU' 

  CALL FSSTEXT  COPIES('?',76)         ,11,2,,#PROT+#BLUE
  CALL FSSTEXT  '4 estipulantes encontrados'  ,12,2,,#PROT+#TURQ
  CALL FSSTEXT  'Sit: AT=Ativo  SU=Suspenso  CA=Cancelado' ,13,2,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('?',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Voltar   PF7=Anterior   PF8=Proximo' ,24,19,,#PROT+#WHITE

  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN
./ ADD NAME=LCFATUR
/* REXX ----------------------------------------------------------------*
 * LCFATUR  - LifeCore IQ - Faturamento                                 *
 *            Geracao de faturas mensais com reajuste IPCA              *
 * Autor  : LifeCore IQ                                                 *
 * Data   : 2026-10-04                                                  *
 * Versao : 1.0.0                                                       *
 * ------------------------------------------------------------------  */

ARG lc_userid .

CALL IMPORT FSSAPI
ADDRESS FSS
CALL FSSINIT

DO forever

  opcao  = ''
  ZERRSM = ''

  CALL FSSTITLE  'LIFECORE IQ  -  FATURAMENTO'

  CALL FSSTEXT  'Usuario: 'lc_userid   ,2,2,,#PROT+#WHITE
  CALL FSSTEXT  COPIES('?',78)         ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Selecione a operacao:' ,5,28,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('?',50)         ,6,14,,#PROT+#BLUE

  CALL FSSTEXT  ' 1  -  GERAR        Gerar fatura mensal por estipulante'  ,8,12
  CALL FSSTEXT  ' 2  -  CONSULTAR    Consultar faturas por competencia'    ,9,12
  CALL FSSTEXT  ' 3  -  IPCA         Consultar taxa IPCA vigente'         ,10,12
  CALL FSSTEXT  ' 4  -  DIVERGENCIAS Listar divergencias de faturamento'  ,11,12
  CALL FSSTEXT  ' 5  -  FECHAR       Fechamento mensal de faturamento'    ,12,12

  CALL FSSTEXT  COPIES('?',50)  ,13,14,,#PROT+#BLUE

  /* info IPCA vigente - simulacao */
  CALL FSSTEXT  'IPCA vigente (OUT/2026): 0,44%' ,15,22,,#PROT+#TURQ+#HI

  CALL FSSTEXT   'Opcao ===>'  ,17,12,,#PROT+#WHITE+#HI
  CALL FSSFIELD  'opcao'       ,17,23,2,#YELLOW+#HI+#USCORE

  CALL FSSTEXT  COPIES('?',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Menu Principal   PF12=Cancelar'  ,24,20,,#PROT+#WHITE

  CALL FSSCURSOR 'opcao'
  CALL FSSDISPLAY

  key = FSSKEY(CHAR)

  IF key = 'PF03' | key = 'PF12' THEN DO
    CALL FSSTERM
    RETURN
  END
  IF key <> 'ENTER' THEN ITERATE

  CALL FSSFGETALL
  opcao = STRIP(opcao)

  SELECT
    WHEN opcao = '1' THEN CALL LC_GERAR_FATURA
    WHEN opcao = '2' THEN CALL LC_CONSULTAR_FATURA
    WHEN opcao = '3' THEN CALL LC_IPCA
    WHEN opcao = '4' THEN CALL LC_DIVERGENCIAS
    WHEN opcao = '5' THEN CALL LC_FECHAR_FAT
    WHEN opcao = '' THEN CALL FSSZERRSM 'Selecione uma opcao'
    OTHERWISE CALL FSSZERRSM 'Opcao invalida'
  END

  CALL FSSINIT

END

CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_GERAR_FATURA                                                       */
/* -------------------------------------------------------------------- */
LC_GERAR_FATURA:
  fat_estip   = ''
  fat_compet  = DATE('S')
  fat_compet  = LEFT(fat_compet,6)

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  GERAR FATURA'
  CALL FSSTEXT  COPIES('?',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Parametros para geracao de fatura:' ,5,22,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('?',55)                       ,6,12,,#PROT+#BLUE

  CALL FSSTEXT   'Nr Estipulante  : '  ,8,14,,#PROT+#WHITE
  CALL FSSFIELD  'fat_estip'           ,8,32,10,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'Competencia     : '  ,10,14,,#PROT+#WHITE
  CALL FSSFIELD  'fat_compet'          ,10,32,6,#GREEN+#USCORE+#NUM ,fat_compet
  CALL FSSTEXT  '(formato: AAAAMM  ex: 202610)'  ,11,32,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('?',55)  ,12,12,,#PROT+#BLUE

  CALL FSSTEXT  'ATENCAO: Apolice deve estar com status AT (Ativa)' ,13,14,,#PRO

  CALL FSSTEXT  COPIES('?',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Gerar   PF3=Cancelar' ,24,26,,#PROT+#WHITE

  CALL FSSCURSOR 'fat_estip'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      fat_estip  = STRIP(fat_estip)
      fat_compet = STRIP(fat_compet)
      IF fat_estip = '' THEN DO
        CALL FSSZERRSM 'Nr Estipulante obrigatorio'
        CALL FSSCURSOR 'fat_estip'
        ITERATE
      END
      IF LENGTH(fat_compet) <> 6 THEN DO
        CALL FSSZERRSM 'Competencia invalida (AAAAMM)'
        CALL FSSCURSOR 'fat_compet'
        ITERATE
      END
      /* aqui acionaria o job FATURA01 via SUBMIT */
      CALL FSSZERRSM 'Fatura gerada! (simulacao)'
    END
  END
  CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_CONSULTAR_FATURA                                                   */
/* -------------------------------------------------------------------- */
LC_CONSULTAR_FATURA:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  CONSULTA DE FATURAS'
  CALL FSSTEXT  COPIES('?',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Nr  Estipulante   Competencia  Valor        Vencimento  Situaca
  CALL FSSTEXT  COPIES('?',76)  ,6,2,,#PROT+#BLUE

  CALL FSSTEXT  ' 1  LIFECORE SEG  202609       R$ 45.890,00  2026/10/10  PAGO' 
  CALL FSSTEXT  ' 2  GRUPO ALPHA   202609       R$ 23.450,00  2026/10/10  ABERTO
  CALL FSSTEXT  ' 3  BETA SERVICOS 202609       R$  8.120,00  2026/10/10  VENCID

  CALL FSSTEXT  COPIES('?',76)  ,10,2,,#PROT+#BLUE
  CALL FSSTEXT  '3 faturas encontradas - Competencia: 09/2026' ,11,2,,#PROT+#TUR

  CALL FSSTEXT  COPIES('?',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Voltar   PF7=Anterior   PF8=Proximo' ,24,19,,#PROT+#WHITE

  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_IPCA                                                               */
/* -------------------------------------------------------------------- */
LC_IPCA:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  TAXA IPCA SUSEP'
  CALL FSSTEXT  COPIES('?',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Mes/Ano    Indice  Acumulado 12m' ,5,22,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('?',36)  ,6,22,,#PROT+#BLUE

  CALL FSSTEXT  'OUT/2026    0,44%    4,83%'  ,7,22,,#PROT+#GREEN
  CALL FSSTEXT  'SET/2026    0,44%    4,42%'  ,8,22,,#PROT+#WHITE
  CALL FSSTEXT  'AGO/2026    0,44%    4,50%'  ,9,22,,#PROT+#WHITE
  CALL FSSTEXT  'JUL/2026    0,38%    4,40%'  ,10,22,,#PROT+#WHITE
  CALL FSSTEXT  'JUN/2026    0,36%    4,06%'  ,11,22,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('?',36)  ,12,22,,#PROT+#BLUE
  CALL FSSTEXT  'Fonte: SUSEP / IBGE'  ,13,22,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('?',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Voltar'  ,24,35,,#PROT+#WHITE

  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_DIVERGENCIAS e LC_FECHAR_FAT - stubs                              */
/* -------------------------------------------------------------------- */
LC_DIVERGENCIAS:
LC_FECHAR_FAT:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE 'LIFECORE IQ  -  FATURAMENTO'
  CALL FSSTEXT  'Em desenvolvimento - Sprint 2' ,12,25,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  'PF3=Voltar' ,14,35,,#PROT+#WHITE
  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN
./ ADD NAME=LCBATCH
/* REXX ----------------------------------------------------------------*
 * LCBATCH  - LifeCore IQ - Submissao de Jobs Batch                    *
 *            Interface para submeter JCLs do LifeCore                  *
 * Autor  : LifeCore IQ                                                 *
 * Data   : 2026-10-04                                                  *
 * ------------------------------------------------------------------  */

ARG lc_userid .

CALL IMPORT FSSAPI
ADDRESS FSS
CALL FSSINIT

DO forever

  opcao  = ''
  ZERRSM = ''

  CALL FSSTITLE  'LIFECORE IQ  -  PROCESSAMENTO BATCH'

  CALL FSSTEXT  'Usuario: 'lc_userid   ,2,2,,#PROT+#WHITE
  CALL FSSTEXT  COPIES('?',78)         ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Selecione o job para submeter:' ,5,24,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('?',55)                   ,6,12,,#PROT+#BLUE

  CALL FSSTEXT  ' 1  -  LCDIA01    Ciclo diario completo (13 steps)'    ,8,12,,#
  CALL FSSTEXT  ' 2  -  LCIMP01    Importacao de arquivo de empresa'    ,9,12,,#
  CALL FSSTEXT  ' 3  -  FATURA01   Geracao de fatura batch'            ,10,12,,#
  CALL FSSTEXT  ' 4  -  ARQVAL01   Validacao de arquivo'               ,11,12,,#
  CALL FSSTEXT  ' 5  -  CONCIL01   Conciliacao faturado x pago'        ,12,12,,#
  CALL FSSTEXT  ' 6  -  COMIS01    Calculo de comissoes'               ,13,12,,#
  CALL FSSTEXT  ' 7  -  VGCCAP01   Calculo de capital segurado'        ,14,12,,#

  CALL FSSTEXT  COPIES('?',55)  ,15,12,,#PROT+#BLUE
  CALL FSSTEXT  ' 9  -  SDSF       Ver output dos jobs submetidos'     ,16,12,,#

  CALL FSSTEXT   'Opcao ===>'  ,18,12,,#PROT+#WHITE+#HI
  CALL FSSFIELD  'opcao'       ,18,23,2,#YELLOW+#HI+#USCORE

  CALL FSSTEXT  COPIES('?',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Menu Principal   PF12=Cancelar'  ,24,20,,#PROT+#WHITE

  CALL FSSCURSOR 'opcao'
  CALL FSSDISPLAY

  key = FSSKEY(CHAR)

  IF key = 'PF03' | key = 'PF12' THEN DO
    CALL FSSTERM
    RETURN
  END
  IF key <> 'ENTER' THEN ITERATE

  CALL FSSFGETALL
  opcao = STRIP(opcao)

  SELECT
    WHEN opcao = '1' THEN CALL LC_SUBMIT 'LCDIA01'
    WHEN opcao = '2' THEN CALL LC_SUBMIT 'LCIMP01'
    WHEN opcao = '3' THEN CALL LC_SUBMIT 'FATURA01'
    WHEN opcao = '4' THEN CALL LC_SUBMIT 'ARQVAL01'
    WHEN opcao = '5' THEN CALL LC_SUBMIT 'CONCIL01'
    WHEN opcao = '6' THEN CALL LC_SUBMIT 'COMIS01'
    WHEN opcao = '7' THEN CALL LC_SUBMIT 'VGCCAP01'
    WHEN opcao = '9' THEN DO
      CALL FSSTERM
      ADDRESS TSO "SDSF"
      CALL FSSINIT
    END
    WHEN opcao = '' THEN CALL FSSZERRSM 'Selecione uma opcao'
    OTHERWISE CALL FSSZERRSM 'Opcao invalida'
  END

  CALL FSSINIT

END

CALL FSSTERM
RETURN

/* -------------------------------------------------------------------- */
/* LC_SUBMIT - Submete um JCL do dataset LIFECORE.JCL                   */
/* -------------------------------------------------------------------- */
LC_SUBMIT:
  ARG jcl_nome .
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  SUBMETER JOB: 'jcl_nome
  CALL FSSTEXT  COPIES('?',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Job a submeter : 'jcl_nome          ,6,18,,#PROT+#WHITE
  CALL FSSTEXT  'Dataset        : LIFECORE.JCL('jcl_nome')' ,7,18,,#PROT+#TURQ

  CALL FSSTEXT  'Deseja submeter o job? (S/N)'  ,10,24,,#PROT+#YELLOW+#HI
  confirm = 'N'
  CALL FSSFIELD  'confirm'  ,10,53,1,#GREEN+#USCORE,'N'

  CALL FSSTEXT  COPIES('?',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Confirmar   PF3=Cancelar'  ,24,24,,#PROT+#WHITE

  CALL FSSCURSOR 'confirm'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      confirm = STRIP(TRANSLATE(confirm))
      IF confirm = 'S' THEN DO
        ADDRESS TSO "SUBMIT 'LIFECORE.JCL("jcl_nome")'"
        IF RC = 0 THEN
          CALL FSSZERRSM jcl_nome' submetido com sucesso'
        ELSE
          CALL FSSZERRSM 'Erro ao submeter: RC='RC
      END
      ELSE
        CALL FSSZERRSM 'Submissao cancelada'
      LEAVE
    END
  END
  CALL FSSTERM
RETURN
@@
//
