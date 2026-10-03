      *================================================================*
      * COPYBOOK : CPYSQLCA                                           *
      * DESCRICAO: SQL Communication Area (SQLCA) padrao DB2          *
      * PROJETO  : LifeCore-Mainframe                                 *
      * VERSAO   : 1.0.0                                              *
      *================================================================*
       01  SQLCA.
           05  SQLCAID                   PIC X(08).
           05  SQLCABC                   PIC S9(09) COMP.
           05  SQLCODE                   PIC S9(09) COMP.
           05  SQLERRM                   PIC X(70).
           05  SQLERRP                   PIC X(08).
           05  SQLERRD  OCCURS 6 TIMES   PIC S9(09) COMP.
           05  SQLWARN  OCCURS 11 TIMES  PIC X(01).
           05  SQLSTATE                  PIC X(05).
