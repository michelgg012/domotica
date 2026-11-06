/*
  09-domotica · Prueba configuracion basica  · WT32-ETH01
  Conecta por Ethernet al servidor y envía una lectura cuando un PIR se activa.

  Core:      esp32 by Espressif 3.x
  Libreria:  WebSockets (Markus Sattler)
  Archivos:  prueba_basica.ino + secrets.h en la misma carpeta
*/
#include <ETH.h>
#include <WebSocketsClient.h>
#include "secrets.h"   // SERVER_IP, SERVER_PORT, DEVICE_TOKEN, OTROS..

// ───── Ethernet WT32-ETH01 (LAN8720) ─────
#define ETH_PHY_ADDR   1
#define ETH_MDC_PIN    23
#define ETH_MDIO_PIN   18
#define ETH_POWER_PIN  16

// ───── PIR ─────
const uint8_t PIR_1_PIN = 35; // 35
const uint8_t PIR_2_PIN = 36; // 36
const int     PIR_1_ID  = 5;   // componentes.id del PIR 1 en la DB
const int     PIR_2_ID  = 4;   // componentes.id del PIR 2 en la DB

WebSocketsClient ws;
volatile bool ethListo = false;   //  evento de red
bool wsIniciado  = false;
bool wsConectado = false;
bool pirAnterior[2] = {false, false};

// Enviar  lectura al servidor: {"type":"lectura","componente_id":X,"valor":Y}
// Formato para enviar mensajes 
void enviarLectura(int componenteId, int valor) {
  if (!wsConectado) return;
  String msg = String("{\"type\":\"lectura\",\"componente_id\":") + componenteId +
               ",\"valor\":" + valor + "}";
  ws.sendTXT(msg);
  Serial.printf("[WS] -> %s\n", msg.c_str());
}

// cambiar de estado: 0 -> 1 
void revisarPIR() {
  static unsigned long ultima = 0;
  if (millis() - ultima < 50) return;   // lee cada 50 ms
  ultima = millis();

  const uint8_t pines[2] = {PIR_1_PIN, PIR_2_PIN};
  const int     ids[2]   = {PIR_1_ID,  PIR_2_ID};

  for (int i = 0; i < 2; i++) {
    bool ahora = digitalRead(pines[i]);
    if (ahora != pirAnterior[i]) {
      Serial.printf("[PIR] %d %s\n", ids[i], ahora ? "activado" : "apagado");
      enviarLectura(ids[i], ahora ? 1 : 0);
    }
    pirAnterior[i] = ahora;
  }
}

void onWsEvento(WStype_t tipo, uint8_t* payload, size_t length) {
  switch (tipo) {
    case WStype_CONNECTED:
      wsConectado = true;
      Serial.println("[WS] Conectado");
      break;
    case WStype_DISCONNECTED:
      wsConectado = false;
      Serial.println("[WS] Desconectado");
      break;
    case WStype_TEXT:
      Serial.printf("[WS] <- %s\n", payload);   // ack u otros mensajes del servidor
      break;
    default:
      break;
  }
}

void onRedEvento(arduino_event_id_t evento, arduino_event_info_t info) {
  switch (evento) {
    case ARDUINO_EVENT_ETH_START:
      ETH.setHostname("wt32-domotica");
      break;
    case ARDUINO_EVENT_ETH_GOT_IP:
      Serial.print("[ETH] IP: ");
      Serial.println(ETH.localIP());
      ethListo = true;
      break;
    case ARDUINO_EVENT_ETH_DISCONNECTED:
    case ARDUINO_EVENT_ETH_STOP:
      ethListo = false;
      wsConectado = false;
      Serial.println("[ETH] Sin red");
      break;
    default:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n[BOOT] Prueba básica");

  pinMode(PIR_1_PIN, INPUT);
  pinMode(PIR_2_PIN, INPUT);

  Network.onEvent(onRedEvento);
  ETH.begin(ETH_PHY_LAN8720, ETH_PHY_ADDR, ETH_MDC_PIN, ETH_MDIO_PIN,
            ETH_POWER_PIN, ETH_CLOCK_GPIO0_IN);
}

void loop() {
  // El WebSocket se arranca desde loop, no desde el evento de red.
  if (ethListo && !wsIniciado) {
    ws.begin(SERVER_IP, SERVER_PORT, "/ws/device");
    ws.setExtraHeaders("Authorization: Bearer " DEVICE_TOKEN);
    ws.onEvent(onWsEvento);
    ws.setReconnectInterval(5000);
    wsIniciado = true;
  }

  ws.loop();
  revisarPIR();
}
