import asyncpg

from app.repositories import eventos_alarmas, zonas
from app.ws.manager import manager


class ZonaNoEncontrada(Exception):
    pass


async def cambiar_armado(pool: asyncpg.Pool, cliente_id: int, usuario_id: int,
                         zona_id: int, armar: bool) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            zona = await zonas.get_para_actualizar(conn, cliente_id, zona_id)
            if zona is None:
                raise ZonaNoEncontrada()
            if zona["armada"] == armar:
                return                               # ya estaba así: no hay evento ni aviso
            await zonas.set_armada(conn, cliente_id, zona_id, armar)
            await eventos_alarmas.insert_cambio_armado(conn, cliente_id, zona_id, armar, usuario_id)
        # Ya hubo COMMIT: recién ahora avisamos a las placas.
        destinos = await zonas.controladores_de_zona(conn, cliente_id, zona_id)

    for controlador_id in destinos:
        await manager.enviar_config(pool, controlador_id)
