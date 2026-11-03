"""Testes de integração: interface (API) <-> banco <-> modelo de ML <-> IA generativa."""


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["llm_mode"] == "offline"
    assert body["knowledge_chunks"] > 20


def test_lista_pets_com_seed(client):
    pets = client.get("/api/pets").json()
    assert [p["name"] for p in pets] == ["Thor", "Luna", "Bob"]
    assert pets[0]["latest"]["risk_label"] == "ESTÁVEL"


def test_telemetria_no_formato_do_firmware_wokwi(client):
    # Mesma linha JSON que o smart_collar.ino imprime no Monitor Serial
    payload = {"petId": 1, "petName": "Thor", "temperatura": 38.4, "bpm": 92, "movimento": False,
               "sos": False, "status": "ESTAVEL", "riskScore": 0}
    r = client.post("/api/telemetry", json=payload)
    assert r.status_code == 201
    assert r.json()["risk"]["risk_label"] == "ESTÁVEL"
    assert r.json()["alert"] is None


def test_telemetria_invalida(client):
    assert client.post("/api/telemetry", json={"deviceId": "X", "temperature": 38, "heartRateBpm": 90}).status_code == 404
    bad = {"deviceId": "CLYVO-COLLAR-01", "temperature": 38, "heartRateBpm": 90, "movementLevel": "VOANDO"}
    assert client.post("/api/telemetry", json=bad).status_code == 422


def test_cenario_critico_gera_alerta_soap_e_notificacoes(client):
    result = client.post("/api/simulate/critico?pet_id=1").json()[0]
    assert result["risk"]["risk_label"] == "CRÍTICO"
    alert = result["alert"]
    assert "Thor" in alert["tutor_message"] and "Mariana" in alert["tutor_message"]
    assert set(alert["soap"]) == {"subjetivo", "objetivo", "avaliacao", "plano"}
    assert "osteossíntese" in alert["soap"]["subjetivo"]
    assert alert["citations"]  # o rascunho cita os protocolos recuperados
    channels = {n["channel"] for n in client.get("/api/notifications").json()}
    assert channels == {"WhatsApp", "Painel da clínica"}


def test_triagem_prioriza_paciente_critico(client):
    client.post("/api/simulate/hipotermia?pet_id=2")
    queue = client.get("/api/triage").json()
    assert queue[0]["pet"]["name"] == "Luna" and queue[0]["level"] == 2


def test_anti_spam_e_reemissao_quando_agrava(client):
    first = client.post("/api/simulate/atencao?pet_id=1").json()[0]
    assert first["alert"] is not None
    repeat = client.post("/api/simulate/atencao?pet_id=1").json()[0]
    assert repeat["alert"] is None and "anti-spam" in repeat["alert_skipped"]
    sos = client.post("/api/simulate/sos?pet_id=1").json()[0]
    assert sos["alert"] is not None  # SOS nunca é bloqueado


def test_assumir_atendimento(client):
    alert = client.post("/api/simulate/critico?pet_id=1").json()[0]["alert"]
    updated = client.patch(f"/api/alerts/{alert['id']}/ack").json()
    assert updated["status"] == "EM ATENDIMENTO"


def test_chat_personalizado_com_prontuario(client):
    reply = client.post("/api/pets/1/chat", json={"message": "Qual o horário do remédio?"}).json()
    assert "Meloxicam" in reply["answer"]
    status = client.post("/api/pets/1/chat", json={"message": "Como o Thor está agora?"}).json()
    assert status["intent"] == "status" and "°C" in status["answer"]
    history = client.get("/api/pets/1/chat").json()
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]


def test_chat_bloqueia_medicamento_humano(client):
    reply = client.post("/api/pets/2/chat", json={"message": "Posso dar paracetamol pra Luna?"}).json()
    assert reply["intent"] == "medicamento_humano"
    assert "fatal" in reply["answer"]


def test_chat_emergencia_escala_alerta_p1(client):
    reply = client.post("/api/pets/1/chat", json={"message": "Os pontos abriram e está sangrando muito!"}).json()
    assert reply["escalate"] is True
    assert reply["alert"]["source"] == "chat"
    assert reply["alert"]["priority"].startswith("P1")
    assert "sangrando" in reply["alert"]["soap"]["subjetivo"]


def test_resumo_diario_personalizado(client):
    client.post("/api/simulate/atencao?pet_id=1")
    summary = client.get("/api/pets/1/summary").json()
    assert "Thor" in summary["resumo"]
    assert summary["stats"]["leituras"] >= 20
    assert any("D2 a D7" in r for r in summary["recomendacoes_personalizadas"])
