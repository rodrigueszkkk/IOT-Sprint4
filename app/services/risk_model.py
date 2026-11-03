"""Classificador preditivo de risco vital (Machine Learning supervisionado).

- Features: as 8 leituras/atributos do paciente + 2 variáveis derivadas (FC normalizada pelos limites
  da espécie), que permitem ao modelo comparar cães e gatos na mesma escala.
- Treino: compara Regressão Logística, Árvore de Decisão, Random Forest e Gradient Boosting com
  validação cruzada estratificada (5 folds), escolhe o melhor por F1-macro e avalia no holdout (25%).
- Explicabilidade: importância por permutação (vale para qualquer algoritmo) + anomalias clínicas.
- Inferência: devolve nível de risco, probabilidades por classe, prioridade de triagem e as anomalias
  que justificam a decisão (explicabilidade).
- Segurança (dupla checagem): o botão SOS e os limites críticos do protocolo clínico (ex.: T > 40 °C,
  T < 37 °C, bradicardia acentuada) sempre resultam em CRÍTICO, mesmo que o modelo discorde. O modelo
  continua decidindo os demais casos e fornece a probabilidade de cada classe.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from . import clinical_rules as rules

RAW_FEATURES = ["species", "age", "needs_post_op", "days_post_op", "temp_celsius", "heart_rate_bpm",
                "movement_level", "emergency_btn"]
FEATURES = RAW_FEATURES + ["hr_rel_high", "hr_rel_low"]


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """FC dividida pelos limites de normalidade da espécie (1.0 = no limite; >1 acima do máximo)."""
    df = df.copy()
    hi = df["species"].map(lambda s: rules.REFERENCE.get(int(s), rules.REFERENCE[0])["hr"][1])
    lo = df["species"].map(lambda s: rules.REFERENCE.get(int(s), rules.REFERENCE[0])["hr"][0])
    df["hr_rel_high"] = df["heart_rate_bpm"] / hi
    df["hr_rel_low"] = df["heart_rate_bpm"] / lo
    return df
MODEL_VERSION = "risk-ml-v2 (sprint 4)"


def _candidates():
    return {
        "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)),
        "DecisionTree": DecisionTreeClassifier(max_depth=6, random_state=42),
        "RandomForest": RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced", random_state=42),
        "GradientBoosting": HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=42),
    }


def train_and_save(dataset_path: str, model_path: str) -> dict:
    df = add_derived_features(pd.read_csv(dataset_path))
    X, y = df[FEATURES], df["risk_level"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    comparison = {}
    for name, estimator in _candidates().items():
        scores = cross_val_score(estimator, X_train, y_train, cv=cv, scoring="f1_macro")
        comparison[name] = {"cv_f1_macro_mean": round(float(scores.mean()), 4), "cv_f1_macro_std": round(float(scores.std()), 4)}

    best_name = max(comparison, key=lambda n: comparison[n]["cv_f1_macro_mean"])
    model = _candidates()[best_name]
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    # Sistema final = modelo + dupla checagem (SOS ou limite crítico do protocolo forçam CRÍTICO)
    rule_levels = np.array([rules.evaluate(r.species, r.age, r.needs_post_op, r.days_post_op, r.temp_celsius,
                                           r.heart_rate_bpm, r.movement_level, r.emergency_btn).level
                            for r in X_test[RAW_FEATURES].itertuples()])
    y_system = np.where(rule_levels == 2, 2, y_pred)

    perm = permutation_importance(model, X_test, y_test, scoring="f1_macro", n_repeats=5, random_state=42)
    importances = {f: round(float(v), 4) for f, v in sorted(zip(FEATURES, perm.importances_mean), key=lambda t: -t[1])}

    metrics = {
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_rows": int(len(df)),
        "class_distribution": {rules.RISK_LABELS[k]: int(v) for k, v in y.value_counts().sort_index().items()},
        "selected_model": best_name,
        "model_comparison": comparison,
        "test_accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "test_f1_macro": round(float(f1_score(y_test, y_pred, average="macro")), 4),
        "test_recall_critico": round(float(recall_score(y_test, y_pred, labels=[2], average="macro")), 4),
        "test_recall_critico_sistema": round(float(recall_score(y_test, y_system, labels=[2], average="macro")), 4),
        "test_accuracy_sistema": round(float(accuracy_score(y_test, y_system)), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=[0, 1, 2]).tolist(),
        "classification_report": classification_report(
            y_test, y_pred, labels=[0, 1, 2], target_names=list(rules.RISK_LABELS.values()), output_dict=True, zero_division=0),
        "feature_importances": importances,
    }

    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "metrics": metrics}, model_path)
    Path(model_path).with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    return metrics


class RiskModel:
    def __init__(self, model_path: str, dataset_path: str):
        self.model_path = model_path
        self.dataset_path = dataset_path
        bundle = None
        if Path(model_path).exists():
            try:
                bundle = joblib.load(model_path)
            except Exception:  # artefato salvo com outra versão do scikit-learn: retreina abaixo
                bundle = None
        if bundle is None or bundle.get("features") != FEATURES:
            # Primeira execução (ou artefato incompatível): treina a partir do dataset versionado
            train_and_save(dataset_path, model_path)
            bundle = joblib.load(model_path)
        self.model = bundle["model"]
        self.metrics = bundle["metrics"]

    @staticmethod
    def build_features(reading: dict, pet: dict) -> dict:
        return {
            "species": rules.SPECIES_CODES.get(str(pet.get("species", "canino")).lower(), 0),
            "age": float(pet.get("age", 4)),
            "needs_post_op": 1 if pet.get("needs_post_op") else 0,
            "days_post_op": int(pet.get("days_post_op") or 0),
            "temp_celsius": float(reading["temperature"]),
            "heart_rate_bpm": float(reading["heart_rate"]),
            "movement_level": rules.MOVEMENT_CODES.get(reading.get("movement_level", "REPOUSO"), 0),
            "emergency_btn": 1 if reading.get("emergency") else 0,
        }

    def predict(self, reading: dict, pet: dict) -> dict:
        feats = self.build_features(reading, pet)
        frame = add_derived_features(pd.DataFrame([feats], columns=RAW_FEATURES))[FEATURES]
        proba = self.model.predict_proba(frame)[0]
        classes = [int(c) for c in self.model.classes_]
        probabilities = {rules.RISK_LABELS[c]: round(float(p), 4) for c, p in zip(classes, proba)}
        level = classes[int(np.argmax(proba))]

        rule = rules.evaluate(feats["species"], feats["age"], feats["needs_post_op"], feats["days_post_op"],
                              feats["temp_celsius"], feats["heart_rate_bpm"], feats["movement_level"], feats["emergency_btn"])
        model_level = level
        override = None
        if feats["emergency_btn"] and level != 2:
            override = "SOS do tutor força nível CRÍTICO (regra de segurança)"
            level = 2
        elif rule.level == 2 and level != 2:
            override = "Limite crítico do protocolo clínico força nível CRÍTICO (dupla checagem)"
            level = 2

        return {
            "risk_level": level,
            "risk_label": rules.RISK_LABELS[level],
            "triage_priority": rules.TRIAGE[level],
            "confidence": round(float(max(proba)), 4) if override is None else 1.0,
            "probabilities": probabilities,
            "anomalies": rule.anomalies,
            "model_level": model_level,
            "rule_level": rule.level,
            "safety_override": override,
            "model_version": MODEL_VERSION,
        }
