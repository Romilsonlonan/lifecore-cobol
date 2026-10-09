      *----------------------------------------------------------------*
      * CPYCOMM - LIFECORE IQ - DFHCOMMAREA PADRAO                    *
      * Compartilhada por todos os programas CICS do LifeCore IQ      *
      * Uso: COPY CPYCOMM in WORKING-STORAGE SECTION                  *
      *----------------------------------------------------------------*
       01  DFHCOMMAREA.
           05  CA-USUARIO          PIC X(10).
           05  CA-PERFIL           PIC X(01).
               88 CA-ADMIN         VALUE 'A'.
               88 CA-ESTIPULANTE   VALUE 'E'.
           05  CA-APOLICE          PIC X(10).
           05  CA-TENTATIVAS       PIC 9(01).
           05  CA-RETURN-CODE      PIC X(02).
               88 CA-RC-OK         VALUE '00'.
               88 CA-RC-BLOQ       VALUE '08'.
               88 CA-RC-ERR        VALUE '12'.
           05  CA-PAGINA           PIC 9(03).
           05  CA-FILLER           PIC X(30).
