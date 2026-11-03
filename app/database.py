"""Camada de persistência (SQLite local, schema espelhado em database/schema_mysql.sql para produção).

Tabelas: tutors, pets, medical_records (prontuário), telemetry (leituras da coleira + inferência do
modelo), alerts (saída da IA Generativa), chat_messages (assistente do tutor) e notifications (fila
de envio WhatsApp/push).
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tutors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT
);
CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tutor_id INTEGER NOT NULL REFERENCES tutors(id),
    name TEXT NOT NULL,
    species TEXT NOT NULL,
    breed TEXT,
    age REAL,
    weight_kg REAL,
    needs_post_op INTEGER NOT NULL DEFAULT 0,
    surgery_date TEXT,
    device_id TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS medical_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    record_date TEXT NOT NULL,
    description TEXT NOT NULL,
    diagnosis TEXT,
    treatment TEXT,
    veterinarian TEXT
);
CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    device_id TEXT,
    temperature REAL NOT NULL,
    heart_rate INTEGER NOT NULL,
    movement_level TEXT NOT NULL,
    emergency INTEGER NOT NULL DEFAULT 0,
    risk_level INTEGER,
    risk_label TEXT,
    confidence REAL,
    probabilities TEXT,
    anomalies TEXT,
    safety_override TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telemetry_pet ON telemetry(pet_id, created_at);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    telemetry_id INTEGER REFERENCES telemetry(id),
    source TEXT NOT NULL,
    risk_level INTEGER NOT NULL,
    priority TEXT NOT NULL,
    tutor_message TEXT NOT NULL,
    soap TEXT NOT NULL,
    hypotheses TEXT,
    citations TEXT,
    llm_mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ABERTO',
    created_at TEXT NOT NULL,
    acknowledged_at TEXT
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    llm_mode TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    alert_id INTEGER REFERENCES alerts(id),
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ENVIADO (simulado)',
    created_at TEXT NOT NULL
);
"""

JSON_FIELDS = {"probabilities", "anomalies", "soap", "hypotheses", "citations"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(SCHEMA)
        if not self.list_pets():
            self.seed()

    @contextmanager
    def _conn(self):
        # Abre, faz commit (ou rollback) e fecha a conexão a cada operação: seguro para as threads do FastAPI
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _row(row) -> dict | None:
        if row is None:
            return None
        data = dict(row)
        for key in JSON_FIELDS & data.keys():
            if data[key]:
                data[key] = json.loads(data[key])
        return data

    def _all(self, sql: str, params=()) -> list:
        with self._conn() as conn:
            return [self._row(r) for r in conn.execute(sql, params).fetchall()]

    def _one(self, sql: str, params=()) -> dict | None:
        with self._conn() as conn:
            return self._row(conn.execute(sql, params).fetchone())

    def _insert(self, table: str, data: dict) -> int:
        data = {k: (json.dumps(v, ensure_ascii=False) if k in JSON_FIELDS and v is not None else v) for k, v in data.items()}
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        with self._conn() as conn:
            return conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values())).lastrowid

    # ------------------------------------------------------------------ seed
    def seed(self) -> None:
        today = utcnow().date()
        mariana = self._insert("tutors", {"name": "Mariana Silva", "phone": "+55 11 98888-1001", "email": "mariana@example.com"})
        rafael = self._insert("tutors", {"name": "Rafael Souza", "phone": "+55 11 97777-2002", "email": "rafael@example.com"})
        helena = self._insert("tutors", {"name": "Helena Prado", "phone": "+55 11 96666-3003", "email": "helena@example.com"})

        thor = self._insert("pets", {"tutor_id": mariana, "name": "Thor", "species": "canino", "breed": "Golden Retriever",
                                     "age": 4, "weight_kg": 32.0, "needs_post_op": 1,
                                     "surgery_date": str(today - timedelta(days=4)), "device_id": "CLYVO-COLLAR-01"})
        luna = self._insert("pets", {"tutor_id": rafael, "name": "Luna", "species": "felino", "breed": "SRD (sem raça definida)",
                                     "age": 2, "weight_kg": 3.8, "needs_post_op": 1,
                                     "surgery_date": str(today - timedelta(days=1)), "device_id": "CLYVO-COLLAR-02"})
        bob = self._insert("pets", {"tutor_id": helena, "name": "Bob", "species": "canino", "breed": "Beagle",
                                    "age": 12, "weight_kg": 14.5, "needs_post_op": 0,
                                    "surgery_date": None, "device_id": "CLYVO-COLLAR-03"})

        records = [
            (thor, today - timedelta(days=4), "Cirurgia ortopédica de osteossíntese femoral",
             "Fratura completa de fêmur direito tratada com placa e parafusos",
             "Meloxicam 0,1 mg/kg SID por 7 dias, dipirona 25 mg/kg TID por 5 dias, repouso absoluto por 6 semanas e colar elizabetano",
             "Dra. Camila Torres - CRMV/SP 38421"),
            (thor, today - timedelta(days=120), "Consulta de rotina e vacinação",
             "Paciente hígido", "Vacina polivalente V10 e antirrábica", "Dr. André Lima - CRMV/SP 40110"),
            (luna, today - timedelta(days=1), "Ovariosalpingohisterectomia (castração eletiva)",
             "Procedimento eletivo sem intercorrências; recuperação anestésica lenta",
             "Meloxicam 0,05 mg/kg SID por 3 dias, roupa cirúrgica por 10 dias e restrição de saltos",
             "Dra. Camila Torres - CRMV/SP 38421"),
            (bob, today - timedelta(days=30), "Consulta cardiológica de acompanhamento",
             "Doença valvar mitral degenerativa estágio B2",
             "Pimobendan 0,25 mg/kg BID contínuo e controle de frequência respiratória em repouso",
             "Dr. Paulo Mendes - CRMV/SP 29877"),
        ]
        for pet_id, date, desc, diag, treat, vet in records:
            self._insert("medical_records", {"pet_id": pet_id, "record_date": str(date), "description": desc,
                                             "diagnosis": diag, "treatment": treat, "veterinarian": vet})

        # Histórico de leituras estáveis das últimas 2 horas para os gráficos começarem preenchidos
        now = utcnow()
        baselines = {thor: (38.6, 96), luna: (38.7, 165), bob: (38.4, 112)}
        for pet_id, (temp, hr) in baselines.items():
            for i in range(24, 0, -1):
                wobble = ((i * 7) % 5 - 2) / 10
                self._insert("telemetry", {
                    "pet_id": pet_id, "device_id": None, "temperature": round(temp + wobble / 2, 1),
                    "heart_rate": int(hr + wobble * 10), "movement_level": "REPOUSO", "emergency": 0,
                    "risk_level": 0, "risk_label": "ESTÁVEL", "confidence": 0.97,
                    "probabilities": {"ESTÁVEL": 0.97, "ATENÇÃO": 0.03, "CRÍTICO": 0.0}, "anomalies": [],
                    "safety_override": None, "created_at": iso(now - timedelta(minutes=5 * i)),
                })

    # ------------------------------------------------------------------ pets
    def _enrich_pet(self, pet: dict | None) -> dict | None:
        if pet and pet.get("surgery_date"):
            surgery = datetime.fromisoformat(pet["surgery_date"]).date()
            pet["days_post_op"] = (utcnow().date() - surgery).days
        elif pet:
            pet["days_post_op"] = 0
        if pet:
            pet["needs_post_op"] = bool(pet["needs_post_op"])
        return pet

    def list_pets(self) -> list:
        rows = self._all("SELECT p.*, t.name AS tutor_name, t.phone AS tutor_phone FROM pets p JOIN tutors t ON t.id = p.tutor_id ORDER BY p.id")
        return [self._enrich_pet(r) for r in rows]

    def get_pet(self, pet_id: int) -> dict | None:
        return self._enrich_pet(self._one(
            "SELECT p.*, t.name AS tutor_name, t.phone AS tutor_phone FROM pets p JOIN tutors t ON t.id = p.tutor_id WHERE p.id = ?", (pet_id,)))

    def get_pet_by_device(self, device_id: str) -> dict | None:
        row = self._one("SELECT id FROM pets WHERE device_id = ?", (device_id,))
        return self.get_pet(row["id"]) if row else None

    def get_records(self, pet_id: int) -> list:
        return self._all("SELECT * FROM medical_records WHERE pet_id = ? ORDER BY record_date DESC", (pet_id,))

    # ------------------------------------------------------------- telemetry
    def add_telemetry(self, data: dict) -> int:
        data = {**data, "created_at": data.get("created_at") or iso(utcnow())}
        return self._insert("telemetry", data)

    def get_telemetry(self, pet_id: int, limit: int = 60) -> list:
        rows = self._all("SELECT * FROM telemetry WHERE pet_id = ? ORDER BY id DESC LIMIT ?", (pet_id, limit))
        return list(reversed(rows))

    def get_telemetry_since(self, pet_id: int, since: datetime) -> list:
        return self._all("SELECT * FROM telemetry WHERE pet_id = ? AND created_at >= ? ORDER BY id", (pet_id, iso(since)))

    def get_telemetry_by_id(self, telemetry_id: int) -> dict | None:
        return self._one("SELECT * FROM telemetry WHERE id = ?", (telemetry_id,))

    def latest_telemetry(self, pet_id: int) -> dict | None:
        return self._one("SELECT * FROM telemetry WHERE pet_id = ? ORDER BY id DESC LIMIT 1", (pet_id,))

    # ---------------------------------------------------------------- alerts
    def add_alert(self, data: dict) -> int:
        return self._insert("alerts", {**data, "created_at": iso(utcnow())})

    def get_alert(self, alert_id: int) -> dict | None:
        return self._one("SELECT * FROM alerts WHERE id = ?", (alert_id,))

    def list_alerts(self, pet_id: int | None = None, limit: int = 50) -> list:
        if pet_id:
            return self._all("SELECT * FROM alerts WHERE pet_id = ? ORDER BY id DESC LIMIT ?", (pet_id, limit))
        return self._all("SELECT a.*, p.name AS pet_name FROM alerts a JOIN pets p ON p.id = a.pet_id ORDER BY a.id DESC LIMIT ?", (limit,))

    def last_alert(self, pet_id: int, risk_level: int) -> dict | None:
        return self._one("SELECT * FROM alerts WHERE pet_id = ? AND risk_level = ? ORDER BY id DESC LIMIT 1", (pet_id, risk_level))

    def acknowledge_alert(self, alert_id: int) -> dict | None:
        with self._conn() as conn:
            conn.execute("UPDATE alerts SET status = 'EM ATENDIMENTO', acknowledged_at = ? WHERE id = ?", (iso(utcnow()), alert_id))
        return self.get_alert(alert_id)

    # ------------------------------------------------------------------ chat
    def add_chat(self, pet_id: int, role: str, content: str, llm_mode: str | None = None) -> int:
        return self._insert("chat_messages", {"pet_id": pet_id, "role": role, "content": content,
                                              "llm_mode": llm_mode, "created_at": iso(utcnow())})

    def get_chat(self, pet_id: int, limit: int = 30) -> list:
        rows = self._all("SELECT * FROM chat_messages WHERE pet_id = ? ORDER BY id DESC LIMIT ?", (pet_id, limit))
        return list(reversed(rows))

    # --------------------------------------------------------- notifications
    def add_notification(self, data: dict) -> int:
        return self._insert("notifications", {**data, "created_at": iso(utcnow())})

    def list_notifications(self, limit: int = 30) -> list:
        return self._all("SELECT n.*, p.name AS pet_name FROM notifications n JOIN pets p ON p.id = n.pet_id ORDER BY n.id DESC LIMIT ?", (limit,))
