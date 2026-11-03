"""Validação das barreiras de segurança da IA."""
from app.services import guardrails as g


def test_detecta_sinais_de_emergencia():
    assert "convulsão" in g.detect_red_flags("Ele está tendo uma CONVULSÃO agora")
    assert "deiscência de sutura" in g.detect_red_flags("os pontos abriram")
    assert g.detect_red_flags("Ele dormiu bem e comeu a ração") == []


def test_detecta_medicamento_humano():
    assert g.detect_human_medication("posso dar Paracetamol?") == ["paracetamol"]
    assert g.detect_human_medication("e ibuprofeno ou dipirona?") == ["ibuprofeno", "dipirona"]
    assert g.detect_human_medication("qual o horário do meloxicam?") == []


def test_resposta_medicamento_alerta_gatos():
    reply = g.medication_safe_reply("Luna", ["paracetamol"], "felino")
    assert "fatal" in reply and "Luna" in reply


def test_remove_dose_fora_da_prescricao_e_mantem_prescrita():
    prescription = "Meloxicam 0,1 mg/kg SID por 7 dias"
    text = "Pode manter o meloxicam 0,1 mg/kg e dar 500 mg de dipirona."
    clean = g.sanitize_output(text, prescription)
    assert "0,1 mg/kg" in clean
    assert "500 mg" not in clean
    assert "[dose definida pelo veterinário]" in clean
    assert g.DISCLAIMER in clean
