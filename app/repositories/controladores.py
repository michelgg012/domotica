import asyncpg


async def get_activo_por_token(conn: asyncpg.Connection, token_hash: str):
    return await conn.fetchrow(
        """
        SELECT ctl.id, ctl.cliente_id, ctl.nombre
        FROM domotica.controladores ctl
        JOIN domotica.clientes c ON c.id = ctl.cliente_id
        WHERE ctl.token_hash = $1 AND ctl.activo AND c.activo
        """,
        token_hash,
    )


async def touch_ultima_conexion(conn: asyncpg.Connection, cliente_id: int, controlador_id: int) -> None:
    await conn.execute(
        "UPDATE domotica.controladores SET ultima_conexion = now() WHERE id = $1 AND cliente_id = $2",
        controlador_id, cliente_id,
    ) 


async def create(conn: asyncpg.Connection, cliente_id: int, mac: str, nombre: str, token_hash: str,
                 modelo: str | None, tipo_conexion: str | None) -> int:
    return await conn.fetchval(
        """
        INSERT INTO domotica.controladores (cliente_id, mac_address, nombre, token_hash, modelo, tipo_conexion)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        cliente_id, mac, nombre, token_hash, modelo, tipo_conexion,
    )

