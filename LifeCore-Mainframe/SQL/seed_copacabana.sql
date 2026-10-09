-- ================================================================
-- FILE   : seed_copacabana.sql
-- DESCRICAO: Seed do estipulante Copacabana Hotel IT com 2
--            substipulantes, produto VGC Escalonado e apólice mestre.
--            Dados vinculados ao formato da planilha informada.
-- ================================================================

-- ----------------------------------------------------------------
-- 1. ESTIPULANTE PRINCIPAL — Copacabana Hotel IT
-- ----------------------------------------------------------------
INSERT INTO EMPRESA
  (NR_CODIGO, NM_RAZAO_SOCIAL, NM_NOME_REDUZIDO, CD_CNPJ,
   TP_EMPRESA, NR_SUSEP, VL_CAPITAL_VINCULADO, VL_CAPITAL_SUBSCRITO,
   VL_ACEITE_COBRANCA, CD_STATUS, DT_INCLUSAO, ID_USUARIO_INCL)
VALUES
  ('000010', 'COPACABANA HOTEL IT LTDA', 'COPA HOTEL IT',
   '12345678000195', 'ES', NULL,
   5000000.00, 5000000.00, 100.00,
   'AT', '20260101', 'LCADMIN ');

-- ----------------------------------------------------------------
-- 2. SUBSTIPULANTE 1 — Funcionários Operacionais
--    Sub=1 na planilha (Módulo 1 / VGC)
-- ----------------------------------------------------------------
INSERT INTO EMPRESA
  (NR_CODIGO, NM_RAZAO_SOCIAL, NM_NOME_REDUZIDO, CD_CNPJ,
   TP_EMPRESA, CD_STATUS, DT_INCLUSAO, ID_USUARIO_INCL)
VALUES
  ('000011', 'COPA HOTEL IT - OPERACIONAL LTDA', 'COPA OPERAC',
   '12345678000277', 'ES', 'AT', '20260101', 'LCADMIN ');

-- ----------------------------------------------------------------
-- 3. SUBSTIPULANTE 2 — Diretores e Alta Gerência
--    Sub=2 na planilha (Módulo 1 / VGC)
-- ----------------------------------------------------------------
INSERT INTO EMPRESA
  (NR_CODIGO, NM_RAZAO_SOCIAL, NM_NOME_REDUZIDO, CD_CNPJ,
   TP_EMPRESA, CD_STATUS, DT_INCLUSAO, ID_USUARIO_INCL)
VALUES
  ('000012', 'COPA HOTEL IT - DIRETORIA LTDA', 'COPA DIRET',
   '12345678000358', 'ES', 'AT', '20260101', 'LCADMIN ');

-- ----------------------------------------------------------------
-- 4. PARÂMETROS DE MATRÍCULA (sequencial para cada substipulante)
-- ----------------------------------------------------------------
-- Nota: CD_EMPRESA deve ser o ID gerado acima. Em produção substituir
-- pelos valores reais de IDENTITY retornados.
-- Para fins de seed com ID fixo, assumir CD_EMPRESA 10, 11, 12.

INSERT INTO MATRICULA_SEQ (CD_EMPRESA, NR_SEQ_INICIAL, NR_SEQ_FINAL, NR_SEQ_ATUAL)
  VALUES (10, 1, 999999, 1);
INSERT INTO MATRICULA_SEQ (CD_EMPRESA, NR_SEQ_INICIAL, NR_SEQ_FINAL, NR_SEQ_ATUAL)
  VALUES (11, 1, 499999, 1);
INSERT INTO MATRICULA_SEQ (CD_EMPRESA, NR_SEQ_INICIAL, NR_SEQ_FINAL, NR_SEQ_ATUAL)
  VALUES (12, 500000, 999999, 500000);

-- ----------------------------------------------------------------
-- 5. PARÂMETROS DE ROTINA para o estipulante principal
-- ----------------------------------------------------------------
INSERT INTO PARAMETRO_ROTINA
  (CD_EMPRESA, FL_APENAS_DIAS_UTEIS, NR_DIAS_ACEITACAO_AUTO,
   DS_MOTIVO_ACEIT_AUTO, NR_DIAS_RECUSA_LEGAL, NR_DIAS_RECUSA_AUTO)
VALUES
  (10, 'S', 15, 'Aceitação automática VGC Escalonado', 15, 13);

-- ----------------------------------------------------------------
-- 6. APÓLICE MESTRE VGC — Capital Escalonado (TP_CAPITAL = 'E')
--    Sub 1 (Operacional):
--      Funcionario(a): faixa 1 → capital = 3 × salário
--    Sub 2 (Diretoria):
--      Diretor(a):     faixa 2 → capital = 6 × salário
-- Nota: A apólice vincula o produto ao estipulante principal.
-- Os substipulantes são identificados pelo campo SUB da planilha.
-- ----------------------------------------------------------------
INSERT INTO APOLICE
  (NR_APOLICE, CD_EMPRESA, CD_CPF_SEGURADO,
   CD_PRODUTO, TP_CAPITAL,
   VL_CAPITAL_SEGURADO, VL_SALARIO_BASE, NR_FATOR_MULT,
   VL_PREMIO_LIQUIDO, VL_PREMIO_BRUTO, VL_IOF,
   TP_FORMA_PAGAMENTO, TP_PERIODICIDADE,
   DT_VIGENCIA_INI, DT_VIGENCIA_FIM, DT_EMISSAO,
   CD_STATUS, ID_USUARIO_EMISSAO)
VALUES
  ('2026.APL.COPA001', 10, '00000000000',
   'VGC', 'E',
   0.00, 0.00, 1.00,
   0.00, 0.00, 0.00,
   'BO', 'ME',
   '20260101', '20261231', '20260101',
   'AT', 'LCADMIN ');

-- Nota: CD_CPF_SEGURADO '00000000000' é o CPF reservado para a
-- apólice mestre do estipulante (sem segurado individual).
-- A COBERTURA real é gerada a cada importação de planilha.

-- ----------------------------------------------------------------
-- 7. COBERTURA padrão da apólice mestre (template)
-- ----------------------------------------------------------------
INSERT INTO COBERTURA
  (CD_COBERTURA, NR_APOLICE, CD_TIPO, NM_COBERTURA,
   VL_CAPITAL, NR_CARENCIA_DIAS, CD_STATUS)
VALUES
  ('COB2026COPA0001', '2026.APL.COPA001', 'MORT',
   'Morte por qualquer causa — VGC Escalonado',
   0.00, 0, 'AT');

INSERT INTO COBERTURA
  (CD_COBERTURA, NR_APOLICE, CD_TIPO, NM_COBERTURA,
   VL_CAPITAL, NR_CARENCIA_DIAS, CD_STATUS)
VALUES
  ('COB2026COPA0002', '2026.APL.COPA001', 'INVA',
   'Invalidez Permanente Total por Acidente — VGC',
   0.00, 90, 'AT');

-- ----------------------------------------------------------------
-- 8. TABELA DE FAIXAS DE CAPITAL ESCALONADO
--    (Usada pelo COBOL VGCCAP01 e pelo serviço Python ao gravar)
-- ----------------------------------------------------------------
-- Para produto VGC Escalonado, o capital é calculado pelo COBOL:
--   Cargo Funcionario(a) → fator_mult 3.0 × vl_salario
--   Cargo Diretor(a)     → fator_mult 6.0 × vl_salario
-- Estes valores são parametrizados na planilha ou nos defaults de cargo.

-- ================================================================
-- REFERÊNCIA RÁPIDA
-- ================================================================
-- Apólice mestre : 2026.APL.COPA001
-- Estipulante    : CD_EMPRESA = 10 (Copacabana Hotel IT)
-- Substipulante 1: CD_EMPRESA = 11 (Operacional) — Sub=1 planilha
-- Substipulante 2: CD_EMPRESA = 12 (Diretoria)   — Sub=2 planilha
-- Produto        : VGC / TP_CAPITAL = 'E' (Escalonado)
-- Vigência       : 01/01/2026 a 31/12/2026
-- ================================================================
