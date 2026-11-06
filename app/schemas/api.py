from datetime import datetime
from pydantic import BaseModel  # BaseModel: define la forma de un mensaje


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SignupIn(BaseModel):
    email: str
    password: str
    rol: str


class SignupOut(BaseModel):
    email: str


class ZonaOut(BaseModel):
    id: int
    nombre: str
    armada: bool
    luz_apagado_s: int
    sirena_duracion_s: int


class ZonaEstadoOut(BaseModel):
    id: int
    armada: bool


class EventoOut(BaseModel):
    id: int
    zona_id: int
    zona: str
    tipo: str
    componente_id: int | None
    usuario_id: int | None
    fecha_hora: datetime
