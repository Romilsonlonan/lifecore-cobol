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
  CALL FSSTEXT  COPIES('═',78)         ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Selecione a operacao desejada:' ,5,24,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',50)                   ,6,14,,#PROT+#BLUE

  CALL FSSTEXT  ' 1  -  CONSULTAR    Consulta de estipulante por CNPJ/Nome' ,8,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 2  -  INCLUIR      Incluir novo estipulante'               ,9,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 3  -  ALTERAR      Alterar dados cadastrais'               ,10,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 4  -  SUBSTIPUL    Gestao de subestipulantes'              ,11,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 5  -  PLANOS       Vincular planos VGC/GLB'                ,12,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 6  -  LISTAR       Listar todos os estipulantes'           ,13,12,,#PROT+#GREEN

  CALL FSSTEXT  COPIES('─',50)  ,14,14,,#PROT+#BLUE

  CALL FSSTEXT   'Opcao ===>'   ,16,12,,#PROT+#WHITE+#HI
  CALL FSSFIELD  'opcao'        ,16,23,2,#YELLOW+#HI+#USCORE

  CALL FSSTEXT  COPIES('═',78) ,22,1,78,#PROT+#BLUE
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
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Informe o criterio de consulta:' ,5,24,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',50)                    ,6,14,,#PROT+#BLUE

  CALL FSSTEXT   'CNPJ         : '  ,9,14,,#PROT+#WHITE
  CALL FSSFIELD  'cnpj_est'         ,9,29,18,#GREEN+#USCORE

  CALL FSSTEXT   'Nome Empresa : '  ,11,14,,#PROT+#WHITE
  CALL FSSFIELD  'nome_est'         ,11,29,40,#GREEN+#USCORE

  CALL FSSTEXT  '(Informe CNPJ ou parte do nome para pesquisar)' ,13,16,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Pesquisar   PF3=Voltar   PF12=Cancelar'  ,24,16,,#PROT+#WHITE

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
  est_cnpj  = ''
  est_nome  = ''
  est_reduz = ''
  est_uf    = ''
  est_cid   = ''
  est_cont  = ''
  est_email = ''
  est_tel   = ''
  est_plano = ''
  est_segur = ''

  CALL FSSTERM
  CALL FSSINIT
  CALL FSSTITLE  'LIFECORE IQ  -  INCLUSAO DE ESTIPULANTE'
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Cadastro do estipulante e vinculos:' ,5,20,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',60)                        ,6,10,,#PROT+#BLUE

  CALL FSSTEXT   'Codigo (6 digitos) : ' ,7,3,,#PROT+#WHITE
  CALL FSSFIELD  'est_codigo'            ,7,25,6,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'CNPJ (14 digitos)  : ' ,8,3,,#PROT+#WHITE
  CALL FSSFIELD  'est_cnpj'              ,8,25,14,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'Razao Social       : ' ,9,3,,#PROT+#WHITE
  CALL FSSFIELD  'est_nome'              ,9,25,54,#GREEN+#USCORE

  CALL FSSTEXT   'Nome reduzido      : ' ,10,3,,#PROT+#WHITE
  CALL FSSFIELD  'est_reduz'             ,10,25,30,#GREEN+#USCORE

  CALL FSSTEXT   'UF                 : ' ,11,3,,#PROT+#WHITE
  CALL FSSFIELD  'est_uf'                ,11,25,2,#GREEN+#USCORE
  CALL FSSTEXT   'Cidade: '              ,11,32,,#PROT+#WHITE
  CALL FSSFIELD  'est_cid'               ,11,40,25,#GREEN+#USCORE

  CALL FSSTEXT   'Contato principal  : ' ,12,3,,#PROT+#WHITE
  CALL FSSFIELD  'est_cont'              ,12,25,30,#GREEN+#USCORE

  CALL FSSTEXT   'E-mail             : ' ,13,3,,#PROT+#WHITE
  CALL FSSFIELD  'est_email'             ,13,25,45,#GREEN+#USCORE

  CALL FSSTEXT   'Telefone           : ' ,14,3,,#PROT+#WHITE
  CALL FSSFIELD  'est_tel'               ,14,25,20,#GREEN+#USCORE

  CALL FSSTEXT   'Produto (VGC/GLB)  : ' ,15,3,,#PROT+#WHITE
  CALL FSSFIELD  'est_plano'             ,15,25,3,#GREEN+#USCORE

  CALL FSSTEXT   'Codigo seguradora  : ' ,16,3,,#PROT+#WHITE
  CALL FSSFIELD  'est_segur'             ,16,25,6,#GREEN+#USCORE+#NUM

  CALL FSSTEXT  'ES=Estipulante; 1 seguradora por cadastro.' ,18,3,,#PROT+#TURQ
  CALL FSSTEXT  'Corretores: vinculo em rotina propria.' ,19,3,,#PROT+#TURQ
  CALL FSSTEXT  'Prototipo sem gravacao no MVS/API.' ,20,3,,#PROT+#YELLOW+#HI

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'ENTER=Validar PF3=Cancelar PF12=Voltar' ,24,18,,#PROT+#WHITE

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
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Nr  CNPJ              Razao Social                    UF  Sit' ,5,2,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',76)  ,6,2,,#PROT+#BLUE

  /* dados de exemplo */
  CALL FSSTEXT  ' 1  11222333000181    LIFECORE SEGUROS DE VIDA S.A.   SP  AT' ,7,2,,#PROT+#GREEN
  CALL FSSTEXT  ' 2  44555666000195    GRUPO ALPHA SAUDE COLETIVA       RJ  AT' ,8,2,,#PROT+#GREEN
  CALL FSSTEXT  ' 3  77888999000112    BETA SERVICOS EMPRESARIAIS       MG  AT' ,9,2,,#PROT+#GREEN
  CALL FSSTEXT  ' 4  22111333000174    CONSTRUTORA OMEGA LTDA           RS  SU' ,10,2,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('─',76)         ,11,2,,#PROT+#BLUE
  CALL FSSTEXT  '4 estipulantes encontrados'  ,12,2,,#PROT+#TURQ
  CALL FSSTEXT  'Sit: AT=Ativo  SU=Suspenso  CA=Cancelado' ,13,2,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
  CALL FSSTEXT  'PF3=Voltar   PF7=Anterior   PF8=Proximo' ,24,19,,#PROT+#WHITE

  CALL FSSDISPLAY
  DO FOREVER
    key = FSSKEY(CHAR)
    IF key = 'PF03' | key = 'ENTER' THEN LEAVE
  END
  CALL FSSTERM
RETURN
