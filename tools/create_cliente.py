"""Alta de un cliente (tenant). Uso:  python -m tools.create_cliente "Lo De Mario" """
import argparse
import asyncio

import asyncpg

from app.core.config import settings
from app.repositories import clientes


async def main(args: argparse.Namespace) -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        nuevo_id = await clientes.create(conn, args.nombre)
    finally:
        await conn.close()
    print(f"Cliente creado: id={nuevo_id} nombre={args.nombre}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alta de cliente")
    parser.add_argument("nombre")
    asyncio.run(main(parser.parse_args()))