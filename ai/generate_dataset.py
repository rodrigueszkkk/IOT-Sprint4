"""Gera o dataset sintético de telemetria veterinária usado para treinar o classificador de risco.

Como não temos (ainda) dados reais rotulados da clínica, o dataset é construído assim:
  1. Sorteamos pacientes e cenários clínicos (recuperação normal, febre, taquicardia, hipotermia
     pós-anestésica, agitação pós-cirúrgica, SOS) com distribuições plausíveis;
  2. Cada leitura "verdadeira" é rotulada pelas regras clínicas de referência (app/services/clinical_rules.py);
  3. Adicionamos ruído de sensor às features (o modelo vê a leitura ruidosa, como na coleira real)
     e 4% de ruído de rótulo (discordância entre veterinários).

Uso:  python ai/generate_dataset.py  [--rows 4000] [--seed 42]
"""
import argparse
import csv
import random
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.clinical_rules import evaluate  # noqa: E402

FIELDS = ["species", "age", "needs_post_op", "days_post_op", "temp_celsius", "heart_rate_bpm",
          "movement_level", "emergency_btn", "risk_level", "clinical_diagnosis"]

SCENARIOS = [
    # (nome, peso, gerador de (temp, hr_offset, movimento, sos))
    ("recuperacao_normal", 0.38, lambda r: (r.gauss(38.5, 0.35), r.gauss(0, 12), r.choices([0, 1, 2], [0.7, 0.25, 0.05])[0], 0)),
    ("febricula", 0.14, lambda r: (r.uniform(39.2, 39.7), r.gauss(10, 12), r.choices([0, 1, 2], [0.6, 0.3, 0.1])[0], 0)),
    ("febre_alta", 0.10, lambda r: (r.uniform(39.6, 41.0), r.gauss(25, 15), r.choices([0, 1, 2], [0.5, 0.3, 0.2])[0], 0)),
    ("taquicardia", 0.09, lambda r: (r.gauss(38.8, 0.4), r.uniform(15, 80), r.choices([0, 1, 2], [0.4, 0.4, 0.2])[0], 0)),
    ("hipotermia_bradicardia", 0.06, lambda r: (r.uniform(36.2, 37.8), r.uniform(-35, -5), 0, 0)),
    # v2: arritmias/bradicardia em qualquer paciente (lacuna encontrada na avaliação dos cenários geriátricos)
    ("bradicardia", 0.05, lambda r: (r.gauss(38.3, 0.3), r.uniform(-65, -30), r.choices([0, 1], [0.8, 0.2])[0], 0)),
    ("agitacao_pos_op", 0.12, lambda r: (r.gauss(38.9, 0.4), r.gauss(15, 12), 2, 0)),
    ("sos_tutor", 0.06, lambda r: (r.gauss(38.9, 0.6), r.gauss(15, 20), r.choices([0, 1, 2], [0.4, 0.3, 0.3])[0], 1)),
]

DIAGNOSIS = {
    "recuperacao_normal": "Evolucao estavel sem intercorrencias",
    "febricula": "Febricula / possivel inflamacao local",
    "febre_alta": "Hipertermia - suspeita de infeccao",
    "taquicardia": "Taquicardia - dor ou desidratacao",
    "hipotermia_bradicardia": "Hipotermia / bradicardia pos-anestesica",
    "bradicardia": "Bradicardia / possivel arritmia",
    "agitacao_pos_op": "Violacao de repouso pos-cirurgico",
    "sos_tutor": "Emergencia sinalizada pelo tutor",
}


def generate(rows: int, seed: int):
    rnd = random.Random(seed)
    names, weights, gens = zip(*SCENARIOS)
    data = []
    for _ in range(rows):
        idx = rnd.choices(range(len(names)), weights)[0]
        species = rnd.choices([0, 1], [0.65, 0.35])[0]
        age = max(0.5, round(rnd.gauss(6, 3.5), 1))
        if names[idx] in ("bradicardia", "taquicardia") and rnd.random() < 0.4:
            age = round(rnd.uniform(10, 16), 1)  # cardiopatias são mais comuns em idosos
        post_op = 1 if (names[idx] == "agitacao_pos_op" or (names[idx] == "hipotermia_bradicardia" and rnd.random() < 0.7)
                        or rnd.random() < 0.55) else 0
        days = rnd.randint(0, 21) if post_op else 0
        if names[idx] == "hipotermia_bradicardia" and post_op:
            days = rnd.randint(0, 1)  # típico do pós-anestésico imediato
        temp, hr_offset, movement, sos = gens[idx](rnd)
        base_hr = 100 if species == 0 else 160
        hr = base_hr + hr_offset * (1.0 if species == 0 else 1.2)

        level = evaluate(species, age, post_op, days, temp, hr, movement, sos).level
        if rnd.random() < 0.04:  # ruído de rótulo para classes vizinhas
            level = min(2, max(0, level + rnd.choice([-1, 1])))

        noisy_temp = round(temp + rnd.gauss(0, 0.1), 1)
        noisy_hr = int(round(hr + rnd.gauss(0, 3)))
        data.append([species, age, post_op, days, noisy_temp, noisy_hr, movement, sos, level, DIAGNOSIS[names[idx]]])
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(BASE_DIR / "ai" / "data" / "dataset_telemetry.csv"))
    args = parser.parse_args()

    data = generate(args.rows, args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(data)

    counts = {0: 0, 1: 0, 2: 0}
    for row in data:
        counts[row[8]] += 1
    print(f"Dataset gerado em {args.out}: {len(data)} linhas | ESTÁVEL={counts[0]} ATENÇÃO={counts[1]} CRÍTICO={counts[2]}")


if __name__ == "__main__":
    main()
