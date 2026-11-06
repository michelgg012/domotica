import asyncpg

from app.repositories import controladores, eventos_alarmas, historial
from app.schemas.device import AlarmaMsg, LecturaMsg


class IngestError(Exception):
     """Error de negocio: el mensaje es válido pero no se puede guardar."""

async def handle_message(pool: asyncpg.Pool, cliente_id: int, controlador_id: int, msg)-> None:
    async with pool.acquire() as conn:
         async with conn.transaction():
              match msg: 
                   case LecturaMsg():
                        ok = await historial.insert_lectura(
                             conn, cliente_id, controlador_id, msg.componente_id, msg.valor, msg.ts
                        )
                        if not ok:
                             raise IngestError(f"componente {msg.componente_id} inexistente, inactivo o ajeno")
                   case AlarmaMsg():
                        ok= await eventos_alarmas.insert_disparo(
                             conn, cliente_id, controlador_id, msg.zona_id, msg.componente_id, msg.ts)
                        if not ok:
                             raise IngestError(
                                  f"el componente {msg.componente_id} no es un PIR activo de la zona {msg.zona_id}"
                             ) 
              await   controladores.touch_ultima_conexion(conn, cliente_id, controlador_id)
                        
