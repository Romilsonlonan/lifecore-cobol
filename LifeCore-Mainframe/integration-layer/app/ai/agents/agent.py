"""
LifeCore AI Layer — Agente COBOL
Loop ReAct: Raciocínio → Ação (Tool Call) → Observação → Resposta final.

O agente usa Tool Calling nativo da API OpenAI-compatible.
Funciona com Ollama (llama3.2, mistral, qwen2.5) sem API paga.

Fluxo:
  Usuário: "Por que o job FATURA01 abendou com S0C7 hoje?"
    1. Agente chama analisar_abend(S0C7, FATURA01)
    2. Agente chama buscar_documentacao("FATURA01 campo COMP-3 capital")
    3. Agente sintetiza: "O campo VL-CAPITAL em CPYFATU não foi inicializado..."
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Generator
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")
MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", "8"))


# ── Tipos ─────────────────────────────────────────────────────────────────────


@dataclass
class AgentStep:
    """Um passo do loop ReAct."""

    turn: int
    thought: str | None  # raciocínio do modelo (se visível)
    tool_name: str | None  # tool chamada
    tool_args: dict | None  # argumentos da tool
    tool_result: dict | None  # resultado da execução
    final: bool = False  # True = resposta final ao usuário


@dataclass
class AgentResponse:
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    tool_calls: int = 0
    error: str | None = None


# ── Agente ────────────────────────────────────────────────────────────────────


class COBOLAgent:
    """
    Agente especializado em diagnóstico COBOL e operações do LifeCore.

    Parâmetros:
      tools_schema : lista de dicts no formato OpenAI tools
      tool_executor: função execute_tool(name, args, rag_engine) → dict
      rag_engine   : instância do RAGEngine (opcional)
    """

    SYSTEM = """Você é o Agente COBOL do LifeCore-Mainframe, assistente técnico
especializado em diagnóstico de falhas, análise de abends, operações batch
e seguros de vida em grupo (VGC/GLB) para o mercado brasileiro.

Regras:
1. NUNCA execute jobs que modificam dados sem confirmar com o usuário.
2. NUNCA gere SQL de escrita (INSERT/UPDATE/DELETE).
3. Ao diagnosticar um abend, sempre chame analisar_abend e buscar_documentacao.
4. Seja direto e técnico. Cite nomes reais de programas, copybooks e campos.
5. Responda em português (BR).
6. Quando incerto, diga "preciso de mais informações" e use buscar_documentacao.

Você tem acesso às seguintes ferramentas: consultar_banco, disparar_job_cobol,
ler_resultado_job, buscar_documentacao, analisar_abend, listar_apolices."""

    def __init__(
        self,
        tools_schema: list[dict],
        tool_executor,
        rag_engine=None,
        model: str = LLM_MODEL,
        max_turns: int = MAX_TURNS,
    ):
        self._tools_schema = tools_schema
        self._tool_executor = tool_executor
        self._rag = rag_engine
        self._model = model
        self._max_turns = max_turns
        self._client = self._build_client()

    def _build_client(self):
        try:
            from openai import OpenAI

            return OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
        except ImportError:
            logger.warning("openai não instalado — agente em modo stub.")
            return None

    def run(
        self, user_message: str, conversation_history: list[dict] | None = None
    ) -> AgentResponse:
        """
        Executa o loop ReAct e retorna a resposta final.
        conversation_history permite manter contexto entre chamadas.
        """
        if self._client is None:
            return AgentResponse(
                answer="Cliente LLM não disponível. Configure LLM_BASE_URL.",
                error="no_llm_client",
            )

        messages = [{"role": "system", "content": self.SYSTEM}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        steps: list[AgentStep] = []
        total_tool_calls = 0

        for turn in range(self._max_turns):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=self._tools_schema,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=2048,
                )
            except Exception as e:
                logger.error("Erro na chamada LLM (turn %d): %s", turn, e)
                return AgentResponse(
                    answer=f"Erro ao chamar o LLM: {e}",
                    steps=steps,
                    tool_calls=total_tool_calls,
                    error=str(e),
                )

            msg = response.choices[0].message

            # ── Resposta final (sem tool calls) ──────────────────────────────
            if not msg.tool_calls:
                answer = msg.content or "Sem resposta do modelo."
                steps.append(
                    AgentStep(
                        turn=turn,
                        thought=None,
                        tool_name=None,
                        tool_args=None,
                        tool_result=None,
                        final=True,
                    )
                )
                return AgentResponse(
                    answer=answer, steps=steps, tool_calls=total_tool_calls
                )

            # ── Processa tool calls ───────────────────────────────────────────
            messages.append(msg)  # adiciona a mensagem do assistente com tool_calls

            for tc in msg.tool_calls:
                total_tool_calls += 1
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                logger.info("Tool call: %s(%s)", tc.function.name, str(args)[:100])

                result = self._tool_executor(tc.function.name, args, self._rag)

                step = AgentStep(
                    turn=turn,
                    thought=None,
                    tool_name=tc.function.name,
                    tool_args=args,
                    tool_result=result,
                )
                steps.append(step)

                # Retorna resultado da tool para o modelo
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )

        # Limite de turnos atingido
        return AgentResponse(
            answer="Limite de turnos do agente atingido. Tente reformular a pergunta.",
            steps=steps,
            tool_calls=total_tool_calls,
            error="max_turns_exceeded",
        )

    def stream(self, user_message: str) -> Generator[str, None, None]:
        """
        Versão streaming do agente — gera tokens à medida que chegam.
        Útil para UIs com resposta progressiva.
        """
        if self._client is None:
            yield "Cliente LLM não disponível."
            return

        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user", "content": user_message},
        ]

        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=self._tools_schema,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=2048,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as e:
            yield f"\n[Erro: {e}]"


# ── Factory ───────────────────────────────────────────────────────────────────


def build_agent(rag_engine=None) -> COBOLAgent:
    from app.ai.agents.tools import TOOLS_SCHEMA, execute_tool

    return COBOLAgent(
        tools_schema=TOOLS_SCHEMA,
        tool_executor=execute_tool,
        rag_engine=rag_engine,
    )
