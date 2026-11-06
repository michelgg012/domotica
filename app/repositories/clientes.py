import asyncpg


async def create(conn: asyncpg.Connection, nombre: str) -> int:
    return await conn.fetchval("INSERT INTO domotica.clientes (nombre) VALUES ($1) RETURNING id", nombre)

