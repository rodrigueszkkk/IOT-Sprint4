import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.knowledge_base import KnowledgeBase  # noqa: E402
from app.services.risk_model import RiskModel  # noqa: E402


@pytest.fixture()
def settings(tmp_path) -> Settings:
    # Banco temporário e IA generativa em modo offline: testes determinísticos e sem custo de API
    s = Settings()
    s.db_path = str(tmp_path / "test.db")
    s.llm_provider = "offline"
    s.alert_cooldown_minutes = 5
    return s


@pytest.fixture()
def client(settings) -> TestClient:
    return TestClient(create_app(settings))


@pytest.fixture(scope="session")
def risk_model() -> RiskModel:
    s = Settings()
    return RiskModel(s.model_path, s.dataset_path)


@pytest.fixture(scope="session")
def kb() -> KnowledgeBase:
    return KnowledgeBase(Settings().knowledge_dir)
