from datetime import datetime
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, TypeAdapter
# BaseModel: define la forma de un mensaje
# Field: agrega reglas o metadatos a un campo
# TypeAdapter: valida algo que NO es un BaseModel


class _Base(BaseModel):
    # hora del dispositivo. Si no viene, se usa la del servidor.
    ts: datetime | None = None


class LecturaMsg(_Base):
    type: Literal["lectura"]
    componente_id: int
    valor: Literal[0, 1]  # fase 1: todo es binario (sensor o rele)


class AlarmaMsg(_Base):
    type: Literal["alarma"]
    zona_id: int
    componente_id: int
    valor: Literal[0, 1]


DeviceMessage = Annotated[
    Union[LecturaMsg, AlarmaMsg],
    Field(discriminator="type")
]

message_adapter = TypeAdapter(DeviceMessage)
