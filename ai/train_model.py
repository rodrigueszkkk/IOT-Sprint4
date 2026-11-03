"""Treina o classificador de risco e salva models/risk_model.joblib (+ métricas em JSON).

Uso:  python ai/train_model.py
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import get_settings  # noqa: E402
from app.services.risk_model import train_and_save  # noqa: E402

if __name__ == "__main__":
    settings = get_settings()
    metrics = train_and_save(settings.dataset_path, settings.model_path)
    print("Comparação de modelos (validação cruzada 5-fold, F1-macro):")
    print(json.dumps(metrics["model_comparison"], indent=2))
    print(f"\nModelo selecionado: {metrics['selected_model']}")
    print(f"Acurácia teste: {metrics['test_accuracy']:.3f} | F1-macro: {metrics['test_f1_macro']:.3f} | "
          f"Recall CRÍTICO: {metrics['test_recall_critico']:.3f} (sistema c/ dupla checagem: {metrics['test_recall_critico_sistema']:.3f})")
    print(f"Matriz de confusão (linhas=real, colunas=previsto | ESTÁVEL, ATENÇÃO, CRÍTICO): {metrics['confusion_matrix']}")
    print(f"Modelo salvo em {settings.model_path}")
