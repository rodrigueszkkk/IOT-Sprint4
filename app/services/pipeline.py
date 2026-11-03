"""Orquestração ponta a ponta: telemetria IoT -> modelo preditivo -> copiloto generativo -> notificações."""
from datetime import datetime, timedelta

from ..database import Database, utcnow
from .chat_agent import TutorChatAgent
from .copilot import ClinicalCopilot
from .risk_model import RiskModel

SCENARIOS = {
    # nome: lista de (temp, delta_fc_sobre_basal, movimento, sos)
    "normal": [(38.5, 0, "REPOUSO", False)],
    "atencao": [(39.3, 15, "MODERADO", False)],
    "critico": [(39.9, 55, "ALTO", False)],
    "sos": [(38.9, 20, "REPOUSO", True)],
    "hipotermia": [(36.8, -40, "REPOUSO", False)],
    "febre_progressiva": [(38.7, 0, "REPOUSO", False), (38.9, 5, "REPOUSO", False), (39.1, 10, "REPOUSO", False),
                          (39.4, 18, "MODERADO", False), (39.7, 30, "MODERADO", False), (40.1, 45, "REPOUSO", False)],
}


class MonitoringPipeline:
    def __init__(self, db: Database, risk_model: RiskModel, copilot: ClinicalCopilot, chat: TutorChatAgent, cooldown_minutes: float):
        self.db = db
        self.risk_model = risk_model
        self.copilot = copilot
        self.chat = chat
        self.cooldown = timedelta(minutes=cooldown_minutes)

    def process_reading(self, pet: dict, reading: dict) -> dict:
        risk = self.risk_model.predict(reading, pet)
        telemetry_id = self.db.add_telemetry({
            "pet_id": pet["id"], "device_id": reading.get("device_id"), "temperature": reading["temperature"],
            "heart_rate": reading["heart_rate"], "movement_level": reading["movement_level"], "emergency": int(bool(reading.get("emergency"))),
            "risk_level": risk["risk_level"], "risk_label": risk["risk_label"], "confidence": risk["confidence"],
            "probabilities": risk["probabilities"], "anomalies": risk["anomalies"], "safety_override": risk["safety_override"],
            "created_at": reading.get("timestamp"),
        })

        result = {"telemetry_id": telemetry_id, "pet_id": pet["id"], "pet_name": pet["name"], "risk": risk, "alert": None, "alert_skipped": None}
        if risk["risk_level"] == 0:
            return result

        # Anti-spam: não repete alerta do mesmo nível dentro da janela de cooldown, a menos que o
        # quadro tenha se agravado (surgiu uma anomalia que o alerta anterior não tinha) ou haja SOS
        last = self.db.last_alert(pet["id"], risk["risk_level"])
        if last and not reading.get("emergency") and utcnow() - datetime.fromisoformat(last["created_at"]) < self.cooldown:
            previous = self.db.get_telemetry_by_id(last["telemetry_id"]) if last["telemetry_id"] else None
            previous_kinds = {a.split(" (")[0] for a in (previous or {}).get("anomalies") or []}
            new_kinds = {a.split(" (")[0] for a in risk["anomalies"]} - previous_kinds
            if not new_kinds:
                result["alert_skipped"] = f"alerta {risk['risk_label']} já emitido há menos de {self.cooldown.total_seconds() / 60:g} min sem agravamento (anti-spam)"
                return result

        result["alert"] = self.create_alert(pet, reading, risk, telemetry_id, source="telemetria")
        return result

    def create_alert(self, pet: dict, reading: dict, risk: dict, telemetry_id: int | None, source: str, tutor_report: str | None = None) -> dict:
        records = self.db.get_records(pet["id"])
        readings = self.db.get_telemetry(pet["id"], limit=24)
        generated = self.copilot.generate_alert(pet, records, readings, reading, risk, tutor_report=tutor_report)
        alert_id = self.db.add_alert({
            "pet_id": pet["id"], "telemetry_id": telemetry_id, "source": source, "risk_level": risk["risk_level"],
            "priority": risk["triage_priority"], "tutor_message": generated["tutor_message"], "soap": generated["soap"],
            "hypotheses": generated["hipoteses"], "citations": generated["citacoes"], "llm_mode": generated["llm_mode"],
        })
        self.db.add_notification({"pet_id": pet["id"], "alert_id": alert_id, "channel": "WhatsApp",
                                  "recipient": f"{pet['tutor_name']} ({pet['tutor_phone']})", "message": generated["tutor_message"]})
        if risk["risk_level"] == 2:
            self.db.add_notification({"pet_id": pet["id"], "alert_id": alert_id, "channel": "Painel da clínica",
                                      "recipient": "Equipe de plantão", "message": f"{risk['triage_priority']} — {pet['name']}: "
                                      + "; ".join(generated["hipoteses"][:2])})
        alert = self.db.get_alert(alert_id)
        alert["retrieved"] = generated["retrieved"]
        alert["trend"] = generated["trend"]
        return alert

    def simulate(self, pet: dict, scenario: str) -> list:
        base_hr = 165 if pet["species"] == "felino" else (112 if pet["age"] >= 10 else 96)
        results = []
        for temp, hr_delta, movement, sos in SCENARIOS[scenario]:
            reading = {"device_id": pet["device_id"], "temperature": temp, "heart_rate": int(base_hr + hr_delta * (1.3 if pet["species"] == "felino" else 1)),
                       "movement_level": movement, "emergency": sos}
            results.append(self.process_reading(pet, reading))
        return results

    def chat_message(self, pet: dict, message: str) -> dict:
        records = self.db.get_records(pet["id"])
        readings = self.db.get_telemetry(pet["id"], limit=24)
        latest = readings[-1] if readings else None
        history = self.db.get_chat(pet["id"], limit=10)
        self.db.add_chat(pet["id"], "user", message)
        reply = self.chat.reply(pet, records, readings, latest, history, message)
        self.db.add_chat(pet["id"], "assistant", reply["answer"], reply["llm_mode"])

        if reply["escalate"]:
            base = latest or {"temperature": 38.5, "heart_rate": 100, "movement_level": "REPOUSO"}
            reading = {"temperature": base["temperature"], "heart_rate": base["heart_rate"], "movement_level": base["movement_level"], "emergency": True}
            risk = self.risk_model.predict(reading, pet)
            risk["anomalies"] = [f"Relato do tutor: {', '.join(reply['red_flags'])}"] + risk["anomalies"]
            reply["alert"] = self.create_alert(pet, reading, risk, None, source="chat", tutor_report=message)
        return reply
