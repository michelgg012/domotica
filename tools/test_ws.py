# Prueba mínima de conexión ESP32 <-> servidor. SIN autenticación: solo para la LAN.
# Ejecutar: uvicorn test_ws:app --host 0.0.0.0 --port 8000
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


@app.websocket("/ws/test")
async def ws_test(websocket: WebSocket):
    await websocket.accept()
    print(f"Conectado: {websocket.client.host}")
    try:
        while True:
            msg = await websocket.receive_text()
            print(f"Recibido: {msg}")
            await websocket.send_text(f"eco: {msg}")
    except WebSocketDisconnect:
        print("Desconectado")