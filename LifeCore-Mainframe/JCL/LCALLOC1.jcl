//LCALLOC1 JOB (LIFECORE),'ALLOC DATASETS',CLASS=A,MSGCLASS=H,
//             NOTIFY=&SYSUID,MSGLEVEL=(1,1)
//*------------------------------------------------------------------*
//* LCALLOC1 - ALOCA TODOS OS DATASETS PDS DO PROJETO LIFECORE IQ   *
//* Executa uma vez para preparar o ambiente no z/OS (Hercules TK5R) *
//* HLQ: LIFECORE                                                    *
//*------------------------------------------------------------------*
//ALLOC    EXEC PGM=IEFBR14
//*
//* ── SRC.COBOL — fontes COBOL batch ──────────────────────────────*
//COBOL    DD  DSN=LIFECORE.SRC.COBOL,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(30,10,50)),
//             DCB=(RECFM=FB,LRECL=80,BLKSIZE=3120,DSORG=PO)
//*
//* ── SRC.CICS — programas CICS ────────────────────────────────── *
//CICS     DD  DSN=LIFECORE.SRC.CICS,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(20,10,30)),
//             DCB=(RECFM=FB,LRECL=80,BLKSIZE=3120,DSORG=PO)
//*
//* ── SRC.BMS — mapas de tela BMS ──────────────────────────────── *
//BMS      DD  DSN=LIFECORE.SRC.BMS,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(10,5,20)),
//             DCB=(RECFM=FB,LRECL=80,BLKSIZE=3120,DSORG=PO)
//*
//* ── COPYLIB — copybooks (layouts de registro) ─────────────────── *
//COPYLIB  DD  DSN=LIFECORE.COPYLIB,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(10,5,20)),
//             DCB=(RECFM=FB,LRECL=80,BLKSIZE=3120,DSORG=PO)
//*
//* ── JCL — Job Control Language ───────────────────────────────── *
//JCLLIB   DD  DSN=LIFECORE.JCL,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(10,5,20)),
//             DCB=(RECFM=FB,LRECL=80,BLKSIZE=3120,DSORG=PO)
//*
//* ── REXX — scripts REXX/TSO ───────────────────────────────────── *
//REXXLIB  DD  DSN=LIFECORE.REXX,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(10,5,20)),
//             DCB=(RECFM=FB,LRECL=80,BLKSIZE=3120,DSORG=PO)
//*
//* ── PROCLIB — procedures JCL ─────────────────────────────────── *
//PROCLIB  DD  DSN=LIFECORE.PROCLIB,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(5,2,10)),
//             DCB=(RECFM=FB,LRECL=80,BLKSIZE=3120,DSORG=PO)
//*
//* ── LOAD — executáveis compilados ────────────────────────────── *
//LOADLIB  DD  DSN=LIFECORE.LOAD,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(50,20,50)),
//             DCB=(RECFM=U,BLKSIZE=32760,DSORG=PO)
//*
//* ── DATA.INPUT — arquivo de entrada (GDG base) ───────────────── *
//DATAIN   DD  DSN=LIFECORE.DATA.INPUT,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(20,10,20)),
//             DCB=(RECFM=FB,LRECL=300,BLKSIZE=3000,DSORG=PO)
//*
//* ── DATA.OUTPUT — arquivo de saída ───────────────────────────── *
//DATAOUT  DD  DSN=LIFECORE.DATA.OUTPUT,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(20,10,20)),
//             DCB=(RECFM=FB,LRECL=300,BLKSIZE=3000,DSORG=PO)
//*
//* ── DATA.QUARANTINE — registros rejeitados ───────────────────── *
//QUARANT  DD  DSN=LIFECORE.DATA.QUARANTINE,
//             DISP=(NEW,CATLG,DELETE),
//             UNIT=SYSDA,
//             SPACE=(TRK,(10,5,20)),
//             DCB=(RECFM=FB,LRECL=300,BLKSIZE=3000,DSORG=PO)
//
