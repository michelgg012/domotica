
import asyncpg


async def get_activo_por_email(conn: asyncpg.Connection, email: str):
    return await conn.fetchrow(
        """
        SELECT u.id, u.password_hash
        FROM domotica.usuarios u
        LEFT JOIN domotica.clientes c ON c.id = u.cliente_id
        WHERE lower(u.email) = lower($1) AND u.activo AND (u.cliente_id IS NULL OR c.activo)
        """,
        email,
    )


async def get_activo(conn: asyncpg.Connection, usuario_id: int):
    return await conn.fetchrow(
        """
        SELECT u.id, u.cliente_id, u.rol
        FROM domotica.usuarios u
        LEFT JOIN domotica.clientes c ON c.id = u.cliente_id
        WHERE u.id = $1 AND u.activo AND (u.cliente_id IS NULL OR c.activo)
        """,
        usuario_id,
    )


async def create(conn: asyncpg.Connection, cliente_id: int | None, email: str,
                 password_hash: str, rol: str) -> int:
    return await conn.fetchval(
        """
        INSERT INTO domotica.usuarios (cliente_id, email, password_hash, rol)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        cliente_id, email, password_hash, rol,
    )
