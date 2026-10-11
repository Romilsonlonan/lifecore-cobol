//LCCANCEL JOB (LIFECORE),'CANCEL PORTAL',CLASS=A,MSGCLASS=X,
//         NOTIFY=&SYSUID,MSGLEVEL=(1,1)
//*
//*================================================================*
//* JOB  : LCCANCEL                                                *
//* SIST : LIFECORE IQ — Ciclo de Cancelamento                    *
//* DESC : Lê PORTAL_EMPRESAS_UPD.dat e propaga cancelamentos/     *
//*        suspensões para DB2 EMPRESA e VSAM LIFECORE.VSAM.APOLICE*
//*                                                                *
//* ETAPAS:                                                        *
//*   STEP010 — Pré-check: arquivo de entrada existe?              *
//*   STEP020 — Executa LCCANCEL (DB2 + VSAM)                     *
//*   STEP030 — Arquiva o arquivo processado com GDG               *
//*                                                                *
//* RETURN CODES ESPERADOS:                                        *
//*   RC=0  Sucesso total                                          *
//*   RC=4  Processado com avisos                                  *
//*   RC=8  Erro em DB2 (registros afetados com falha)             *
//*   RC=12 Erro de I/O no arquivo de entrada                      *
//*================================================================*
//*
//JOBLIB  DD DSN=LIFECORE.LOAD,DISP=SHR
//*
//*--- STEP010: Verificar existência do arquivo de entrada ----------
//STEP010 EXEC PGM=IDCAMS
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
  LISTCAT ENT(LIFECORE.DATA.PORTAL.EMPRESAS.UPD) -
          ALL
/*
//SYSPRINT DD SYSOUT=*
// IF STEP010.RC > 4 THEN
//  GOTO STEP030    /* arquivo não existe — pula processamento */
// ENDIF
//*
//*--- STEP020: Executar LCCANCEL ----------------------------------
//STEP020 EXEC PGM=LCCANCEL,REGION=0M,
//             PARM='',
//             DYNAMNBR=20
//STEPLIB  DD DSN=LIFECORE.LOAD,DISP=SHR
//         DD DSN=DSN.V13R1.SDSNEXIT,DISP=SHR
//         DD DSN=DSN.V13R1.SDSNLOAD,DISP=SHR
//UPDFILE  DD DSN=LIFECORE.DATA.PORTAL.EMPRESAS.UPD,
//            DISP=SHR
//VSAMIN   DD DSN=LIFECORE.VSAM.APOLICE,
//            DISP=SHR
//SYSPRINT DD SYSOUT=*
//SYSOUT   DD SYSOUT=*
//SYSDBOUT DD SYSOUT=*
//SYSUDUMP DD SYSOUT=*
//*
//* DB2 subsystem bind — ajustar SSID conforme ambiente
//DSNREXX  DD DSN=DSN.V13R1.SDSNLOAD,DISP=SHR
//*
// IF STEP020.RC > 8 THEN
//ABEND020 EXEC PGM=IEFBR14
// ENDIF
//*
//*--- STEP030: Arquivar UPD (GDG +1) após processamento ----------
//STEP030 EXEC PGM=IEBGENER,
//             COND=(8,LT,STEP020)
//SYSPRINT DD SYSOUT=*
//SYSUT1   DD DSN=LIFECORE.DATA.PORTAL.EMPRESAS.UPD,
//            DISP=SHR
//SYSUT2   DD DSN=LIFECORE.DATA.PORTAL.EMPRESAS.UPD.HIST(+1),
//            DISP=(NEW,CATLG,DELETE),
//            SPACE=(CYL,(1,1)),
//            DCB=(RECFM=FB,LRECL=128,BLKSIZE=12800)
//SYSIN    DD DUMMY
//*
//*--- STEP040: Limpar arquivo de entrada após arquivamento --------
//STEP040 EXEC PGM=IEFBR14,
//             COND=(8,LT,STEP020)
//DELFILE  DD DSN=LIFECORE.DATA.PORTAL.EMPRESAS.UPD,
//            DISP=(MOD,DELETE,KEEP),
//            SPACE=(CYL,0)
//*
