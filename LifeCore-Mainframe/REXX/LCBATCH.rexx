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
  CALL FSSTEXT  COPIES('═',78)         ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Selecione o job para submeter:' ,5,24,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',55)                   ,6,12,,#PROT+#BLUE

  CALL FSSTEXT  ' 1  -  LCDIA01    Ciclo diario completo (13 steps)'    ,8,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 2  -  LCIMP01    Importacao de arquivo de empresa'    ,9,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 3  -  FATURA01   Geracao de fatura batch'            ,10,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 4  -  ARQVAL01   Validacao de arquivo'               ,11,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 5  -  CONCIL01   Conciliacao faturado x pago'        ,12,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 6  -  COMIS01    Calculo de comissoes'               ,13,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 7  -  VGCCAP01   Calculo de capital segurado'        ,14,12,,#PROT+#GREEN

  CALL FSSTEXT  COPIES('─',55)  ,15,12,,#PROT+#BLUE
  CALL FSSTEXT  ' 9  -  SDSF       Ver output dos jobs submetidos'     ,16,12,,#PROT+#TURQ

  CALL FSSTEXT   'Opcao ===>'  ,18,12,,#PROT+#WHITE+#HI
  CALL FSSFIELD  'opcao'       ,18,23,2,#YELLOW+#HI+#USCORE

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
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Job a submeter : 'jcl_nome          ,6,18,,#PROT+#WHITE
  CALL FSSTEXT  'Dataset        : LIFECORE.JCL('jcl_nome')' ,7,18,,#PROT+#TURQ

  CALL FSSTEXT  'Deseja submeter o job? (S/N)'  ,10,24,,#PROT+#YELLOW+#HI
  confirm = 'N'
  CALL FSSFIELD  'confirm'  ,10,53,1,#GREEN+#USCORE,'N'

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
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
