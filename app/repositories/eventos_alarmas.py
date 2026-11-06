from datetime import datetime

import asyncpg


async def insert_disparo(conn: asyncpg.Connection, cliente_id: int, controlador_id: int,
                         zona_id: int, componente_id: int, ts: datetime | None) -> bool:
    #Solo si el sensor es un PIR activo de esta placa, de este cliente y de esa zona
    nuevo_id = await conn.fetchval(
        """
        INSERT INTO eventos_alarma (cliente_id, zona_id, tipo, componente_id, fecha_hora)
        SELECT c.cliente_id, c.zona_id, 'DISPARO', c.id, COALESCE($5::timestamptz, now())
        FROM domotica.componentes c
        WHERE c.id = $4 AND c.zona_id = $3 AND c.cliente_id = $1 AND c.controlador_id = $2
          AND c.activo AND c.funcion = 'SENSOR_MOVIMIENTO'
        RETURNING id
        """,
        cliente_id, controlador_id, zona_id, componente_id, ts,
    )
    return nuevo_id is not None


async def insert_cambio_armado(conn: asyncpg.Connection, cliente_id: int, zona_id: int,
                               armada: bool, usuario_id: int) -> None:
    await conn.execute(
        """
        INSERT INTO domotica.eventos_alarma (cliente_id, zona_id, tipo, usuario_id)
        VALUES ($1, $2, $3, $4)
        """,
        cliente_id, zona_id, "ARMADO" if armada else "DESARMADO", usuario_id,
    )


async def list_eventos(conn: asyncpg.Connection, cliente_id: int, zona_id: int | None,
                       desde: datetime | None, hasta: datetime | None, limite: int):
    # Cada filtro opcional se "apaga" cuando su parámetro llega como NULL.
    return await conn.fetch(
        """
        SELECT e.id, e.zona_id, z.nombre AS zona, e.tipo, e.componente_id, e.usuario_id, e.fecha_hora
        FROM domotica.eventos_alarma e
        JOIN domotica.zonas z ON z.id = e.zona_id AND z.cliente_id = e.cliente_id
        WHERE e.cliente_id = $1
          AND ($2::int IS NULL OR e.zona_id = $2)
          AND ($3::timestamptz IS NULL OR e.fecha_hora >= $3)
          AND ($4::timestamptz IS NULL OR e.fecha_hora < $4)
        ORDER BY e.fecha_hora DESC
        LIMIT $5
        """,
        cliente_id, zona_id, desde, hasta, limite,
    )