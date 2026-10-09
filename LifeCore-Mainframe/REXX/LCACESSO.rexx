/* REXX ----------------------------------------------------------------*
 * LCACESSO - LifeCore IQ - Gestao de Acessos                           *
 *            Exclusivo para ADMIN                                       *
 *            Cadastra login/senha de Estipulantes e Corretores          *
 *            para acesso ao modulo de servicos (LCSVC)                  *
 *                                                                       *
 * Modelo da tabela (futuramente DB2):                                   *
 *   USUARIOS_ACESSO                                                     *
 *     CD_APOLICE   CHAR(10)  - nr da apolice da empresa                 *
 *     DS_LOGIN     CHAR(10)  - login do estipulante/corretor            *
 *     DS_SENHA     CHAR(10)  - senha (criptografada no DB2)             *
 *     TP_PERFIL    CHAR(2)   - ES=Estipulante  CO=Corretor              *
 *     DT_CRIACAO   DATE                                                 *
 *     DT_EXPIRA    DATE      - expiracao da senha (90 dias)             *
 *     ST_ATIVO     CHAR(1)   - A=Ativo  B=Bloqueado  I=Inativo          *
 *     DS_CRIADO_POR CHAR(10) - login do admin que cadastrou             *
 *                                                                       *
 * Autor  : LifeCore IQ                                                  *
 * Data   : 2026-10-04                                                   *
 * Versao : 1.0.0                                                        *
 * ------------------------------------------------------------------  */

ARG lc_admin .

IF lc_admin = '' THEN lc_admin = 'LCADMIN'

CALL IMPORT FSSAPI
ADDRESS FSS
CALL FSSINIT

/* ------- simula tabela em memoria (futuramente DB2) ----------------- */
/* estrutura: ACESSO.n = apolice|login|tp_perfil|st_ativo|dt_criacao   */
ACESSO.0 = 3
ACESSO.1 = '0000000001|TESTE   |ES|A|04/10/2026'
ACESSO.2 = '0000000001|CORRETOR|CO|A|04/10/2026'
ACESSO.3 = '0000000002|ESTIP02 |ES|B|01/10/2026'

/* ------- loop principal -------------------------------------------- */
DO forever

  opcao  = ''
  ZERRSM = ''

  CALL FSSTITLE  'LIFECORE IQ  -  GESTAO DE ACESSOS  [ADMIN: 'lc_admin']'

  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Gerencie os logins de Estipulantes e Corretores:' ,5,16,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',55)                                     ,6,12,,#PROT+#BLUE

  CALL FSSTEXT  ' 1  -  INCLUIR     Cadastrar novo login'                ,8,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 2  -  ALTERAR     Alterar dados ou redefinir senha'    ,9,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 3  -  BLOQUEAR    Bloquear acesso de um usuario'       ,10,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 4  -  ATIVAR      Reativar usuario bloqueado'          ,11,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 5  -  LISTAR      Listar todos os acessos cadastrados' ,12,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 6  -  CONSULTAR   Consultar por apolice'               ,13,12,,#PROT+#GREEN

  CALL FSSTEXT  COPIES('─',55)  ,14,12,,#PROT+#BLUE

  /* totalizadores simulados */
  tot_at = 0; tot_bl = 0
  DO i = 1 TO ACESSO.0
    IF WORD(TRANSLATE(ACESSO.i,'  ','|'),4) = 'A' THEN tot_at = tot_at + 1
    ELSE tot_bl = tot_bl + 1
  END
  CALL FSSTEXT  'Usuarios ativos: 'tot_at'   Bloqueados: 'tot_bl  ,15,18,,#PROT+#TURQ

  CALL FSSTEXT   'Opcao ===>'  ,17,12,,#PROT+#WHITE+#HI
  CALL FSSFIELD  'opcao'       ,17,23,2,#YELLOW+#HI+#USCORE

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
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
    WHEN opcao = '1' THEN CALL LC_INCLUIR_ACESSO
    WHEN opcao = '2' THEN CALL LC_ALTERAR_ACESSO
    WHEN opcao = '3' THEN CALL LC_BLOQUEAR_ACESSO
    WHEN opcao = '4' THEN CALL LC_ATIVAR_ACESSO
    WHEN opcao = '5' THEN CALL LC_LISTAR_ACESSOS
    WHEN opcao = '6' THEN CALL LC_CONSULTAR_APOLICE
    WHEN opcao = '' THEN CALL FSSZERRSM 'Selecione uma opcao'
    OTHERWISE CALL FSSZERRSM 'Opcao invalida'
  END

  CALL FSSINIT

END

CALL FSSTERM
RETURN

/* ==================================================================== */
/* LC_INCLUIR_ACESSO - Cadastrar novo login Estipulante ou Corretor      */
/* ==================================================================== */
LC_INCLUIR_ACESSO:
  ac_apolice = ''
  ac_login   = ''
  ac_senha   = ''
  ac_confirm = ''
  ac_perfil  = 'ES'
  ac_nome    = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  INCLUIR ACESSO'
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Preencha os dados do novo usuario de acesso:' ,5,18,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',55)  ,6,12,,#PROT+#BLUE

  CALL FSSTEXT   'Nr Apolice     :'  ,8,14,,#PROT+#WHITE
  CALL FSSFIELD  'ac_apolice'        ,8,31,10,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'Nome / Empresa :'  ,9,14,,#PROT+#WHITE
  CALL FSSFIELD  'ac_nome'           ,9,31,40,#GREEN+#USCORE

  CALL FSSTEXT   'Login          :'  ,10,14,,#PROT+#WHITE
  CALL FSSFIELD  'ac_login'          ,10,31,10,#GREEN+#USCORE
  CALL FSSTEXT  '(max 10 caracteres, sem espacos)'  ,10,42,,#PROT+#TURQ

  CALL FSSTEXT   'Senha          :'  ,12,14,,#PROT+#WHITE
  CALL FSSFIELD  'ac_senha'          ,12,31,10,#GREEN+#NON+#USCORE
  CALL FSSTEXT  '(min 6 / max 10 caracteres)'  ,12,42,,#PROT+#TURQ

  CALL FSSTEXT   'Confirmar Senha:'  ,13,14,,#PROT+#WHITE
  CALL FSSFIELD  'ac_confirm'        ,13,31,10,#GREEN+#NON+#USCORE

  CALL FSSTEXT   'Perfil         :'  ,15,14,,#PROT+#WHITE
  CALL FSSFIELD  'ac_perfil'         ,15,31,2,#GREEN+#USCORE,'ES'
  CALL FSSTEXT  'ES=Estipulante  CO=Corretor'  ,15,34,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('─',55)  ,16,12,,#PROT+#BLUE
  CALL FSSTEXT  'Senha expira em 90 dias. Admin sera notificado apos 3 erros.' ,17,14,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Incluir   PF3=Cancelar'  ,24,25,,#PROT+#WHITE

  CALL FSSCURSOR 'ac_apolice'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE

    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      ac_apolice = STRIP(ac_apolice)
      ac_login   = STRIP(ac_login)
      ac_senha   = STRIP(ac_senha)
      ac_confirm = STRIP(ac_confirm)
      ac_perfil  = STRIP(TRANSLATE(ac_perfil))
      ac_nome    = STRIP(ac_nome)

      /* validacoes */
      IF ac_apolice = '' THEN DO
        CALL FSSZERRSM 'Nr Apolice obrigatorio'
        CALL FSSCURSOR 'ac_apolice'; ITERATE
      END
      IF ac_login = '' THEN DO
        CALL FSSZERRSM 'Login obrigatorio'
        CALL FSSCURSOR 'ac_login'; ITERATE
      END
      IF LENGTH(ac_login) < 3 THEN DO
        CALL FSSZERRSM 'Login deve ter no minimo 3 caracteres'
        CALL FSSCURSOR 'ac_login'; ITERATE
      END
      IF ac_senha = '' THEN DO
        CALL FSSZERRSM 'Senha obrigatoria'
        CALL FSSCURSOR 'ac_senha'; ITERATE
      END
      IF LENGTH(ac_senha) < 6 THEN DO
        CALL FSSZERRSM 'Senha deve ter no minimo 6 caracteres'
        CALL FSSCURSOR 'ac_senha'; ITERATE
      END
      IF ac_senha <> ac_confirm THEN DO
        CALL FSSZERRSM 'Senha e confirmacao nao conferem'
        CALL FSSCURSOR 'ac_confirm'; ITERATE
      END
      IF ac_perfil <> 'ES' & ac_perfil <> 'CO' THEN DO
        CALL FSSZERRSM 'Perfil invalido: ES ou CO'
        CALL FSSCURSOR 'ac_perfil'; ITERATE
      END

      /* aqui: INSERT INTO USUARIOS_ACESSO ... */
      /* simula inclusao na tabela em memoria */
      n = ACESSO.0 + 1
      ACESSO.n = ac_apolice'|'LEFT(ac_login,8)'|'ac_perfil'|A|'DATE('E')
      ACESSO.0 = n

      CALL FSSZERRSM 'Acesso incluido: 'ac_login' / Apolice: 'ac_apolice
    END
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* LC_ALTERAR_ACESSO - Redefinir senha ou alterar dados                  */
/* ==================================================================== */
LC_ALTERAR_ACESSO:
  al_apolice = ''
  al_login   = ''
  al_nsenha  = ''
  al_confirm = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  ALTERAR / REDEFINIR SENHA'
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Informe o usuario para alterar:' ,5,24,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',50)  ,6,14,,#PROT+#BLUE

  CALL FSSTEXT   'Nr Apolice  :'  ,8,18,,#PROT+#WHITE
  CALL FSSFIELD  'al_apolice'     ,8,32,10,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'Login       :'  ,9,18,,#PROT+#WHITE
  CALL FSSFIELD  'al_login'       ,9,32,10,#GREEN+#USCORE

  CALL FSSTEXT  COPIES('─',50)  ,10,14,,#PROT+#BLUE
  CALL FSSTEXT  'Nova Senha  :'   ,12,18,,#PROT+#WHITE
  CALL FSSFIELD  'al_nsenha'      ,12,32,10,#GREEN+#NON+#USCORE

  CALL FSSTEXT  'Confirmar   :'   ,13,18,,#PROT+#WHITE
  CALL FSSFIELD  'al_confirm'     ,13,32,10,#GREEN+#NON+#USCORE

  CALL FSSTEXT  '(deixe em branco para nao alterar a senha)'  ,15,18,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Salvar   PF3=Cancelar'  ,24,26,,#PROT+#WHITE

  CALL FSSCURSOR 'al_apolice'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      al_apolice = STRIP(al_apolice)
      al_login   = STRIP(al_login)
      al_nsenha  = STRIP(al_nsenha)
      al_confirm = STRIP(al_confirm)

      IF al_apolice = '' | al_login = '' THEN DO
        CALL FSSZERRSM 'Apolice e Login obrigatorios'
        CALL FSSCURSOR 'al_apolice'; ITERATE
      END
      IF al_nsenha <> '' & al_nsenha <> al_confirm THEN DO
        CALL FSSZERRSM 'Nova senha e confirmacao nao conferem'
        CALL FSSCURSOR 'al_confirm'; ITERATE
      END
      IF al_nsenha <> '' & LENGTH(al_nsenha) < 6 THEN DO
        CALL FSSZERRSM 'Senha deve ter no minimo 6 caracteres'
        CALL FSSCURSOR 'al_nsenha'; ITERATE
      END

      /* aqui: UPDATE USUARIOS_ACESSO SET DS_SENHA=... */
      IF al_nsenha <> '' THEN
        CALL FSSZERRSM 'Senha redefinida para: 'al_login' / Apolice: 'al_apolice
      ELSE
        CALL FSSZERRSM 'Dados atualizados: 'al_login
    END
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* LC_BLOQUEAR_ACESSO - Bloquear usuario                                 */
/* ==================================================================== */
LC_BLOQUEAR_ACESSO:
  bl_apolice = ''
  bl_login   = ''
  bl_motivo  = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  BLOQUEAR ACESSO'
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Bloquear acesso de usuario:' ,5,26,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',50)  ,6,14,,#PROT+#BLUE

  CALL FSSTEXT   'Nr Apolice  :'  ,8,18,,#PROT+#WHITE
  CALL FSSFIELD  'bl_apolice'     ,8,32,10,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'Login       :'  ,9,18,,#PROT+#WHITE
  CALL FSSFIELD  'bl_login'       ,9,32,10,#GREEN+#USCORE

  CALL FSSTEXT   'Motivo      :'  ,11,18,,#PROT+#WHITE
  CALL FSSFIELD  'bl_motivo'      ,11,32,40,#GREEN+#USCORE
  CALL FSSTEXT   '(opcional — registrado no log de auditoria)'  ,12,18,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Bloquear   PF3=Cancelar'  ,24,24,,#PROT+#RED

  CALL FSSCURSOR 'bl_apolice'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      bl_apolice = STRIP(bl_apolice)
      bl_login   = STRIP(bl_login)
      IF bl_apolice = '' | bl_login = '' THEN DO
        CALL FSSZERRSM 'Apolice e Login obrigatorios'
        CALL FSSCURSOR 'bl_apolice'; ITERATE
      END
      /* aqui: UPDATE USUARIOS_ACESSO SET ST_ATIVO='B' WHERE ... */
      CALL FSSZERRSM 'Usuario BLOQUEADO: 'bl_login' / Apolice: 'bl_apolice
    END
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* LC_ATIVAR_ACESSO - Reativar usuario bloqueado                         */
/* ==================================================================== */
LC_ATIVAR_ACESSO:
  at_apolice = ''
  at_login   = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  ATIVAR / DESBLOQUEAR ACESSO'
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Reativar usuario bloqueado:' ,5,26,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',50)  ,6,14,,#PROT+#BLUE

  CALL FSSTEXT   'Nr Apolice  :'  ,8,18,,#PROT+#WHITE
  CALL FSSFIELD  'at_apolice'     ,8,32,10,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'Login       :'  ,9,18,,#PROT+#WHITE
  CALL FSSFIELD  'at_login'       ,9,32,10,#GREEN+#USCORE

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Ativar   PF3=Cancelar'  ,24,26,,#PROT+#GREEN

  CALL FSSCURSOR 'at_apolice'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      at_apolice = STRIP(at_apolice)
      at_login   = STRIP(at_login)
      IF at_apolice = '' | at_login = '' THEN DO
        CALL FSSZERRSM 'Apolice e Login obrigatorios'
        CALL FSSCURSOR 'at_apolice'; ITERATE
      END
      /* aqui: UPDATE USUARIOS_ACESSO SET ST_ATIVO='A' WHERE ... */
      CALL FSSZERRSM 'Usuario ATIVADO: 'at_login' / Apolice: 'at_apolice
    END
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* LC_LISTAR_ACESSOS - Listar todos os acessos                           */
/* ==================================================================== */
LC_LISTAR_ACESSOS:
  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  LISTA DE ACESSOS CADASTRADOS'
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Apolice    Login      Perfil  Situacao  Cadastrado em' ,5,2,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',76)  ,6,2,,#PROT+#BLUE

  row = 7
  DO i = 1 TO ACESSO.0
    PARSE VAR ACESSO.i apl '|' lgn '|' prf '|' sit '|' dtc
    IF sit = 'A' THEN cor = #GREEN
    ELSE cor = #RED
    prf_desc = 'Estipulante'
    IF prf = 'CO' THEN prf_desc = 'Corretor   '
    CALL FSSTEXT  ' 'apl'  'LEFT(lgn,10)' 'prf_desc' 'sit'         'dtc ,row,2,,#PROT+cor
    row = row + 1
    IF row > 18 THEN LEAVE  /* max 12 linhas por pagina */
  END

  CALL FSSTEXT  COPIES('─',76)            ,row,2,,#PROT+#BLUE
  CALL FSSTEXT  ACESSO.0' usuario(s) encontrado(s)' ,row+1,2,,#PROT+#TURQ
  CALL FSSTEXT  'Sit: A=Ativo  B=Bloqueado  I=Inativo' ,row+2,2,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Voltar   PF7=Anterior   PF8=Proximo' ,24,19,,#PROT+#WHITE

  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN

/* ==================================================================== */
/* LC_CONSULTAR_APOLICE - Ver todos os acessos de uma apolice            */
/* ==================================================================== */
LC_CONSULTAR_APOLICE:
  cq_apolice = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  CONSULTAR ACESSOS POR APOLICE'
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT   'Nr Apolice  :'  ,8,18,,#PROT+#WHITE
  CALL FSSFIELD  'cq_apolice'     ,8,32,10,#GREEN+#USCORE+#NUM

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Pesquisar   PF3=Voltar'  ,24,25,,#PROT+#WHITE

  CALL FSSCURSOR 'cq_apolice'
  CALL FSSDISPLAY

  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'PF12' THEN LEAVE
    IF key = 'ENTER' THEN DO
      CALL FSSFGETALL
      cq_apolice = STRIP(cq_apolice)
      IF cq_apolice = '' THEN DO
        CALL FSSZERRSM 'Informe o Nr da Apolice'
        CALL FSSCURSOR 'cq_apolice'; ITERATE
      END

      /* filtrar tabela em memoria */
      CALL FSSTERM
      CALL FSSINIT
      CALL FSSTITLE  'LIFECORE IQ  -  ACESSOS DA APOLICE 'cq_apolice
      CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE
      CALL FSSTEXT  'Login      Perfil       Situacao  Cadastrado em' ,5,10,,#PROT+#YELLOW+#HI
      CALL FSSTEXT  COPIES('─',58)  ,6,10,,#PROT+#BLUE

      row = 7; cnt = 0
      DO i = 1 TO ACESSO.0
        PARSE VAR ACESSO.i apl '|' lgn '|' prf '|' sit '|' dtc
        IF STRIP(apl) <> STRIP(cq_apolice) THEN ITERATE
        IF sit = 'A' THEN cor = #GREEN; ELSE cor = #RED
        prf_desc = 'Estipulante '
        IF prf = 'CO' THEN prf_desc = 'Corretor    '
        CALL FSSTEXT  LEFT(lgn,10)' 'prf_desc' 'sit'       'dtc ,row,10,,#PROT+cor
        row = row + 1; cnt = cnt + 1
      END

      IF cnt = 0 THEN
        CALL FSSTEXT  'Nenhum acesso encontrado para esta apolice.' ,9,16,,#PROT+#RED+#HI

      CALL FSSTEXT  COPIES('─',58)   ,row,10,,#PROT+#BLUE
      CALL FSSTEXT  cnt' acesso(s) encontrado(s)' ,row+1,10,,#PROT+#TURQ
      CALL FSSTEXT  COPIES('═',78)   ,22,1,78,#PROT+#BLUE
      CALL FSSTEXT  'PF3=Voltar'     ,24,35,,#PROT+#WHITE

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
