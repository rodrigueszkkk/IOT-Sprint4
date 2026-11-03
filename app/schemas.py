"""Contratos de entrada da API.

O pacote de telemetria aceita tanto o formato da API (inglês) quanto o JSON emitido pelo firmware
da coleira no Wokwi (smart_collar.ino: temperatura, bpm, movimento, sos), para que a ponte serial
possa repassar a linha do Monitor Serial sem transformação.
"""
from pydantic import AliasChoices, BaseModel, Field, field_validator


class TelemetryIn(BaseModel):
    device_id: str | None = Field(None, validation_alias=AliasChoices("device_id", "deviceId"))
    pet_id: int | None = Field(None, validation_alias=AliasChoices("pet_id", "petId"))
    temperature: float = Field(..., ge=30, le=45, validation_alias=AliasChoices("temperature", "temperatura"))
    heart_rate: int = Field(..., ge=20, le=300, validation_alias=AliasChoices("heart_rate", "heartRateBpm", "bpm"))
    movement_level: str = Field("REPOUSO", validation_alias=AliasChoices("movement_level", "movementLevel", "movimento"))
    emergency: bool = Field(False, validation_alias=AliasChoices("emergency", "emergencyPressed", "sos"))
    timestamp: str | None = None

    @field_validator("movement_level", mode="before")
    @classmethod
    def normalize_movement(cls, value):
        # O firmware envia movimento como booleano (botão de atividade pressionado = ALTO)
        if isinstance(value, bool):
            return "ALTO" if value else "REPOUSO"
        value = str(value).upper()
        if value not in ("REPOUSO", "MODERADO", "ALTO"):
            raise ValueError("movement_level deve ser REPOUSO, MODERADO ou ALTO")
        return value

    def to_reading(self) -> dict:
        return {"device_id": self.device_id, "temperature": round(self.temperature, 1), "heart_rate": self.heart_rate,
                "movement_level": self.movement_level, "emergency": self.emergency, "timestamp": self.timestamp}


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
