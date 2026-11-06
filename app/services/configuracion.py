import asyncpg

from app.repositories import configuracion


async def build_config(pool: asyncpg.Pool, cliente_id: int, controlador_id: int) -> dict:
    async with pool.acquire() as conn:
        zonas = await configuracion.list_zonas(conn, cliente_id, controlador_id)
        componentes = await configuracion.list_componentes(conn, cliente_id, controlador_id)
    return {
        "type": "config",
        "zonas": [dict(r) for r in zonas],
        "componentes": [dict(r) for r in componentes],
    }