import asyncpg


async def list_activas(conn: asyncpg.Connection, cliente_id: int):
    return await conn.fetch(
        """
        SELECT id, nombre, armada, luz_apagado_s, sirena_duracion_s
        FROM domotica.zonas
        WHERE cliente_id = $1 AND activo
        ORDER BY nombre
        """,
        cliente_id,
    )


async def existe(conn: asyncpg.Connection, cliente_id: int, zona_id: int) -> bool:
    return await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM domotica.zonas WHERE id = $1 AND cliente_id = $2 AND activo)",
        zona_id, cliente_id,
    )


async def get_para_actualizar(conn: asyncpg.Connection, cliente_id: int, zona_id: int):
    """FOR UPDATE bloquea la fila hasta el COMMIT: dos admins no pueden pisarse."""
    return await conn.fetchrow(
        "SELECT id, armada FROM domotica.zonas WHERE id = $1 AND cliente_id = $2 AND activo FOR UPDATE",
        zona_id, cliente_id,
    )


async def set_armada(conn: asyncpg.Connection, cliente_id: int, zona_id: int, armada: bool) -> None:
    await conn.execute(
        "UPDATE domotica.zonas SET armada = $3, actualizado_en = now() WHERE id = $1 AND cliente_id = $2",
        zona_id, cliente_id, armada,
    )


async def controladores_de_zona(conn: asyncpg.Connection, cliente_id: int, zona_id: int) -> list[int]:
    filas = await conn.fetch(
        """
        SELECT DISTINCT controlador_id
        FROM domotica.componentes
        WHERE cliente_id = $1 AND zona_id = $2 AND activo
        """,
        cliente_id, zona_id,
    )
    return [f["controlador_id"] for f in filas]