import asyncpg

from app.core.config import settings

_pool: asyncpg.Pool | None = None


# -> Sirve para  anotar el valor que va a obtener la funcion
async def open_pool() -> None:
    # Con blobal modificas la variable del modulo, no creas otra 
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        server_settings={"search_path": "domotica"},
    )

async def close_pool() -> None:
    if _pool is not None:
        await _pool.close()
    
def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("El pool de DB no esta inicializado")
    return _pool