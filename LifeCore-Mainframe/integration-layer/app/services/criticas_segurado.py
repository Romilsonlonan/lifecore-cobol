"""
Motor de Críticas — Validação de Segurados na Importação

Catálogo de críticas:
┌───────┬──────────┬─────────────────────────────────────────────────────────────────┐
│ Cód.  │ Severid. │ Descrição                                                       │
├───────┼──────────┼─────────────────────────────────────────────────────────────────┤
│ E001  │ BLOQ     │ CPF com dígito verificador inválido (algoritmo Receita Federal)  │
│ E002  │ BLOQ     │ CPF em formato inválido (não tem 11 dígitos ou todos iguais)     │
│ E003  │ BLOQ     │ CPF constando como cancelado/suspenso na Receita Federal        │
│ E004  │ BLOQ     │ CPF constando como titular de CPF diferente (homônimo)         │
│ W039  │ ALRT     │ CPF não localizado na Receita Federal (situação desconhecida)   │
│ E010  │ BLOQ     │ Data de nascimento ausente — obrigatória para crítica de idade  │
│ E011  │ BLOQ     │ Data de nascimento inválida (formato ou data inexistente)       │
│ E012  │ BLOQ     │ Segurado abaixo da idade mínima (< 14 anos na data de inclusão) │
│ W025  │ MANU     │ Segurado acima da idade de implementação (> 70 anos) —          │
│       │          │   requer liberação manual; bloqueia novo segurado               │
│ E013  │ BLOQ     │ Segurado acima da idade máxima operacional (> 65 anos)          │
│       │          │   para apólices sem cláusula de permanência especial            │
│ W026  │ ALRT     │ Segurado próximo ao limite de idade (60–65 anos) — aviso        │
│ E020  │ BLOQ     │ CPF já cadastrado com cobertura ATIVA nesta apólice             │
│ W021  │ ALRT     │ CPF já existia com cobertura CANCELADA — possível reinclusão    │
│ E030  │ BLOQ     │ Nome do segurado vazio                                          │
│ W031  │ ALRT     │ Nome do segurado muito curto (< 5 chars) — possível truncamento │
│ E040  │ BLOQ     │ Data de inclusão ausente                                        │
│ E041  │ BLOQ     │ Data de inclusão inválida                                       │
│ W042  │ ALRT     │ Data de inclusão retroativa (> 30 dias no passado)              │
│ W043  │ ALRT     │ Data de inclusão futura (> 60 dias à frente)                   │
└───────┴──────────┴─────────────────────────────────────────────────────────────────┘

Severidades:
  BLOQ = Bloqueante — linha rejeitada, não gera endosso
  MANU = Manual    — gera endosso em PENDENTE_LIBERACAO, exige decisão do operador
  ALRT = Alerta    — gera endosso normalmente, mas registra aviso na resposta

API da Receita Federal:
  Usamos a API pública ReceitaWS (https://www.receitaws.com.br/v1/cpf/{cpf})
  que é gratuita e sem chave de API, com rate limit de ~3 req/min.
  Em produção, substituir por API paga (Serpro/Neoway) para volume maior.
  O serviço degrada graciosamente: se a API estiver offline retorna W039.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional


# ── Enums ─────────────────────────────────────────────────────────────────────

class SeveridadeCritica(str, Enum):
    BLOQ = "BLOQ"   # Bloqueante — rejeita a linha
    MANU = "MANU"   # Manual     — pende liberação do operador
    ALRT = "ALRT"   # Alerta     — processa mas notifica


class StatusLiberacao(str, Enum):
    PENDENTE  = "PENDENTE"
    LIBERADO  = "LIBERADO"
    BLOQUEADO = "BLOQUEADO"


# ── Catálogo de críticas ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class DefCritica:
    codigo:      str
    severidade:  SeveridadeCritica
    descricao:   str
    orientacao:  str    # instrução para o operador resolver


CATALOGO: dict[str, DefCritica] = {
    "E001": DefCritica("E001", SeveridadeCritica.BLOQ,
        "CPF com dígito verificador inválido.",
        "Corrija o CPF na planilha e reenvie."),
    "E002": DefCritica("E002", SeveridadeCritica.BLOQ,
        "CPF em formato inválido (não tem 11 dígitos ou todos os dígitos são iguais).",
        "Informe 11 dígitos numéricos sem pontuação."),
    "E003": DefCritica("E003", SeveridadeCritica.BLOQ,
        "CPF cancelado ou suspenso na Receita Federal.",
        "Verifique a situação cadastral do segurado na Receita Federal."),
    "E004": DefCritica("E004", SeveridadeCritica.BLOQ,
        "CPF associado a nome diferente do informado (possível homônimo).",
        "Confirme o CPF e o nome correto do segurado."),
    "W039": DefCritica("W039", SeveridadeCritica.ALRT,
        "CPF não localizado ou situação desconhecida na Receita Federal.",
        "Verifique a situação cadastral; o endosso foi gerado com ressalva."),
    "E010": DefCritica("E010", SeveridadeCritica.BLOQ,
        "Data de nascimento ausente — obrigatória para crítica de idade.",
        "Informe a data de nascimento na coluna dt_nascimento."),
    "E011": DefCritica("E011", SeveridadeCritica.BLOQ,
        "Data de nascimento inválida.",
        "Use o formato DD/MM/AAAA."),
    "E012": DefCritica("E012", SeveridadeCritica.BLOQ,
        "Segurado abaixo da idade mínima permitida (14 anos na data de inclusão).",
        "Menores de 14 anos não podem ser incluídos neste produto."),
    "W025": DefCritica("W025", SeveridadeCritica.MANU,
        "Segurado acima da idade de implementação (70 anos). "
        "Novo segurado: inclusão bloqueada até liberação manual. "
        "Segurado já existente: permanência permitida com autorização.",
        "Acesse o endpoint de liberação manual e decida: LIBERAR ou BLOQUEAR."),
    "E013": DefCritica("E013", SeveridadeCritica.BLOQ,
        "Segurado acima da idade máxima operacional (65 anos) sem cláusula de permanência.",
        "Verifique se a apólice possui cláusula de permanência especial."),
    "W026": DefCritica("W026", SeveridadeCritica.ALRT,
        "Segurado na faixa de atenção de idade (60–65 anos). "
        "A cobertura será mantida até o limite contratual.",
        "Verifique a cláusula de vigência da apólice para este segurado."),
    "E020": DefCritica("E020", SeveridadeCritica.BLOQ,
        "CPF já possui cobertura ATIVA nesta apólice.",
        "Use tp_movimentacao=CAP para alterar capital ou EXC para excluir."),
    "W021": DefCritica("W021", SeveridadeCritica.ALRT,
        "CPF já existia com cobertura CANCELADA — possível reinclusão.",
        "O endosso foi processado. Verifique se é reinclusão intencional."),
    "E030": DefCritica("E030", SeveridadeCritica.BLOQ,
        "Nome do segurado vazio.",
        "Informe o nome completo na coluna nome_segurado."),
    "W031": DefCritica("W031", SeveridadeCritica.ALRT,
        "Nome do segurado muito curto (menos de 5 caracteres).",
        "Verifique se o nome não foi truncado na planilha."),
    "E040": DefCritica("E040", SeveridadeCritica.BLOQ,
        "Data de inclusão ausente.",
        "Informe a data de início de cobertura na coluna dt_inclusao."),
    "E041": DefCritica("E041", SeveridadeCritica.BLOQ,
        "Data de inclusão inválida.",
        "Use o formato DD/MM/AAAA."),
    "W042": DefCritica("W042", SeveridadeCritica.ALRT,
        "Data de inclusão retroativa (mais de 30 dias no passado).",
        "Confirme se a inclusão retroativa é intencional."),
    "W043": DefCritica("W043", SeveridadeCritica.ALRT,
        "Data de inclusão futura (mais de 60 dias à frente).",
        "Confirme se a inclusão futura está correta."),
}


# ── Resultado de crítica ──────────────────────────────────────────────────────

@dataclass
class CriticaResultado:
    codigo:          str
    severidade:      SeveridadeCritica
    descricao:       str
    orientacao:      str
    valor_informado: Optional[str] = None  # dado que gerou a crítica
    fl_liberavel:    bool = False           # True = operador pode liberar
    fl_liberado:     bool = False
    id_liberacao:    Optional[str] = None
    dt_liberacao:    Optional[str] = None
    id_usuario_lib:  Optional[str] = None

    @property
    def bloqueante(self) -> bool:
        return self.severidade == SeveridadeCritica.BLOQ

    @property
    def manual(self) -> bool:
        return self.severidade == SeveridadeCritica.MANU

    def to_dict(self) -> dict:
        return {
            "codigo":          self.codigo,
            "severidade":      self.severidade.value,
            "descricao":       self.descricao,
            "orientacao":      self.orientacao,
            "valor_informado": self.valor_informado,
            "fl_liberavel":    self.fl_liberavel,
            "fl_liberado":     self.fl_liberado,
            "id_liberacao":    self.id_liberacao,
        }


def _critica(codigo: str, valor: Optional[str] = None) -> CriticaResultado:
    defn = CATALOGO[codigo]
    return CriticaResultado(
        codigo=codigo,
        severidade=defn.severidade,
        descricao=defn.descricao,
        orientacao=defn.orientacao,
        valor_informado=valor,
        fl_liberavel=(defn.severidade == SeveridadeCritica.MANU),
    )


# ── Validador de CPF (algoritmo Receita Federal) ──────────────────────────────

def _validar_cpf_algoritmo(cpf: str) -> bool:
    """Valida os dois dígitos verificadores conforme algoritmo da Receita Federal."""
    if len(cpf) != 11 or not cpf.isdigit() or len(set(cpf)) == 1:
        return False
    # Primeiro dígito
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10 % 11) % 10
    if d1 != int(cpf[9]):
        return False
    # Segundo dígito
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10 % 11) % 10
    return d2 == int(cpf[10])


# ── Consulta ReceitaWS (gratuita, sem API key) ────────────────────────────────

_RECEITAWS_CACHE: dict[str, dict] = {}   # cache simples em memória


def _consultar_receita_federal(cpf: str, nm_segurado: str = "") -> list[CriticaResultado]:
    """
    Consulta a ReceitaWS (https://www.receitaws.com.br/v1/cpf/{cpf}).
    Rate limit: ~3 req/min no plano gratuito. Degrada graciosamente.

    Campos verificados:
      - situação (Regular / Cancelado / Suspenso / Pendente Regularização)
      - nome (se informado, compara com o nome da planilha)

    Em produção usar: Serpro CPF API ou Neoway (pagas, sem rate limit).
    """
    criticas: list[CriticaResultado] = []

    # Cache de sessão (evita reprocessar o mesmo CPF na mesma importação)
    if cpf in _RECEITAWS_CACHE:
        dados = _RECEITAWS_CACHE[cpf]
    else:
        try:
            import urllib.request
            import json as _json
            url = f"https://www.receitaws.com.br/v1/cpf/{cpf}"
            req = urllib.request.Request(url, headers={"User-Agent": "LifeCore-IQ/2.1"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                dados = _json.loads(resp.read().decode())
            _RECEITAWS_CACHE[cpf] = dados
        except Exception:
            # API offline ou timeout → W039 (alerta, não bloqueia)
            criticas.append(_critica("W039", cpf))
            return criticas

    situacao = (dados.get("situacao") or dados.get("status") or "").upper()

    if situacao in ("CANCELADO", "CANCELADA"):
        criticas.append(_critica("E003", situacao))
    elif situacao in ("SUSPENSO", "PENDENTE DE REGULARIZACAO", "PENDENTE"):
        criticas.append(_critica("E003", situacao))
    elif situacao not in ("REGULAR", "REGULARIZADO"):
        criticas.append(_critica("W039", situacao or "sem retorno"))

    # Verificação de nome (se a API retornar nome e tiver nome na planilha)
    if nm_segurado:
        nome_api = (dados.get("nome") or "").upper().strip()
        nome_inf = nm_segurado.upper().strip()
        if nome_api and nome_inf and _similaridade_nome(nome_api, nome_inf) < 0.5:
            criticas.append(_critica("E004",
                f"Informado: '{nm_segurado}' | Receita: '{dados.get('nome', '?')}'"))

    return criticas


def _similaridade_nome(a: str, b: str) -> float:
    """Jaccard simples sobre conjuntos de palavras — suficiente para detecção grosseira."""
    sa = set(a.split())
    sb = set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ── Validador de idade ────────────────────────────────────────────────────────

# Parâmetros do produto (em produção: vêm da tabela de config da apólice)
IDADE_MINIMA          = 14    # anos completos na data de inclusão
IDADE_MAXIMA_OPERAT   = 65    # acima disto: E013 (sem cláusula de permanência)
IDADE_IMPLEMENTACAO   = 70    # acima disto: W025 (requer liberação manual)
IDADE_ATENCAO_INICIO  = 60    # início da faixa de atenção (W026)


def _calcular_idade(dt_nasc_str: str, dt_ref_str: str) -> int:
    """Retorna idade em anos completos de dt_nasc_str até dt_ref_str (ambos AAAAMMDD)."""
    try:
        nasc = date(int(dt_nasc_str[:4]), int(dt_nasc_str[4:6]), int(dt_nasc_str[6:8]))
        ref  = date(int(dt_ref_str[:4]),  int(dt_ref_str[4:6]),  int(dt_ref_str[6:8]))
        idade = ref.year - nasc.year - (
            (ref.month, ref.day) < (nasc.month, nasc.day)
        )
        return max(0, idade)
    except (ValueError, TypeError):
        return -1


def _validar_idade(
    dt_nascimento: Optional[str],
    dt_inclusao: str,
    tp_movimentacao: str,
    coberturas_existentes: dict,   # _COBERTURAS store
    nr_apolice: str,
    cpf: str,
) -> list[CriticaResultado]:
    """Valida faixas de idade e gera críticas conforme parâmetros do produto."""
    criticas: list[CriticaResultado] = []

    if not dt_nascimento:
        # Para inclusões, dt_nascimento é obrigatória para crítica de idade
        if tp_movimentacao == "INC":
            criticas.append(_critica("E010"))
        return criticas

    idade = _calcular_idade(dt_nascimento, dt_inclusao)
    if idade < 0:
        criticas.append(_critica("E011", dt_nascimento))
        return criticas

    valor_str = f"{dt_nascimento} → {idade} anos em {dt_inclusao}"

    if idade < IDADE_MINIMA:
        criticas.append(_critica("E012", valor_str))

    elif idade > IDADE_IMPLEMENTACAO:
        # Acima de 70 anos: W025 (MANU)
        chave = f"{nr_apolice}:{cpf}"
        ja_existe = chave in coberturas_existentes
        c = _critica("W025", valor_str)
        # Novo segurado: bloqueia até liberação. Já existente: só alerta.
        if not ja_existe and tp_movimentacao == "INC":
            # Mantém como MANU (será bloqueado sem liberação)
            pass
        else:
            # Segurado existente: downgrade para ALRT
            c = CriticaResultado(
                codigo="W025",
                severidade=SeveridadeCritica.ALRT,
                descricao=CATALOGO["W025"].descricao,
                orientacao="Segurado já existente — permanência autorizada mediante análise.",
                valor_informado=valor_str,
                fl_liberavel=False,
            )
        criticas.append(c)

    elif idade > IDADE_MAXIMA_OPERAT:
        # Entre 65 e 70: E013 (BLOQ) — sem cláusula de permanência
        criticas.append(_critica("E013", valor_str))

    elif idade >= IDADE_ATENCAO_INICIO:
        # Entre 60 e 65: W026 (ALRT)
        criticas.append(_critica("W026", valor_str))

    return criticas


# ── Validador de data de inclusão ─────────────────────────────────────────────

def _validar_dt_inclusao(dt_inclusao: str) -> list[CriticaResultado]:
    criticas: list[CriticaResultado] = []
    if not dt_inclusao:
        criticas.append(_critica("E040"))
        return criticas
    try:
        d = date(int(dt_inclusao[:4]), int(dt_inclusao[4:6]), int(dt_inclusao[6:8]))
        hoje = date.today()
        delta = (d - hoje).days
        if delta < -30:
            criticas.append(_critica("W042", f"{dt_inclusao} ({abs(delta)} dias atrás)"))
        elif delta > 60:
            criticas.append(_critica("W043", f"{dt_inclusao} ({delta} dias à frente)"))
    except (ValueError, TypeError):
        criticas.append(_critica("E041", dt_inclusao))
    return criticas


# ── Validador de nome ─────────────────────────────────────────────────────────

def _validar_nome(nome: str) -> list[CriticaResultado]:
    criticas: list[CriticaResultado] = []
    if not nome or not nome.strip():
        criticas.append(_critica("E030"))
    elif len(nome.strip()) < 5:
        criticas.append(_critica("W031", nome))
    return criticas


# ── Validador de duplicidade na apólice ──────────────────────────────────────

def _validar_duplicidade(
    nr_apolice: str,
    cpf: str,
    tp_movimentacao: str,
    coberturas: dict,
) -> list[CriticaResultado]:
    from app.schemas.lifecore import StatusCoberturaEnum
    criticas: list[CriticaResultado] = []
    chave = f"{nr_apolice}:{cpf}"
    if tp_movimentacao != "INC":
        return criticas
    if chave in coberturas:
        cob = coberturas[chave]
        if cob.get("cd_status_cobertura") == StatusCoberturaEnum.ATIVA:
            criticas.append(_critica("E020", cpf))
        elif cob.get("cd_status_cobertura") == StatusCoberturaEnum.CANCELADA:
            criticas.append(_critica("W021", cpf))
    return criticas


# ── Motor principal ───────────────────────────────────────────────────────────

@dataclass
class ResultadoCriticas:
    cpf:               str
    nome:              str
    criticas:          list[CriticaResultado] = field(default_factory=list)
    fl_bloqueado:      bool = False
    fl_pendente_manu:  bool = False

    @property
    def tem_bloqueante(self) -> bool:
        return any(c.bloqueante and not c.fl_liberado for c in self.criticas)

    @property
    def tem_manual_pendente(self) -> bool:
        return any(c.manual and not c.fl_liberado for c in self.criticas)

    @property
    def alertas(self) -> list[CriticaResultado]:
        return [c for c in self.criticas if c.severidade == SeveridadeCritica.ALRT]

    def to_dict(self) -> dict:
        return {
            "cpf":              self.cpf,
            "nome":             self.nome,
            "criticas":         [c.to_dict() for c in self.criticas],
            "fl_bloqueado":     self.tem_bloqueante,
            "fl_pendente_manu": self.tem_manual_pendente,
            "nr_criticas":      len(self.criticas),
            "nr_bloqueantes":   sum(1 for c in self.criticas if c.bloqueante),
            "nr_manuais":       sum(1 for c in self.criticas if c.manual),
            "nr_alertas":       len(self.alertas),
        }


def executar_criticas(
    cpf: str,
    nome: str,
    dt_nascimento: Optional[str],
    dt_inclusao: str,
    tp_movimentacao: str,
    nr_apolice: str,
    coberturas: dict,
    verificar_receita: bool = True,
) -> ResultadoCriticas:
    """
    Executa todas as críticas configuradas para um segurado.

    Ordem de execução:
      1. CPF — formato e dígito verificador (local, sem I/O)
      2. Nome — presença e tamanho
      3. Data de inclusão — validade e janela temporal
      4. Idade — faixas mínima/máxima/implementação
      5. Duplicidade na apólice
      6. Receita Federal — situação cadastral (I/O, opcional)
    """
    resultado = ResultadoCriticas(cpf=cpf, nome=nome)
    criticas: list[CriticaResultado] = []

    # ── 1. CPF formato ────────────────────────────────────────────────────────
    cpf_limpo = re.sub(r"\D", "", cpf or "")
    if len(cpf_limpo) != 11 or len(set(cpf_limpo)) == 1:
        criticas.append(_critica("E002", cpf))
    elif not _validar_cpf_algoritmo(cpf_limpo):
        criticas.append(_critica("E001", cpf))

    # ── 2. Nome ───────────────────────────────────────────────────────────────
    criticas.extend(_validar_nome(nome))

    # ── 3. Data de inclusão ───────────────────────────────────────────────────
    criticas.extend(_validar_dt_inclusao(dt_inclusao))

    # ── 4. Idade ──────────────────────────────────────────────────────────────
    if not any(c.codigo in ("E040", "E041") for c in criticas):
        criticas.extend(_validar_idade(
            dt_nascimento, dt_inclusao, tp_movimentacao, coberturas, nr_apolice, cpf_limpo
        ))

    # ── 5. Duplicidade ────────────────────────────────────────────────────────
    if not any(c.codigo == "E002" for c in criticas):
        criticas.extend(_validar_duplicidade(nr_apolice, cpf_limpo, tp_movimentacao, coberturas))

    # ── 6. Receita Federal (somente se CPF é estruturalmente válido) ──────────
    if verificar_receita and not any(c.codigo in ("E001", "E002") for c in criticas):
        criticas.extend(_consultar_receita_federal(cpf_limpo, nome))

    resultado.criticas = criticas
    resultado.fl_bloqueado = resultado.tem_bloqueante
    resultado.fl_pendente_manu = resultado.tem_manual_pendente
    return resultado
