"""Assistente conversacional do tutor ("Pergunte à CLYVO").

Cada resposta é personalizada com o contexto do pet: perfil, fase da recuperação, prescrição do
prontuário, últimas leituras da coleira e protocolos recuperados por RAG. Antes do LLM, guardrails
tratam emergências (escalonamento P1 automático) e perguntas sobre medicamentos humanos.
"""
from .copilot import _pet_text, _records_text, compute_trend
from .guardrails import detect_human_medication, detect_red_flags, medication_safe_reply, normalize, sanitize_output
from .knowledge_base import KnowledgeBase
from .llm_client import LLMClient, LLMUnavailable

CHAT_SYSTEM = """Você é a assistente virtual da CLYVO VET conversando por chat com o tutor de um pet que está \
sendo monitorado por uma coleira inteligente. Responda em português do Brasil, com carinho e objetividade, em \
até 5 frases curtas, como numa conversa de WhatsApp. Chame o pet pelo nome e personalize a resposta com a fase \
da recuperação, a prescrição e as leituras recentes informadas no contexto.

Regras de segurança: use apenas as informações do contexto e dos protocolos [Kn]; nunca informe doses que não \
estejam na prescrição do prontuário; nunca recomende medicamentos de uso humano; se o relato sugerir \
emergência, oriente ir imediatamente à clínica. Quando não souber, diga que vai encaminhar a dúvida à equipe \
veterinária."""

INTENTS = [
    ("status", ["como ele esta", "como ela esta", "como esta", "esta agora", "como ta", "esta bem", "ta bem", "sinais", "temperatura", "febre", "batimento", "coracao", "coleira", "status"]),
    ("ferida", ["ferida", "pontos", "curativo", "incisao", "corte", "lamb", "colar", "roupa cirurgica"]),
    ("alimentacao", ["comer", "comida", "racao", "agua", "apetite", "fome", "beber"]),
    ("atividade", ["passear", "passeio", "andar", "pular", "correr", "brincar", "escada", "sofa", "cama"]),
    ("medicacao", ["remedio", "medicamento", "medicacao", "horario", "dose", "meloxicam", "dipirona", "pimobendan", "receita"]),
]


class TutorChatAgent:
    def __init__(self, llm: LLMClient, kb: KnowledgeBase):
        self.llm = llm
        self.kb = kb

    def reply(self, pet: dict, records: list, readings: list, latest: dict | None, history: list, message: str) -> dict:
        red_flags = detect_red_flags(message)
        if red_flags:
            text = (f"⚠️ {pet['tutor_name'].split()[0]}, o que você descreveu ({', '.join(red_flags)}) pode ser uma emergência. "
                    f"Leve o(a) {pet['name']} agora para a CLYVO VET mais próxima. Já abri um alerta de prioridade máxima e a "
                    f"equipe de plantão recebeu o prontuário. Mantenha-o calmo e evite que ele se movimente no caminho.")
            return {"answer": text, "escalate": True, "red_flags": red_flags, "intent": "emergencia",
                    "retrieved": self.kb.search(message + " emergência", k=2), "llm_mode": "guardrail (sem LLM)"}

        meds = detect_human_medication(message)
        if meds:
            return {"answer": sanitize_output(medication_safe_reply(pet["name"], meds, pet["species"]), ""), "escalate": False,
                    "red_flags": [], "intent": "medicamento_humano", "retrieved": self.kb.search("medicamentos humanos tóxicos " + " ".join(meds), k=2),
                    "llm_mode": "guardrail (sem LLM)"}

        kb_results = self.kb.search(f"{message} {records[0]['description'] if records else ''} {pet['species']}", k=3)
        trend = compute_trend(readings)
        latest_txt = (f"{latest['temperature']}°C, {latest['heart_rate']} BPM, atividade {latest['movement_level']}, "
                      f"classificação {latest['risk_label']}" if latest else "sem leituras")
        context = (f"[PACIENTE]\n{_pet_text(pet)}\n\n[PRONTUÁRIO]\n{_records_text(records)}\n\n"
                   f"[COLEIRA]\nÚltima leitura: {latest_txt}. Tendência: {trend['text']}.\n\n"
                   f"[PROTOCOLOS]\n{KnowledgeBase.format_context(kb_results)}")
        messages = [{"role": m["role"], "content": m["content"]} for m in history[-10:] if m["role"] in ("user", "assistant")]
        messages.append({"role": "user", "content": f"{context}\n\n[PERGUNTA DO TUTOR]\n{message}"})
        try:
            answer = self.llm.generate(CHAT_SYSTEM, messages)
            mode = f"gemini ({self.llm.model})"
            intent = "llm"
        except LLMUnavailable:
            intent = self.classify_intent(message)
            answer = self._offline_answer(intent, pet, records, latest, trend, kb_results)
            mode = "offline (gerador determinístico)"

        prescriptions = " ".join(r["treatment"] or "" for r in records)
        return {"answer": sanitize_output(answer, prescriptions), "escalate": False, "red_flags": [], "intent": intent,
                "retrieved": kb_results, "llm_mode": mode}

    @staticmethod
    def classify_intent(message: str) -> str:
        norm = normalize(message)
        for intent, keywords in INTENTS:
            if any(k in norm for k in keywords):
                return intent
        return "geral"

    @staticmethod
    def _offline_answer(intent, pet, records, latest, trend, kb_results) -> str:
        name = pet["name"]
        record = records[0] if records else None
        tip = ""
        if kb_results:
            first_sentences = ". ".join(kb_results[0]["text"].split(". ")[:2]).rstrip(".")
            tip = f" Pelo protocolo da clínica [{kb_results[0]['ref']}]: {first_sentences}."

        if intent == "status" and latest:
            mood = {"ESTÁVEL": "está estável 💚", "ATENÇÃO": "pede atenção ⚠️", "CRÍTICO": "está em nível crítico 🚨"}[latest["risk_label"]]
            return (f"Agora o(a) {name} {mood}: {latest['temperature']}°C e {latest['heart_rate']} batimentos por minuto, "
                    f"em {latest['movement_level'].lower()}. Tendência: {trend['text']}."
                    + (f" Estamos no D{pet['days_post_op']} da recuperação." if pet["needs_post_op"] else ""))
        if intent == "medicacao" and record:
            return (f"A prescrição atual do(a) {name} é: {record['treatment']} (por {record['veterinarian']}). "
                    f"Siga exatamente a receita e, se esquecer um horário, não dobre a dose — fale com a clínica.")
        if intent == "atividade" and pet["needs_post_op"]:
            return (f"No D{pet['days_post_op']} após {record['description'].lower() if record else 'a cirurgia'}, o(a) {name} ainda precisa "
                    f"de repouso restrito: passeios curtos só na guia, sem pular ou subir escadas.{tip}")
        return f"Sobre o(a) {name}:{tip or ' vou encaminhar sua dúvida para a equipe veterinária.'}"
