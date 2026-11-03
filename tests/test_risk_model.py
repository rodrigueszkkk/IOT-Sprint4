"""Validação do classificador de risco (Machine Learning)."""
import pytest

THOR = {"species": "canino", "age": 4, "needs_post_op": True, "days_post_op": 4}
LUNA = {"species": "felino", "age": 2, "needs_post_op": True, "days_post_op": 1}
BOB = {"species": "canino", "age": 12, "needs_post_op": False, "days_post_op": 0}


def reading(temp, hr, movement="REPOUSO", sos=False):
    return {"temperature": temp, "heart_rate": hr, "movement_level": movement, "emergency": sos}


def test_metricas_minimas_do_modelo(risk_model):
    m = risk_model.metrics
    assert m["selected_model"] in m["model_comparison"]
    assert m["test_accuracy"] >= 0.85
    assert m["test_f1_macro"] >= 0.85
    # Errar um paciente crítico é o erro mais caro: exigimos recall alto nessa classe, e o sistema
    # final (modelo + dupla checagem clínica) precisa ser ainda mais sensível que o modelo puro
    assert m["test_recall_critico"] >= 0.85
    assert m["test_recall_critico_sistema"] >= m["test_recall_critico"]


@pytest.mark.parametrize("pet,read,expected", [
    (THOR, reading(38.5, 95), "ESTÁVEL"),
    (THOR, reading(39.9, 152, "ALTO"), "CRÍTICO"),
    (THOR, reading(40.5, 110), "CRÍTICO"),
    (LUNA, reading(36.6, 95), "CRÍTICO"),
    (LUNA, reading(38.6, 170), "ESTÁVEL"),  # 170 BPM é normal para gatos
    (BOB, reading(38.4, 112), "ESTÁVEL"),
])
def test_cenarios_clinicos(risk_model, pet, read, expected):
    assert risk_model.predict(read, pet)["risk_label"] == expected


def test_sos_sempre_critico(risk_model):
    result = risk_model.predict(reading(38.5, 95, sos=True), THOR)
    assert result["risk_label"] == "CRÍTICO"
    assert result["triage_priority"].startswith("P1")
    assert any("SOS" in a for a in result["anomalies"])


def test_explicabilidade_e_probabilidades(risk_model):
    result = risk_model.predict(reading(39.9, 152, "ALTO"), THOR)
    assert abs(sum(result["probabilities"].values()) - 1) < 1e-3
    assert any("Hipertermia" in a for a in result["anomalies"])
    assert any("repouso" in a for a in result["anomalies"])
