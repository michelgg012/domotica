import asyncpg


async def list_componentes(conn: asyncpg.Connection, cliente_id: int, controlador_id: int):
    return await conn.fetch(
        """
        SELECT c.id, c.zona_id, c.pin_esp32, c.funcion, t.metodo_lectura
        FROM componentes c
        JOIN tipos_dispositivos t ON t.id = c.tipo_dispositivo_id
        WHERE c.cliente_id = $1 AND c.controlador_id = $2 AND c.activo
        ORDER BY c.id
        """,
        cliente_id, controlador_id,
    )


async def list_zonas(conn: asyncpg.Connection, cliente_id: int, controlador_id: int):

    return await conn.fetch(
        """
        SELECT z.id, z.armada, z.luz_apagado_s, z.sirena_duracion_s
        FROM zonas z
        WHERE z.cliente_id = $1 AND z.activo
          AND z.id IN (
              SELECT zona_id FROM componentes
              WHERE cliente_id = $1 AND controlador_id = $2 AND activo
          )
        ORDER BY z.id
        """,
        cliente_id, controlador_id,
    )