//LCVIDAS1 JOB (LIFECORE),'PROC VIDAS',CLASS=A,
//         MSGCLASS=X,NOTIFY=&SYSUID
//*----------------------------------------------------------*
//* LCVIDAS1.JCL - Processa fila de vidas importadas        *
//* Executa LCVIDAS01 para calcular capital VGC Escalonado  *
//* e confirmar STATUS='OK' em IMPORTACAO_VIDAS             *
//*----------------------------------------------------------*
//STEP010  EXEC PGM=LCVIDAS01,
//         PARM='LIFECORE'
//STEPLIB  DD   DSN=LIFECORE.LOADLIB,DISP=SHR
//SYSOUT   DD   SYSOUT=*
//SYSPRINT DD   SYSOUT=*
//DDRELAT  DD   DSN=LIFECORE.DATA.VIDAS.RELAT,
//         DISP=(NEW,CATLG,DELETE),
//         DCB=(RECFM=FA,LRECL=133,BLKSIZE=0),
//         SPACE=(CYL,(1,1))
//*----------------------------------------------------------*
//* RC 0  = OK total
//* RC 4  = OK com advertencias
//* RC 8  = Erro recuperavel
//* RC 16 = Falha critica (verificar SYSOUT)
//*----------------------------------------------------------*
