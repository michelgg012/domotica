"""Alta de un usuario. La contraseña se pide por consola (no queda en el historial).
Uso:  python -m tools.create_usuario admin@lodemario.com admin --cliente-id 1
      python -m tools.create_usuario vos@mail.com superadmin"""
import argparse
import asyncio
import getpass

import asyncpg

from app.core.config import settings
from app.core.security import hash_password
from app.repositories import usuarios


async def main(args: argparse.Namespace) -> None:
    if (args.rol == "superadmin") != (args.cliente_id is None):
        raise SystemExit("superadmin va SIN --cliente-id; admin y lector, CON --cliente-id")
    password = getpass.getpass("Contraseña: ")
    if len(password) < 8:
        raise SystemExit("La contraseña debe tener al menos 8 caracteres")
    conn = await asyncpg.connect(settings.database_url)
    try:
        nuevo_id = await usuarios.create(conn, args.cliente_id, args.email, hash_password(password), args.rol)
    finally:
        await conn.close()
    print(f"Usuario creado: id={nuevo_id} email={args.email} rol={args.rol}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alta de usuario")
    parser.add_argument("email")
    parser.add_argument("rol", choices=["superadmin", "admin", "lector"])
    parser.add_argument("--cliente-id", type=int)
    asyncio.run(main(parser.parse_args()))