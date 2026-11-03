"""Cliente do LLM: Google Gemini via API do Google AI Studio (SDK oficial `google-genai`).

- Modo "gemini" (padrão): exige a chave GEMINI_API_KEY, gratuita em https://aistudio.google.com/apikey.
  Quando um schema é informado, o Gemini devolve JSON validado (response_json_schema).
- Modo "offline": não chama nenhuma API; o copiloto usa geradores determinísticos baseados nos mesmos
  dados recuperados (RAG). Precisa ser escolhido explicitamente (CLYVO_LLM_PROVIDER=offline) e é usado
  nos testes automatizados.

Se uma chamada ao Gemini falhar durante a operação (cota gratuita esgotada, rede, erro da API), a
chamada levanta LLMUnavailable e o copiloto usa o gerador offline só naquele alerta, para que o tutor
nunca fique sem aviso.
"""
import json
import logging
import os

log = logging.getLogger("clyvo.llm")


class LLMUnavailable(Exception):
    """A chamada ao LLM não pôde ser concluída; o chamador deve usar o modo offline."""


class LLMConfigError(RuntimeError):
    """O Gemini foi exigido, mas a chave ou o SDK não estão disponíveis."""


class LLMClient:
    def __init__(self, provider: str = "gemini", model: str = "gemini-flash-latest"):
        self.model = model
        self.client = None
        if provider == "offline":
            self.mode = "offline"
            return
        if provider != "gemini":
            raise LLMConfigError(f"CLYVO_LLM_PROVIDER inválido: {provider!r} (use 'gemini' ou 'offline')")

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise LLMConfigError(
                "GEMINI_API_KEY não configurada. Gere uma chave gratuita em https://aistudio.google.com/apikey "
                "e coloque no arquivo .env (veja .env.example). Para rodar sem IA online, use CLYVO_LLM_PROVIDER=offline.")
        try:
            from google import genai
            from google.genai import errors, types
        except ImportError as exc:
            raise LLMConfigError("SDK do Gemini não instalado: rode `pip install -r requirements.txt`") from exc

        self.types = types
        self.errors = errors
        self.client = genai.Client(api_key=api_key)
        self.mode = "gemini"

    @property
    def online(self) -> bool:
        return self.mode == "gemini"

    def generate(self, system: str, messages: list, schema: dict | None = None) -> dict | str:
        """Gera uma resposta. Com `schema`, devolve o JSON já validado como dict; sem, devolve texto.

        `messages` usa o formato [{"role": "user" | "assistant", "content": str}, ...].
        """
        if not self.online:
            raise LLMUnavailable("modo offline")

        types = self.types
        contents = [types.Content(role="model" if m["role"] == "assistant" else "user",
                                  parts=[types.Part(text=m["content"])]) for m in messages]
        config = types.GenerateContentConfig(system_instruction=system, temperature=0.3)
        if schema:
            config.response_mime_type = "application/json"
            config.response_json_schema = schema
        try:
            response = self.client.models.generate_content(model=self.model, contents=contents, config=config)
        except self.errors.ClientError as exc:
            if exc.code == 429:
                log.warning("Cota gratuita do Gemini atingida (429); usando o gerador offline neste alerta")
                raise LLMUnavailable("rate limit") from exc
            log.error("Requisição recusada pelo Gemini (%s): %s", exc.code, exc)
            raise LLMUnavailable(f"client error {exc.code}") from exc
        except self.errors.ServerError as exc:
            log.error("Erro no servidor do Gemini (%s): %s", exc.code, exc)
            raise LLMUnavailable(f"server error {exc.code}") from exc
        except Exception as exc:  # falhas de rede/timeout do cliente HTTP
            log.error("Falha de conexão com o Gemini: %s", exc)
            raise LLMUnavailable("connection") from exc

        text = (response.text or "").strip()
        if not text:
            # Resposta vazia normalmente indica bloqueio pelos filtros de segurança
            reason = response.candidates[0].finish_reason if response.candidates else "sem candidatos"
            raise LLMUnavailable(f"resposta vazia ({reason})")
        if schema:
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise LLMUnavailable("json inválido") from exc
        return text
