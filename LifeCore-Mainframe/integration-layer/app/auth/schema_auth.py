"""
Auth Layer — SQL Schema
Tabelas: USUARIO, REFRESH_TOKEN, SESSAO_AUDITORIA
Adicionar ao schema_v2.sql ou aplicar separado.
"""

AUTH_SCHEMA_SQL = """
-- ================================================================
-- AUTH LAYER — LifeCore-Mainframe
-- ================================================================

-- Roles disponíveis
-- ADMIN        : gestão total (usuários, empresas, acesso)
-- OPERADOR     : emissão, sinistro, impressão (própria empresa)
-- CORRETOR     : consulta apólices/sinistros vinculados a ele
-- ESTIPULANTE  : consulta faturas/apólices da própria empresa
-- LEITURA      : somente GET em todos os módulos

CREATE TABLE IF NOT EXISTS USUARIO (
    cd_usuario          SERIAL          PRIMARY KEY,
    cd_empresa          INTEGER         REFERENCES EMPRESA(cd_empresa),
    nm_nome             VARCHAR(80)     NOT NULL,
    cd_email            VARCHAR(120)    NOT NULL UNIQUE,
    ds_senha_hash       VARCHAR(255)    NOT NULL,
    cd_role             VARCHAR(20)     NOT NULL DEFAULT 'LEITURA'
                            CHECK (cd_role IN ('ADMIN','OPERADOR','CORRETOR','ESTIPULANTE','LEITURA')),
    fl_ativo            CHAR(1)         NOT NULL DEFAULT 'S'
                            CHECK (fl_ativo IN ('S','N')),
    nr_cpf              CHAR(11),
    nr_susep            VARCHAR(10),       -- para corretores
    dt_inclusao         CHAR(8)         NOT NULL,
    dt_ultimo_login     CHAR(8),
    hr_ultimo_login     CHAR(6),
    nr_tentativas_falha SMALLINT        NOT NULL DEFAULT 0,
    fl_bloqueado        CHAR(1)         NOT NULL DEFAULT 'N',
    dt_expiracao_senha  CHAR(8),          -- força troca periódica
    id_usuario_incl     VARCHAR(20),
    ts_inclusao         TIMESTAMP       NOT NULL DEFAULT NOW(),
    ts_atualizacao      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usuario_email    ON USUARIO(cd_email);
CREATE INDEX IF NOT EXISTS idx_usuario_empresa  ON USUARIO(cd_empresa);
CREATE INDEX IF NOT EXISTS idx_usuario_role     ON USUARIO(cd_role);

-- Refresh tokens (revogação explícita)
CREATE TABLE IF NOT EXISTS REFRESH_TOKEN (
    cd_token            SERIAL          PRIMARY KEY,
    cd_usuario          INTEGER         NOT NULL REFERENCES USUARIO(cd_usuario),
    ds_token_hash       VARCHAR(255)    NOT NULL UNIQUE,
    dt_expiracao        TIMESTAMP       NOT NULL,
    fl_revogado         CHAR(1)         NOT NULL DEFAULT 'N',
    ip_origem           VARCHAR(45),
    ds_user_agent       VARCHAR(200),
    ts_criacao          TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refresh_usuario ON REFRESH_TOKEN(cd_usuario);
CREATE INDEX IF NOT EXISTS idx_refresh_hash    ON REFRESH_TOKEN(ds_token_hash);

-- Auditoria de sessões (login, logout, tentativas falhas)
CREATE TABLE IF NOT EXISTS SESSAO_AUDITORIA (
    cd_sessao           SERIAL          PRIMARY KEY,
    cd_usuario          INTEGER         REFERENCES USUARIO(cd_usuario),
    cd_email_tentativa  VARCHAR(120),   -- captura emails de tentativas inválidas
    tp_evento           VARCHAR(20)     NOT NULL
                            CHECK (tp_evento IN ('LOGIN_OK','LOGIN_FAIL','LOGOUT',
                                                 'TOKEN_REFRESH','SENHA_RESET',
                                                 'USUARIO_CRIADO','USUARIO_ATIVADO',
                                                 'USUARIO_DESATIVADO','ACESSO_NEGADO')),
    ip_origem           VARCHAR(45),
    ds_detalhe          VARCHAR(300),
    ts_evento           TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessao_usuario ON SESSAO_AUDITORIA(cd_usuario);
CREATE INDEX IF NOT EXISTS idx_sessao_evento  ON SESSAO_AUDITORIA(tp_evento);

-- Seed: usuário admin padrão
-- Senha: lifecore@2026  (hash bcrypt — trocar imediatamente em produção)
INSERT INTO USUARIO (
    cd_empresa, nm_nome, cd_email, ds_senha_hash, cd_role,
    fl_ativo, dt_inclusao, id_usuario_incl
) VALUES (
    1,
    'Administrador LifeCore',
    'admin@lifecore.com.br',
    '$2b$12$placeholder_change_on_first_login',
    'ADMIN',
    'S',
    TO_CHAR(NOW(), 'YYYYMMDD'),
    'SYSTEM'
) ON CONFLICT (cd_email) DO NOTHING;
"""
