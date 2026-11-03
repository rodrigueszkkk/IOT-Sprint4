"""Configuração central da aplicação CLYVO VET (lida de variáveis de ambiente / arquivo .env)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Carrega um .env simples (CHAVE=valor) sem sobrescrever variáveis já definidas."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


@dataclass
class Settings:
    db_path: str = field(default_factory=lambda: os.getenv("CLYVO_DB_PATH", str(BASE_DIR / "database" / "clyvo.db")))
    model_path: str = field(default_factory=lambda: os.getenv("CLYVO_MODEL_PATH", str(BASE_DIR / "models" / "risk_model.joblib")))
    dataset_path: str = field(default_factory=lambda: os.getenv("CLYVO_DATASET_PATH", str(BASE_DIR / "ai" / "data" / "dataset_telemetry.csv")))
    knowledge_dir: str = field(default_factory=lambda: os.getenv("CLYVO_KNOWLEDGE_DIR", str(BASE_DIR / "ai" / "data" / "knowledge")))
    # "gemini" (padrão, exige GEMINI_API_KEY do Google AI Studio) ou "offline" (gerador determinístico, usado nos testes)
    llm_provider: str = field(default_factory=lambda: os.getenv("CLYVO_LLM_PROVIDER", "gemini").lower())
    llm_model: str = field(default_factory=lambda: os.getenv("CLYVO_LLM_MODEL", "gemini-flash-latest"))
    # Intervalo mínimo (em minutos) entre dois alertas do mesmo nível para o mesmo pet
    alert_cooldown_minutes: float = field(default_factory=lambda: float(os.getenv("CLYVO_ALERT_COOLDOWN_MIN", "5")))


def get_settings() -> Settings:
    return Settings()
