"""Regras clínicas de referência (faixas fisiológicas por espécie) usadas em três lugares:

1. Rotulagem do dataset sintético de treino (ai/generate_dataset.py);
2. Explicação das anomalias detectadas em cada leitura (explicabilidade para o veterinário);
3. Override de segurança: o botão SOS sempre resulta em CRÍTICO, independentemente do modelo.

Faixas baseadas em literatura de clínica de pequenos animais (valores de repouso).
"""
from dataclasses import dataclass

SPECIES_CODES = {"canino": 0, "felino": 1}
MOVEMENT_CODES = {"REPOUSO": 0, "MODERADO": 1, "ALTO": 2}
RISK_LABELS = {0: "ESTÁVEL", 1: "ATENÇÃO", 2: "CRÍTICO"}
TRIAGE = {0: "P3 - VERDE (Eletivo)", 1: "P2 - AMARELO (Urgente)", 2: "P1 - VERMELHO (Imediato)"}

REFERENCE = {
    0: {"temp": (37.5, 39.2), "hr": (60, 140), "hr_severe": (50, 160)},   # canino
    1: {"temp": (37.8, 39.2), "hr": (120, 200), "hr_severe": (100, 220)},  # felino
}


@dataclass
class RuleResult:
    score: int
    level: int
    anomalies: list


def evaluate(species: int, age: float, needs_post_op: int, days_post_op: int, temp: float,
             hr: float, movement: int, emergency: int) -> RuleResult:
    ref = REFERENCE.get(int(species), REFERENCE[0])
    score = 0
    anomalies = []

    # Temperatura corporal
    if temp > 40.0:
        score += 3
        anomalies.append(f"Hipertermia severa ({temp:.1f}°C > 40.0°C)")
    elif temp > 39.5:
        score += 2
        anomalies.append(f"Hipertermia ({temp:.1f}°C > 39.5°C)")
    elif temp > ref["temp"][1]:
        score += 1
        anomalies.append(f"Febrícula ({temp:.1f}°C)")
    elif temp < 37.0:
        score += 3
        anomalies.append(f"Hipotermia severa ({temp:.1f}°C < 37.0°C)")
    elif temp < ref["temp"][0]:
        score += 2
        anomalies.append(f"Hipotermia ({temp:.1f}°C < {ref['temp'][0]}°C)")

    # Frequência cardíaca (faixas diferentes para cães e gatos)
    lo, hi = ref["hr"]
    slo, shi = ref["hr_severe"]
    if hr > shi:
        score += 2
        anomalies.append(f"Taquicardia acentuada ({hr:.0f} BPM)")
    elif hr > hi:
        score += 1
        anomalies.append(f"Taquicardia leve ({hr:.0f} BPM)")
    elif hr < slo:
        score += 2
        anomalies.append(f"Bradicardia acentuada ({hr:.0f} BPM)")
    elif hr < lo:
        score += 1
        anomalies.append(f"Bradicardia leve ({hr:.0f} BPM)")

    # Repouso pós-operatório
    if needs_post_op:
        if movement == 2:
            score += 2 if days_post_op <= 14 else 1
            anomalies.append("Atividade intensa durante repouso pós-cirúrgico")
        elif movement == 1 and days_post_op <= 3:
            score += 1
            anomalies.append("Movimentação moderada nas primeiras 72h pós-cirurgia")
        # Janela de maior risco de infecção de ferida (dias 2 a 7) potencializa a febre
        if 2 <= days_post_op <= 7 and temp > ref["temp"][1]:
            score += 1
            anomalies.append("Febre na janela de risco de infecção cirúrgica (D2-D7)")

    # Pacientes geriátricos descompensam mais rápido
    if age >= 10 and score > 0:
        score += 1
        anomalies.append(f"Paciente geriátrico ({age:.0f} anos) com parâmetro alterado")

    if emergency:
        score += 4
        anomalies.append("Botão SOS acionado pelo tutor")

    level = 2 if (score >= 3 or emergency) else (1 if score >= 1 else 0)
    return RuleResult(score=score, level=level, anomalies=anomalies)
