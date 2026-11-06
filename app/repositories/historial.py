from datetime import datetime

import asyncpg


async def insert_lectura(conn: asyncpg.Connection, cliente_id: int, controlador_id: int,
                         componente_id: int, valor: int, ts: datetime | None) -> bool:
    #Inserta SOLO si el componente es de esta placa, de este cliente y está activo.
    nuevo_id = await conn.fetchval(
        """
        INSERT INTO historial_datos (cliente_id, componente_id, valor, fecha_hora)
        SELECT c.cliente_id, c.id, $4::numeric, COALESCE($5::timestamptz, now())
        FROM domotica.componentes c
        WHERE c.id = $3 AND c.cliente_id = $1 AND c.controlador_id = $2 AND c.activo
        RETURNING id
        """,
        cliente_id, controlador_id, componente_id, valor, ts,
    )
    return nuevo_id is not None