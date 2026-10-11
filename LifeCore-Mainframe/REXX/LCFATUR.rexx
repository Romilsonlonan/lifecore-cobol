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
  CALL FSSTEXT  COPIES('═',78)         ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Selecione a operacao:' ,5,28,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',50)         ,6,14,,#PROT+#BLUE

  CALL FSSTEXT  ' 1  -  GERAR        Gerar fatura mensal por estipulante'  ,8,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 2  -  CONSULTAR    Consultar faturas por competencia'    ,9,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 3  -  IPCA         Consultar taxa IPCA vigente'         ,10,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 4  -  DIVERGENCIAS Listar divergencias de faturamento'  ,11,12,,#PROT+#GREEN
  CALL FSSTEXT  ' 5  -  FECHAR       Fechamento mensal de faturamento'    ,12,12,,#PROT+#GREEN

  CALL FSSTEXT  COPIES('─',50)  ,13,14,,#PROT+#BLUE

  /* info IPCA vigente - simulacao */
  CALL FSSTEXT  'IPCA vigente (OUT/2026): 0,44%' ,15,22,,#PROT+#TURQ+#HI

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
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Parametros para geracao de fatura:' ,5,22,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',55)                       ,6,12,,#PROT+#BLUE

  CALL FSSTEXT   'Nr Estipulante  : '  ,8,14,,#PROT+#WHITE
  CALL FSSFIELD  'fat_estip'           ,8,32,10,#GREEN+#USCORE+#NUM

  CALL FSSTEXT   'Competencia     : '  ,10,14,,#PROT+#WHITE
  CALL FSSFIELD  'fat_compet'          ,10,32,6,#GREEN+#USCORE+#NUM ,fat_compet
  CALL FSSTEXT  '(formato: AAAAMM  ex: 202610)'  ,11,32,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('─',55)  ,12,12,,#PROT+#BLUE

  CALL FSSTEXT  'ATENCAO: Apolice deve estar com status AT (Ativa)' ,13,14,,#PROT+#RED+#HI

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
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
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Nr  Estipulante   Competencia  Valor        Vencimento  Situacao' ,5,2,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',76)  ,6,2,,#PROT+#BLUE

  CALL FSSTEXT  ' 1  LIFECORE SEG  202609       R$ 45.890,00  2026/10/10  PAGO'   ,7,2,,#PROT+#GREEN
  CALL FSSTEXT  ' 2  GRUPO ALPHA   202609       R$ 23.450,00  2026/10/10  ABERTO' ,8,2,,#PROT+#YELLOW
  CALL FSSTEXT  ' 3  BETA SERVICOS 202609       R$  8.120,00  2026/10/10  VENCID' ,9,2,,#PROT+#RED

  CALL FSSTEXT  COPIES('─',76)  ,10,2,,#PROT+#BLUE
  CALL FSSTEXT  '3 faturas encontradas - Competencia: 09/2026' ,11,2,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
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
  CALL FSSTEXT  COPIES('═',78)  ,3,1,78,#PROT+#BLUE

  CALL FSSTEXT  'Mes/Ano    Indice  Acumulado 12m' ,5,22,,#PROT+#YELLOW+#HI
  CALL FSSTEXT  COPIES('─',36)  ,6,22,,#PROT+#BLUE

  CALL FSSTEXT  'OUT/2026    0,44%    4,83%'  ,7,22,,#PROT+#GREEN
  CALL FSSTEXT  'SET/2026    0,44%    4,42%'  ,8,22,,#PROT+#WHITE
  CALL FSSTEXT  'AGO/2026    0,44%    4,50%'  ,9,22,,#PROT+#WHITE
  CALL FSSTEXT  'JUL/2026    0,38%    4,40%'  ,10,22,,#PROT+#WHITE
  CALL FSSTEXT  'JUN/2026    0,36%    4,06%'  ,11,22,,#PROT+#WHITE

  CALL FSSTEXT  COPIES('─',36)  ,12,22,,#PROT+#BLUE
  CALL FSSTEXT  'Fonte: SUSEP / IBGE'  ,13,22,,#PROT+#TURQ

  CALL FSSTEXT  COPIES('═',78)  ,22,1,78,#PROT+#BLUE
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
