"""Copiloto Clínico com IA Generativa (LLM + RAG).

Funde quatro fontes de contexto -- perfil do pet, prontuário (SQL), tendência da telemetria e
protocolos clínicos recuperados (TF-IDF) -- e produz:
  * mensagem humanizada e personalizada para o tutor (WhatsApp / app);
  * rascunho de relatório SOAP + hipóteses para a equipe veterinária;
  * resumo diário personalizado de acompanhamento.

Com o Gemini, a geração usa saída estruturada (JSON Schema). Se ele falhar, um gerador
determinístico monta o mesmo formato a partir das anomalias e dos protocolos recuperados.
"""
from statistics import mean

from .guardrails import sanitize_output
from .knowledge_base import KnowledgeBase
from .llm_client import LLMClient, LLMUnavailable

ALERT_SYSTEM = """Você é o Copiloto Clínico da CLYVO VET, uma rede de clínicas veterinárias que monitora pets \
após a alta com uma coleira inteligente. A cada alerta você recebe o perfil do paciente, o prontuário, a \
telemetria recente, a avaliação do modelo preditivo de risco e trechos de protocolos clínicos identificados \
como [K1], [K2]...

Produza dois textos com objetivos diferentes:
1. tutor_message: mensagem de WhatsApp para o tutor, em português do Brasil, acolhedora e direta, chamando \
tutor e pet pelo nome. Explique o que foi detectado em linguagem leiga, diga o que fazer agora em passos \
numerados e o que NÃO fazer. Para nível CRÍTICO, oriente ir à clínica imediatamente e informe que a equipe já \
foi avisada; para ATENÇÃO, oriente observação e diga que a coleira seguirá monitorando. Até 900 caracteres.
2. soap: rascunho técnico para o médico-veterinário (Subjetivo, Objetivo, Avaliação e Plano), usando termos \
clínicos, a tendência das leituras e o procedimento recente. O plano é uma lista de condutas e exames.

Regras: baseie-se apenas no contexto fornecido; nunca informe doses de medicamentos que não estejam na \
prescrição do prontuário; nunca recomende medicamentos humanos. Em hipoteses, liste de 1 a 4 hipóteses em \
ordem de probabilidade. Em citacoes, liste os identificadores [Kn] dos protocolos que você usou."""

ALERT_SCHEMA = {
    "type": "object",
    "properties": {
        "tutor_message": {"type": "string"},
        "soap": {
            "type": "object",
            "properties": {
                "subjetivo": {"type": "string"},
                "objetivo": {"type": "string"},
                "avaliacao": {"type": "string"},
                "plano": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["subjetivo", "objetivo", "avaliacao", "plano"],
            "additionalProperties": False,
        },
        "hipoteses": {"type": "array", "items": {"type": "string"}},
        "citacoes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["tutor_message", "soap", "hipoteses", "citacoes"],
    "additionalProperties": False,
}

SUMMARY_SYSTEM = """Você é o assistente de acompanhamento da CLYVO VET. Com base nas estatísticas da coleira \
inteligente das últimas horas, no prontuário e nos protocolos [Kn], escreva para o tutor um resumo do dia do \
pet, em português do Brasil, carinhoso e objetivo, personalizado para a fase de recuperação (dias desde a \
cirurgia, espécie, idade). Não informe doses de medicamentos e não recomende medicamentos humanos."""

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "resumo": {"type": "string"},
        "destaques": {"type": "array", "items": {"type": "string"}},
        "recomendacoes_personalizadas": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["resumo", "destaques", "recomendacoes_personalizadas"],
    "additionalProperties": False,
}


def compute_trend(readings: list) -> dict:
    """Variação de temperatura e FC entre o início e o fim da janela recente (até 12 leituras)."""
    window = readings[-12:]
    if len(window) < 2:
        return {"temp_delta": 0.0, "hr_delta": 0, "window": len(window), "text": "sem histórico suficiente"}
    temp_delta = round(window[-1]["temperature"] - window[0]["temperature"], 1)
    hr_delta = int(window[-1]["heart_rate"] - window[0]["heart_rate"])
    parts = []
    if abs(temp_delta) >= 0.3:
        parts.append(f"temperatura {'subiu' if temp_delta > 0 else 'caiu'} {abs(temp_delta):.1f}°C")
    if abs(hr_delta) >= 15:
        parts.append(f"FC {'subiu' if hr_delta > 0 else 'caiu'} {abs(hr_delta)} BPM")
    text = (", ".join(parts) if parts else "parâmetros estáveis") + f" nas últimas {len(window)} leituras"
    return {"temp_delta": temp_delta, "hr_delta": hr_delta, "window": len(window), "text": text}


def _records_text(records: list) -> str:
    return "\n".join(f"- {r['record_date']}: {r['description']} | Diagnóstico: {r['diagnosis']} | "
                     f"Prescrição: {r['treatment']} | {r['veterinarian']}" for r in records) or "- sem registros"


def _pet_text(pet: dict) -> str:
    post_op = f"SIM (D{pet['days_post_op']} pós-cirurgia)" if pet["needs_post_op"] else "NÃO"
    return (f"Nome: {pet['name']} | Espécie: {pet['species']} | Raça: {pet['breed']} | Idade: {pet['age']:g} anos | "
            f"Peso: {pet['weight_kg']} kg | Tutor(a): {pet['tutor_name']} | Protocolo pós-operatório: {post_op}")


class ClinicalCopilot:
    def __init__(self, llm: LLMClient, kb: KnowledgeBase):
        self.llm = llm
        self.kb = kb

    # ------------------------------------------------------------------ RAG
    def retrieve(self, pet: dict, records: list, risk: dict, extra: str = "") -> list:
        procedure = records[0]["description"] if records else ""
        query = " ".join([*risk.get("anomalies", []), procedure, records[0]["diagnosis"] if records else "",
                          "pós-operatório" if pet["needs_post_op"] else "", pet["species"], extra])
        return self.kb.search(query, k=4)

    # --------------------------------------------------------------- alerts
    def generate_alert(self, pet: dict, records: list, readings: list, reading: dict, risk: dict,
                       tutor_report: str | None = None) -> dict:
        trend = compute_trend(readings)
        kb_results = self.retrieve(pet, records, risk, extra=tutor_report or "")
        context = (
            f"[PACIENTE]\n{_pet_text(pet)}\n\n[PRONTUÁRIO]\n{_records_text(records)}\n\n"
            f"[TELEMETRIA ATUAL]\nTemperatura: {reading['temperature']}°C | FC: {reading['heart_rate']} BPM | "
            f"Atividade: {reading['movement_level']} | SOS: {'ACIONADO' if reading.get('emergency') else 'não'}\n"
            f"Tendência: {trend['text']}\n\n"
            f"[MODELO PREDITIVO]\nNível: {risk['risk_label']} | Prioridade: {risk['triage_priority']} | "
            f"Confiança: {risk['confidence'] * 100:.0f}% | Anomalias: {'; '.join(risk['anomalies']) or 'nenhuma'}"
            f"{' | ' + risk['safety_override'] if risk.get('safety_override') else ''}\n\n"
            + (f"[RELATO DO TUTOR NO CHAT]\n{tutor_report}\n\n" if tutor_report else "")
            + f"[PROTOCOLOS CLÍNICOS RECUPERADOS]\n{KnowledgeBase.format_context(kb_results)}"
        )
        try:
            result = self.llm.generate(ALERT_SYSTEM, [{"role": "user", "content": context}], schema=ALERT_SCHEMA)
            mode = f"gemini ({self.llm.model})"
        except LLMUnavailable:
            result = self._offline_alert(pet, records, reading, risk, trend, kb_results, tutor_report)
            mode = "offline (gerador determinístico)"

        prescriptions = " ".join(r["treatment"] or "" for r in records)
        result["tutor_message"] = sanitize_output(result["tutor_message"], prescriptions)
        result.update({"llm_mode": mode, "trend": trend, "retrieved": kb_results, "context_preview": context})
        return result

    def _offline_alert(self, pet, records, reading, risk, trend, kb_results, tutor_report) -> dict:
        name, tutor = pet["name"], pet["tutor_name"].split()[0]
        level = risk["risk_level"]
        procedure = records[0]["description"] if records else "acompanhamento clínico"
        anomalies = " ".join(risk["anomalies"]).lower()
        is_ortho = "osteoss" in procedure.lower() or "ligamento" in procedure.lower()

        lay = []
        if "hipertermia" in anomalies or "febr" in anomalies:
            lay.append(f"temperatura elevada ({reading['temperature']}°C), sinal de febre")
        if "hipotermia" in anomalies:
            lay.append(f"temperatura baixa ({reading['temperature']}°C)")
        if "taquicardia" in anomalies:
            lay.append(f"coração acelerado ({reading['heart_rate']} batimentos por minuto)")
        if "bradicardia" in anomalies:
            lay.append(f"coração mais lento que o normal ({reading['heart_rate']} BPM)")
        if "atividade" in anomalies or "movimenta" in anomalies:
            lay.append("movimentação acima do permitido para o repouso da cirurgia")
        if "sos" in anomalies:
            lay.append("o botão SOS da coleira foi acionado")
        if tutor_report:
            lay.append(f"você relatou: \"{tutor_report.strip()[:120]}\"")

        steps = []
        if "hipotermia" in anomalies:
            steps.append(f"Aqueça {name} com mantas, sem bolsa de água quente ou secador direto na pele.")
        elif "hipertermia" in anomalies or "febr" in anomalies:
            steps.append(f"Deixe {name} em local fresco e arejado, com água à vontade.")
        if "atividade" in anomalies or is_ortho:
            steps.append(f"Mantenha {name} contido e sem pular ou correr" + (" — o esforço pode soltar o implante do fêmur." if is_ortho else "."))
        steps.append("NÃO ofereça remédios de uso humano (paracetamol, ibuprofeno etc.).")
        if level == 2:
            steps.append("Venha agora para o pronto-atendimento da CLYVO VET mais próxima.")
        else:
            steps.append("Observe apetite, disposição e a ferida cirúrgica; responda aqui se notar algo diferente.")

        if level == 2:
            header = "🚨 *ALERTA URGENTE CLYVO VET*"
            closing = "📍 A equipe de plantão já recebeu o prontuário do " + name + " e está aguardando vocês."
        else:
            header = "⚠️ *AVISO DE ATENÇÃO CLYVO VET*"
            closing = "A coleira segue monitorando e avisamos imediatamente se os sinais piorarem."
        tutor_message = (f"{header}\n\nOi, {tutor}! A coleira do(a) *{name}* detectou: " + "; ".join(lay or ["alteração nos sinais vitais"])
                         + ".\n\n*O que fazer agora:*\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)) + f"\n\n{closing}")

        hypotheses, plan = [], []
        early_window = pet["needs_post_op"] and 2 <= pet["days_post_op"] <= 7
        if "hipertermia" in anomalies or "febr" in anomalies:
            hypotheses.append("Infecção de sítio cirúrgico (febre na janela D2-D7)" if early_window else "Resposta inflamatória / processo infeccioso")
            plan += ["Inspeção e palpação do sítio cirúrgico", "Hemograma completo e PCR", "Cultura com antibiograma se houver secreção"]
        if "taquicardia" in anomalies:
            hypotheses += ["Dor mal controlada (aplicar escala de Glasgow)", "Desidratação / hipovolemia"]
            plan += ["ECG e pressão arterial", "Hematócrito e proteínas totais", "Reavaliar plano analgésico"]
        if "hipotermia" in anomalies:
            hypotheses.append("Hipotermia pós-anestésica")
            plan += ["Aquecimento ativo controlado", "Temperatura seriada a cada 15 min", "Glicemia"]
        if "bradicardia" in anomalies:
            hypotheses.append("Arritmia / descompensação cardíaca" if "cardi" in procedure.lower() else "Bradicardia associada a hipotermia ou anestesia")
            plan.append("ECG contínuo")
        if "atividade" in anomalies or "movimenta" in anomalies:
            hypotheses.append("Risco de falha de implante / deiscência por atividade" if is_ortho else "Risco de deiscência de sutura por atividade")
            plan.append("Radiografia de controle do implante" if is_ortho else "Inspeção da sutura")
        if "sos" in anomalies or tutor_report:
            hypotheses.append("Emergência relatada pelo tutor — avaliar presencialmente")
            plan.insert(0, "Contato telefônico imediato com o tutor")
        plan.append("Validar este rascunho gerado por IA antes de registrar no prontuário")

        subjective = f"Alerta automático da coleira. {'Pós-operatório D' + str(pet['days_post_op']) + ' de ' if pet['needs_post_op'] else 'Paciente em acompanhamento: '}{procedure.lower()}."
        if tutor_report:
            subjective += f" Relato do tutor: \"{tutor_report.strip()}\"."
        objective = (f"T {reading['temperature']}°C | FC {reading['heart_rate']} BPM | Atividade {reading['movement_level']} | "
                     f"SOS {'sim' if reading.get('emergency') else 'não'}. Tendência: {trend['text']}. "
                     f"Modelo: {risk['risk_label']} ({risk['confidence'] * 100:.0f}%).")
        return {
            "tutor_message": tutor_message,
            "soap": {"subjetivo": subjective, "objetivo": objective,
                     "avaliacao": "Hipóteses: " + "; ".join(hypotheses or ["Alteração inespecífica — reavaliar"]),
                     "plano": list(dict.fromkeys(plan))},
            "hipoteses": hypotheses or ["Alteração inespecífica — reavaliar"],
            "citacoes": [r["ref"] for r in kb_results],
        }

    # --------------------------------------------------------------- summary
    def daily_summary(self, pet: dict, records: list, readings: list, alerts: list) -> dict:
        if not readings:
            return {"resumo": f"Ainda não recebemos leituras da coleira do(a) {pet['name']}.", "destaques": [],
                    "recomendacoes_personalizadas": [], "stats": {}, "llm_mode": "n/a"}
        temps = [r["temperature"] for r in readings]
        hrs = [r["heart_rate"] for r in readings]
        rest = sum(1 for r in readings if r["movement_level"] == "REPOUSO") / len(readings)
        stats = {
            "leituras": len(readings), "temp_min": min(temps), "temp_max": max(temps), "temp_media": round(mean(temps), 1),
            "fc_min": min(hrs), "fc_max": max(hrs), "fc_media": round(mean(hrs)), "pct_repouso": round(rest * 100),
            "alertas": len(alerts), "alertas_criticos": sum(1 for a in alerts if a["risk_level"] == 2),
        }
        kb_results = self.kb.search(f"recuperação {records[0]['description'] if records else ''} {pet['species']} repouso alimentação", k=3)
        context = (f"[PACIENTE]\n{_pet_text(pet)}\n\n[PRONTUÁRIO]\n{_records_text(records)}\n\n[ESTATÍSTICAS DA COLEIRA]\n"
                   + "\n".join(f"{k}: {v}" for k, v in stats.items())
                   + f"\n\n[PROTOCOLOS]\n{KnowledgeBase.format_context(kb_results)}")
        try:
            result = self.llm.generate(SUMMARY_SYSTEM, [{"role": "user", "content": context}], schema=SUMMARY_SCHEMA)
            mode = f"gemini ({self.llm.model})"
        except LLMUnavailable:
            result = self._offline_summary(pet, records, stats)
            mode = "offline (gerador determinístico)"
        result.update({"stats": stats, "llm_mode": mode})
        return result

    @staticmethod
    def _offline_summary(pet: dict, records: list, stats: dict) -> dict:
        name = pet["name"]
        phase = f"{pet['days_post_op']}º dia após a cirurgia" if pet["needs_post_op"] else "acompanhamento contínuo"
        stable = stats["alertas_criticos"] == 0 and stats["temp_max"] <= 39.2
        resumo = (f"{name} está no {phase}. " + ("O dia foi tranquilo: " if stable else "Tivemos pontos de atenção hoje: ")
                  + f"temperatura entre {stats['temp_min']}°C e {stats['temp_max']}°C e batimentos médios de {stats['fc_media']} BPM, "
                  f"com {stats['pct_repouso']}% do tempo em repouso.")
        destaques = [f"{stats['leituras']} leituras analisadas pela IA", f"{stats['alertas']} alerta(s) gerado(s), {stats['alertas_criticos']} crítico(s)"]
        recs = []
        if pet["needs_post_op"]:
            recs.append(f"Mantenha {name} em repouso restrito" + (" — ainda estamos na janela de maior risco de infecção (D2 a D7); confira a ferida 2x ao dia." if 2 <= pet["days_post_op"] <= 7 else "."))
            if stats["pct_repouso"] < 80:
                recs.append(f"{name} se movimentou mais que o ideal; experimente um espaço menor e piso antiderrapante.")
        if pet["species"] == "felino":
            recs.append("Gatos escondem dor: observe se ela está comendo e se não está se escondendo mais que o normal.")
        if pet["age"] >= 10:
            recs.append(f"Como {name} é idoso, conte a respiração dele dormindo; acima de 30 por minuto, avise a clínica.")
        recs.append("Dê somente os medicamentos da receita, nos horários indicados.")
        return {"resumo": resumo, "destaques": destaques, "recomendacoes_personalizadas": recs}
