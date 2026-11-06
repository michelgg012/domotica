import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.db import get_pool
from app.core.security import hash_token
from app.repositories import controladores
from app.schemas.device import message_adapter
from app.services.ingest import IngestError, handle_message
from app.ws.manager import manager
log = logging.getLogger(__name__)
router = APIRouter()


def _token_de_header(websocket: WebSocket) -> str:
    """Lee 'Authorization: Bearer <token>'. Devuelve "" si no viene o tiene otro formato."""
    esquema, _, token = websocket.headers.get(
        "authorization", "").partition(" ")
    print(esquema, token)
    return token.strip() if esquema.lower() == "bearer" else ""


@router.websocket("/ws/device")
async def device_ws(websocket: WebSocket, token_url: str | None = Query(None, alias="token")):
    pool = get_pool()

    # 1) Autenticar ANTES de aceptar. De acá salen el controlador y SU cliente.
    # TEMPORAL: si no viene el header, se acepta ?token= en la URL. Borrar al pasar al header.
    token = _token_de_header(websocket) or (token_url or "").strip()
    print('token', token)
    ctrl = None
    if token:
        async with pool.acquire() as conn:
            ctrl = await controladores.get_activo_por_token(conn, hash_token(token))
            if ctrl is not None:
                await controladores.touch_ultima_conexion(conn, ctrl["cliente_id"], ctrl["id"])
    if ctrl is None:
        log.warning("Conexión rechazada desde %s", websocket.client)
        await websocket.close(code=1008)  # policy violation
        return

    cliente_id, controlador_id = ctrl["cliente_id"], ctrl["id"]
    await websocket.accept()
    conexion = await manager.registrar(controlador_id, websocket, cliente_id)
    log.info("Conectado: %s (cliente=%s, id=%s)",
             ctrl["nombre"], cliente_id, controlador_id)

    try:
        # 2) Enviar la configuración
        response = await manager.enviar_config(pool, controlador_id)
        print("response", response)
        # 3) Recibir mensajes mientras la placa esté conectada
        while True:
            raw = await websocket.receive_text()
            try:
                msg = message_adapter.validate_json(raw)
                print("Mensaje recibido:", msg)
                await handle_message(pool, cliente_id, controlador_id, msg)
                respuesta = {"type": "ack", "ok": True}
            except ValidationError as e:
                errores = e.errors(include_url=False,
                                   include_context=False, include_input=False)
                respuesta = {"type": "ack", "ok": False, "error": errores}
            except IngestError as e:
                respuesta = {"type": "ack", "ok": False, "error": str(e)}
            await manager.enviar(conexion, respuesta)
    except WebSocketDisconnect:
        log.info("Desconectado: %s", ctrl["nombre"])
    except Exception:
        log.exception("Error con %s", ctrl["nombre"])
        try:
            await websocket.close(code=1011)  # error interno
        except Exception:
            pass
    finally:
        manager.quitar(controlador_id, conexion)
