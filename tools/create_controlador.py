"""Alta de un controlador (placa ESP32) para un cliente. Muestra el token UNA sola vez.
Uso:  python -m tools.create_controlador 1 AA:BB:CC:DD:EE:01 "Tablero Depósito" --modelo ESP32-DevKit --conexion Wi-Fi"""
import argparse
import asyncio

import asyncpg

from app.core.config import settings
from app.core.security import generate_token, hash_token
from app.repositories import controladores


async def main(args: argparse.Namespace) -> None:
    token = generate_token()
    conn = await asyncpg.connect(settings.database_url)
    try:
        nuevo_id = await controladores.create(
            conn, args.cliente_id, args.mac, args.nombre, hash_token(token), args.modelo, args.conexion
        )
    finally:
        await conn.close()
    print(f"Controlador creado: id={nuevo_id} cliente={args.cliente_id} nombre={args.nombre}")
    print(f"TOKEN (guardalo, no se vuelve a mostrar): {token}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alta de controlador ESP32")
    parser.add_argument("cliente_id", type=int)
    parser.add_argument("mac", help="ej: AA:BB:CC:DD:EE:FF")
    parser.add_argument("nombre")
    parser.add_argument("--modelo")
    parser.add_argument("--conexion", choices=["Ethernet", "Wi-Fi"])
    asyncio.run(main(parser.parse_args()))