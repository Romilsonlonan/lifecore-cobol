//LCSETUP1 JOB (LIFECORE),'GDG SETUP',CLASS=A,MSGCLASS=X,
//         NOTIFY=&SYSUID,MSGLEVEL=(1,1)
//*
//* ================================================================
//* JOB    : LCSETUP1
//* DESCRICAO: Criacao inicial dos GDGs do LifeCore-Mainframe
//*            Execute uma unica vez por ambiente.
//* PROJETO: LifeCore-Mainframe
//* ================================================================
//*
//STEP010  EXEC PGM=IDCAMS
//SYSPRINT DD  SYSOUT=*
//SYSIN    DD  *
  /* ---- GDG BASE: Arquivo de Apolices ---- */
  DEFINE GDG (NAME(LIFECORE.DATA.GDG.APOLICE)   -
              LIMIT(31)                           -
              NOEMPTY                             -
              SCRATCH)
  /* ---- GDG BASE: Arquivo de Fatura ---- */
  DEFINE GDG (NAME(LIFECORE.DATA.GDG.FATURA)     -
              LIMIT(31)                           -
              NOEMPTY                             -
              SCRATCH)
  /* ---- GDG BASE: Arquivo de Pagamento ---- */
  DEFINE GDG (NAME(LIFECORE.DATA.GDG.PAGAMENTO)  -
              LIMIT(31)                           -
              NOEMPTY                             -
              SCRATCH)
  /* ---- GDG BASE: Arquivo de Conciliacao ---- */
  DEFINE GDG (NAME(LIFECORE.DATA.GDG.CONCILIACAO)-
              LIMIT(31)                           -
              NOEMPTY                             -
              SCRATCH)
  /* ---- GDG BASE: Arquivo de Clearing ---- */
  DEFINE GDG (NAME(LIFECORE.DATA.GDG.CLEARING)   -
              LIMIT(31)                           -
              NOEMPTY                             -
              SCRATCH)
  /* ---- GDG BASE: Arquivo de Quarentena ---- */
  DEFINE GDG (NAME(LIFECORE.DATA.GDG.QUARENTENA) -
              LIMIT(31)                           -
              NOEMPTY                             -
              SCRATCH)
  IF LASTCC = 0 THEN DO
    SET MAXCC = 0
  END
/*
//*
//STEP020  EXEC PGM=IDCAMS,COND=(4,LT,STEP010)
//* Cria VSAM KSDS para cache de status de apólice
//SYSPRINT DD  SYSOUT=*
//SYSIN    DD  *
  DEFINE CLUSTER (                                -
      NAME(LIFECORE.VSAM.APOLICE.STATUS)          -
      RECORDS(10000 2000)                         -
      KEYS(12 0)                                  -
      RECORDSIZE(300 300)                         -
      INDEXED)                                    -
    DATA (NAME(LIFECORE.VSAM.APOLICE.STATUS.DATA))-
    INDEX(NAME(LIFECORE.VSAM.APOLICE.STATUS.IDX))
/*
