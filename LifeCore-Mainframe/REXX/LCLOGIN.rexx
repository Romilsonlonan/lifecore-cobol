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

/* ------- credenciais admin (fixas por ora — futuramente DB2) -------- */
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

  CALL FSSTEXT COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  /* logo compacto */
  CALL FSSTEXT '   ██╗     ██╗███████╗███████╗ ██████╗ ██████╗ ██████╗ ███████╗'  ,5,7,,#PROT+#TURQ
  CALL FSSTEXT '   ██║     ██║██╔════╝██╔════╝██╔════╝██╔═══██╗██╔══██╗██╔════╝'  ,6,7,,#PROT+#TURQ
  CALL FSSTEXT '   ██║     ██║█████╗  █████╗  ██║     ██║   ██║██████╔╝█████╗  '  ,7,7,,#PROT+#TURQ
  CALL FSSTEXT '   ███████╗██║██║     ███████╗╚██████╗╚██████╔╝██║  ██║███████╗'  ,8,7,,#PROT+#TURQ
  CALL FSSTEXT '   Gestao de Apolices  /  Segurados  /  Faturamento  /  Sinistros' ,9,7,,#PROT+#WHITE

  CALL FSSTEXT COPIES('─',78)  ,10,1,78,#PROT+#BLUE

  /* ---- tipo de acesso ---------------------------------------------- */
  CALL FSSTEXT 'Tipo de Acesso :'                 ,12,16,,#PROT+#YELLOW+#HI
  CALL FSSTEXT 'A=Administrador  E=Estipulante/Corretor' ,12,34,,#PROT+#WHITE
  CALL FSSFIELD 'lc_tipo'                         ,12,33,1,#GREEN+#HI+#USCORE,'A'

  CALL FSSTEXT COPIES('─',46)  ,13,16,,#PROT+#BLUE

  /* ---- campos de login --------------------------------------------- */
  CALL FSSTEXT  'Usuario        :'  ,15,16,,#PROT+#WHITE
  CALL FSSFIELD 'lc_user'           ,15,33,10,#GREEN+#USCORE

  CALL FSSTEXT  'Apólice        :'  ,16,16,,#PROT+#WHITE
  CALL FSSTEXT  '(somente para Estipulante/Corretor)' ,16,46,,#PROT+#TURQ
  CALL FSSFIELD 'lc_apolice'        ,16,33,10,#GREEN+#USCORE

  CALL FSSTEXT  'Senha          :'  ,18,16,,#PROT+#WHITE
  CALL FSSFIELD 'lc_pass'           ,18,33,10,#GREEN+#NON+#USCORE

  /* tentativas restantes */
  IF tentativas > 0 THEN DO
    rest = MAX_TENT - tentativas
    CALL FSSTEXT 'Tentativas restantes: 'rest  ,20,26,,#PROT+#RED+#HI
  END

  CALL FSSTEXT COPIES('═',78)  ,22,1,78,#PROT+#BLUE
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

  /* ---- autenticacao ESTIPULANTE/CORRETOR (stub — futuramente DB2) -- */
  IF lc_tipo = 'E' THEN DO
    /* por ora valida dummy: qualquer usuario cadastrado retorna OK */
    /* futuramente: SELECT FROM USUARIOS_ACESSO WHERE
         CD_APOLICE=lc_apolice AND DS_LOGIN=lc_user
         AND DS_SENHA=ENCRYPT(lc_pass) */
    IF lc_apolice = '0000000001' & lc_user = 'TESTE' & lc_pass = 'TESTE123' THEN DO
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
