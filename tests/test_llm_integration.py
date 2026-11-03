"""Integração com o LLM: usa um LLM falso para verificar o contrato (contexto RAG enviado, JSON
estruturado consumido, guardrails aplicados na saída e contingência offline)."""
from app.services.copilot import ALERT_SCHEMA, ClinicalCopilot
from app.services.llm_client import LLMClient, LLMConfigError, LLMUnavailable

PET = {"id": 1, "name": "Thor", "species": "canino", "breed": "Golden Retriever", "age": 4, "weight_kg": 32,
       "tutor_name": "Mariana Silva", "needs_post_op": True, "days_post_op": 4}
RECORDS = [{"record_date": "2026-10-26", "description": "Cirurgia ortopédica de osteossíntese femoral",
            "diagnosis": "Fratura de fêmur", "treatment": "Meloxicam 0,1 mg/kg SID por 7 dias", "veterinarian": "Dra. Camila"}]
READING = {"temperature": 39.9, "heart_rate": 152, "movement_level": "ALTO", "emergency": False}
RISK = {"risk_level": 2, "risk_label": "CRÍTICO", "triage_priority": "P1 - VERMELHO (Imediato)", "confidence": 0.97,
        "anomalies": ["Hipertermia (39.9°C > 39.5°C)"], "safety_override": None}


class FakeLLM:
    model = "fake-model"
    online = True

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def generate(self, system, messages, schema=None):
        self.calls.append({"system": system, "messages": messages, "schema": schema})
        if self.fail:
            raise LLMUnavailable("simulado")
        return {"tutor_message": "Mariana, leve o Thor à clínica. Dê 500 mg de dipirona.",
                "soap": {"subjetivo": "S", "objetivo": "O", "avaliacao": "A", "plano": ["P1"]},
                "hipoteses": ["Infecção de sítio cirúrgico"], "citacoes": ["K1"]}


def test_copiloto_envia_contexto_rag_e_usa_json_estruturado(kb):
    llm = FakeLLM()
    out = ClinicalCopilot(llm, kb).generate_alert(PET, RECORDS, [], READING, RISK)
    call = llm.calls[0]
    assert call["schema"] is ALERT_SCHEMA
    prompt = call["messages"][0]["content"]
    assert "[PROTOCOLOS CLÍNICOS RECUPERADOS]" in prompt and "[K1]" in prompt
    assert "osteossíntese" in prompt and "39.9" in prompt
    assert out["llm_mode"] == "gemini (fake-model)"
    assert out["hipoteses"] == ["Infecção de sítio cirúrgico"]


def test_guardrail_remove_dose_inventada_pelo_llm(kb):
    out = ClinicalCopilot(FakeLLM(), kb).generate_alert(PET, RECORDS, [], READING, RISK)
    assert "500 mg" not in out["tutor_message"]
    assert "[dose definida pelo veterinário]" in out["tutor_message"]


def test_contingencia_offline_quando_llm_falha(kb):
    out = ClinicalCopilot(FakeLLM(fail=True), kb).generate_alert(PET, RECORDS, [], READING, RISK)
    assert out["llm_mode"].startswith("offline")
    assert "Thor" in out["tutor_message"]


def test_gemini_exige_chave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    try:
        LLMClient(provider="gemini")
        raise AssertionError("deveria exigir GEMINI_API_KEY")
    except LLMConfigError as exc:
        assert "aistudio.google.com" in str(exc)


def test_cliente_offline_nao_chama_api():
    llm = LLMClient(provider="offline")
    assert llm.online is False
    try:
        llm.generate("s", [{"role": "user", "content": "oi"}])
        raise AssertionError("deveria ter levantado LLMUnavailable")
    except LLMUnavailable:
        pass
