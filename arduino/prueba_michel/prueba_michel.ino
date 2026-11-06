/*
  09-domotica · Firmware Fase 1 · WT32-ETH01 (ESP32 + LAN8720)
  Implementa las tareas G1..G5 de tasks-fase1.md.

  Core:        esp32 by Espressif 3.x
  Librerías:   WebSockets (Markus Sattler)  ·  ArduinoJson 7.x (Benoit Blanchon)

  IMPORTANTE: los pines NO están fijos en el código. Llegan del servidor en el
  mensaje "config" (tabla componentes.pin_esp32). Sin config, la placa no hace nada.
*/
#include <ETH.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "secrets.h"   // SERVER_IP, SERVER_PORT, DEVICE_TOKEN  (NO se commitea)

// ───────────── Ethernet WT32-ETH01 (LAN8720) ─────────────
// El WT32-ETH01 usa un oscilador externo de 50 MHz que entra por GPIO0,
// habilitado por GPIO16. Por eso el clock es GPIO0_IN (no GPIO17_OUT).
#define WT32_PHY_ADDR  1
#define WT32_MDC       23
#define WT32_MDIO      18
#define WT32_POWER     16
#define WT32_CLK       ETH_CLOCK_GPIO0_IN

// ───────────── Parámetros ─────────────
const char*  WS_PATH        = "/ws/device";
const char*  NTP_SERVER     = "pool.ntp.org";
const long   GMT_OFFSET_S   = -10800;        // UTC-3 (solo para logs; el ts se envía en UTC)

const uint8_t RELE_ON  = HIGH;               // si tu módulo de relé es activo en LOW, invertí estos dos
const uint8_t RELE_OFF = LOW;

const unsigned long PIR_WARMUP_MS    = 60000; // el PIR se ignora los primeros 60 s
const unsigned long LECTURA_CADA_MS  = 50;    // cada cuánto se leen los sensores
const uint8_t       LECTURAS_ESTABLES = 3;    // antirrebote: 3 lecturas iguales seguidas (150 ms)

const int MAX_ZONAS = 8;
const int MAX_COMP  = 16;

// ───────────── Modelo (espejo de la config del servidor) ─────────────
enum Funcion : uint8_t { F_DESCONOCIDA, F_MOVIMIENTO, F_PRESENCIA, F_RELE_LUZ, F_SIRENA };

struct Zona {
  int           id;
  bool          armada;
  uint32_t      luzApagadoMs;
  uint32_t      sirenaMs;
  bool          luzOn;
  bool          timerLuz;      // temporizador de apagado corriendo
  unsigned long luzDesde;
  bool          sirenaOn;
  unsigned long sirenaDesde;
};

struct Componente {
  int      id;
  int      zonaId;
  int      pin;
  Funcion  funcion;
  bool     esSalida;
  uint8_t  estado;      // último estado confirmado (0/1)
  uint8_t  candidato;   // antirrebote
  uint8_t  cuenta;
};

Zona       zonas[MAX_ZONAS];
int        nZonas = 0;
Componente comps[MAX_COMP];
int        nComps = 0;

// ───────────── Estado de red ─────────────
volatile bool ethConectado = false;   // lo escribe el evento de red (otra tarea)
bool wsIniciado   = false;
bool wsConectado  = false;
bool enviarSnapshot = false;          // al conectar: mandar el estado de todo después de la config

WebSocketsClient webSocket;

// ═════════════ Utilidades ═════════════

Funcion parseFuncion(const char* s) {
  if (!s) return F_DESCONOCIDA;
  if (!strcmp(s, "SENSOR_MOVIMIENTO")) return F_MOVIMIENTO;
  if (!strcmp(s, "SENSOR_PRESENCIA"))  return F_PRESENCIA;
  if (!strcmp(s, "RELE_LUZ"))          return F_RELE_LUZ;
  if (!strcmp(s, "SIRENA"))            return F_SIRENA;
  return F_DESCONOCIDA;
}

// Acepta "14", "GPIO14" o "IO14". Devuelve -1 si no es válido.
int parsePin(JsonVariantConst v) {
  if (v.is<int>()) return v.as<int>();
  const char* s = v.as<const char*>();
  if (!s) return -1;
  while (*s && !isdigit((unsigned char)*s)) s++;
  if (!*s) return -1;
  return atoi(s);
}

// Pines que NO se pueden usar en el WT32-ETH01
bool pinProhibido(int pin) {
  if (pin < 0 || pin > 39) return true;
  if (pin >= 6 && pin <= 11) return true;                    // flash interna
  if (pin == 20 || pin == 24 || (pin >= 28 && pin <= 31)) return true;  // no existen
  const int reservados[] = {0, 1, 3, 16, 18, 19, 21, 22, 23, 25, 26, 27}; // Ethernet + Serial0
  for (int r : reservados) if (r == pin) return true;
  return false;
}

Zona* buscarZona(int id) {
  for (int i = 0; i < nZonas; i++) if (zonas[i].id == id) return &zonas[i];
  return nullptr;
}

bool horaSincronizada() { return time(nullptr) > 1700000000; }

// Si no hay hora válida NO se manda ts: el servidor usa su propia hora (now()).
void agregarTs(JsonDocument& d) {
  if (!horaSincronizada()) return;
  time_t t = time(nullptr);
  struct tm tm;
  gmtime_r(&t, &tm);
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
  d["ts"] = String(buf);
}

// ═════════════ Envío al servidor ═════════════

void enviarJson(JsonDocument& d) {
  if (!wsConectado) return;
  String out;
  serializeJson(d, out);
  webSocket.sendTXT(out);
  Serial.printf("[WS] -> %s\n", out.c_str());
}

void enviarLectura(const Componente& c) {
  if (enviarSnapshot) return;   // hay un snapshot pendiente: lo va a incluir
  JsonDocument d;
  d["type"] = "lectura";
  d["componente_id"] = c.id;
  d["valor"] = c.estado;
  agregarTs(d);
  enviarJson(d);
}

void enviarAlarma(int zonaId, int componenteId) {
  JsonDocument d;
  d["type"] = "alarma";
  d["zona_id"] = zonaId;
  d["componente_id"] = componenteId;
  agregarTs(d);
  enviarJson(d);
}

// ═════════════ Salidas (luces y sirena) ═════════════

void escribirSalidas(int zonaId, Funcion f, bool on) {
  for (int i = 0; i < nComps; i++) {
    Componente& c = comps[i];
    if (c.zonaId != zonaId || c.funcion != f) continue;
    digitalWrite(c.pin, on ? RELE_ON : RELE_OFF);
    uint8_t v = on ? 1 : 0;
    if (c.estado != v) { c.estado = v; enviarLectura(c); }
  }
}

void setLuz(Zona& z, bool on) {
  if (z.luzOn == on) return;
  z.luzOn = on;
  escribirSalidas(z.id, F_RELE_LUZ, on);
  Serial.printf("[LUZ] Zona %d -> %s\n", z.id, on ? "ON" : "OFF");
}

void setSirena(Zona& z, bool on) {
  if (z.sirenaOn == on) return;
  z.sirenaOn = on;
  if (on) z.sirenaDesde = millis();
  escribirSalidas(z.id, F_SIRENA, on);
  Serial.printf("[SIRENA] Zona %d -> %s\n", z.id, on ? "ON" : "OFF");
}

// ═════════════ Reglas (G3 luces · G4 alarma) ═════════════

// Luces: cualquier radar de la zona en 1 = hay presencia.
void evaluarPresencia(Zona& z) {
  bool tieneRadar = false, hay = false;
  for (int i = 0; i < nComps; i++) {
    if (comps[i].zonaId == z.id && comps[i].funcion == F_PRESENCIA) {
      tieneRadar = true;
      if (comps[i].estado) hay = true;
    }
  }
  if (!tieneRadar) return;

  if (hay) {                              // 0 -> 1: luz ON y se cancela el temporizador
    z.timerLuz = false;
    setLuz(z, true);
  } else if (z.luzOn && !z.timerLuz) {    // 1 -> 0: arranca el temporizador
    z.timerLuz = true;
    z.luzDesde = millis();
    Serial.printf("[LUZ] Zona %d sin presencia, apaga en %lu s\n", z.id, z.luzApagadoMs / 1000);
  }
}

void onCambioSensor(const Componente& c) {
  Zona* z = buscarZona(c.zonaId);
  if (!z) return;

  if (c.funcion == F_PRESENCIA) {
    evaluarPresencia(*z);
  } else if (c.funcion == F_MOVIMIENTO && c.estado == 1) {
    if (millis() < PIR_WARMUP_MS) {
      Serial.printf("[PIR] %d ignorado (warm-up)\n", c.id);
      return;
    }
    if (z->armada && !z->sirenaOn) {
      setSirena(*z, true);
      enviarAlarma(z->id, c.id);
    }
  }
}

void revisarTemporizadores() {
  unsigned long ahora = millis();
  for (int i = 0; i < nZonas; i++) {
    Zona& z = zonas[i];
    if (z.timerLuz && ahora - z.luzDesde >= z.luzApagadoMs) {
      z.timerLuz = false;
      setLuz(z, false);
    }
    if (z.sirenaOn && ahora - z.sirenaDesde >= z.sirenaMs) {
      setSirena(z, false);
    }
  }
}

// ═════════════ Lectura de sensores (G5) ═════════════

void leerSensores() {
  static unsigned long ultima = 0;
  if (millis() - ultima < LECTURA_CADA_MS) return;
  ultima = millis();

  for (int i = 0; i < nComps; i++) {
    Componente& c = comps[i];
    if (c.esSalida) continue;

    uint8_t v = digitalRead(c.pin) ? 1 : 0;
    if (v == c.estado) { c.candidato = v; c.cuenta = 0; continue; }

    if (v != c.candidato) { c.candidato = v; c.cuenta = 1; }
    else                  { c.cuenta++; }
    if (c.cuenta < LECTURAS_ESTABLES) continue;

    c.estado = v;             // cambio confirmado
    c.cuenta = 0;
    Serial.printf("[SENSOR] %d (pin %d) -> %d\n", c.id, c.pin, v);
    enviarLectura(c);
    onCambioSensor(c);
  }
}

// ═════════════ Config del servidor (G2) ═════════════

void aplicarConfig(JsonDocument& doc) {
  // Copia del estado anterior: en un re-push (armar/desarmar) no se pierde lo que estaba pasando.
  static Zona       zViejas[MAX_ZONAS];
  static Componente cViejos[MAX_COMP];
  int nzv = nZonas, ncv = nComps;
  memcpy(zViejas, zonas, sizeof(zonas));
  memcpy(cViejos, comps, sizeof(comps));

  // ── Zonas ──
  nZonas = 0;
  for (JsonObjectConst zj : doc["zonas"].as<JsonArrayConst>()) {
    if (nZonas >= MAX_ZONAS) { Serial.println("[CFG] Demasiadas zonas, se ignoran las restantes"); break; }
    Zona z = {};
    z.id           = zj["id"] | -1;
    z.armada       = zj["armada"] | false;
    z.luzApagadoMs = (uint32_t)(zj["luz_apagado_s"] | 900) * 1000UL;
    z.sirenaMs     = (uint32_t)(zj["sirena_duracion_s"] | 180) * 1000UL;
    for (int i = 0; i < nzv; i++) {
      if (zViejas[i].id == z.id) {
        z.luzOn = zViejas[i].luzOn;       z.timerLuz = zViejas[i].timerLuz;
        z.luzDesde = zViejas[i].luzDesde; z.sirenaOn = zViejas[i].sirenaOn;
        z.sirenaDesde = zViejas[i].sirenaDesde;
      }
    }
    zonas[nZonas++] = z;
  }

  // ── Componentes ──
  nComps = 0;
  for (JsonObjectConst cj : doc["componentes"].as<JsonArrayConst>()) {
    if (nComps >= MAX_COMP) { Serial.println("[CFG] Demasiados componentes, se ignoran los restantes"); break; }
    Componente c = {};
    c.id      = cj["id"] | -1;
    c.zonaId  = cj["zona_id"] | -1;
    c.pin     = parsePin(cj["pin_esp32"]);
    c.funcion = parseFuncion(cj["funcion"] | "");
    const char* metodo = cj["metodo_lectura"] | "";

    if (pinProhibido(c.pin)) { Serial.printf("[CFG] Componente %d: pin %d no permitido\n", c.id, c.pin); continue; }
    if (c.funcion == F_DESCONOCIDA) { Serial.printf("[CFG] Componente %d: funcion desconocida\n", c.id); continue; }
    if (!buscarZona(c.zonaId)) { Serial.printf("[CFG] Componente %d: zona %d no recibida\n", c.id, c.zonaId); continue; }

    c.esSalida = (c.funcion == F_RELE_LUZ || c.funcion == F_SIRENA);
    if (c.esSalida) {
      if (c.pin >= 34) { Serial.printf("[CFG] Componente %d: GPIO%d es solo entrada\n", c.id, c.pin); continue; }
      pinMode(c.pin, OUTPUT);
    } else {
      bool pullup = !strcmp(metodo, "GPIO_IN_PULLUP");
      if (pullup && c.pin >= 34) Serial.printf("[CFG] Aviso: GPIO%d no tiene pull-up interno\n", c.pin);
      pinMode(c.pin, pullup ? INPUT_PULLUP : INPUT);
    }

    bool conocido = false;
    for (int i = 0; i < ncv; i++) {
      if (cViejos[i].id == c.id && cViejos[i].pin == c.pin) {
        c.estado = cViejos[i].estado; c.candidato = cViejos[i].candidato; c.cuenta = cViejos[i].cuenta;
        conocido = true;
      }
    }
    if (!conocido && !c.esSalida) { c.estado = digitalRead(c.pin) ? 1 : 0; c.candidato = c.estado; }
    comps[nComps++] = c;
  }

  // Salidas que ya no están en la config: se apagan.
  for (int i = 0; i < ncv; i++) {
    if (!cViejos[i].esSalida) continue;
    bool sigue = false;
    for (int j = 0; j < nComps; j++) if (comps[j].esSalida && comps[j].pin == cViejos[i].pin) sigue = true;
    if (!sigue) digitalWrite(cViejos[i].pin, RELE_OFF);
  }

  // Llevar las salidas al estado de su zona y aplicar reglas.
  for (int i = 0; i < nZonas; i++) {
    Zona& z = zonas[i];
    escribirSalidas(z.id, F_RELE_LUZ, z.luzOn);
    escribirSalidas(z.id, F_SIRENA,   z.sirenaOn);
    if (!z.armada && z.sirenaOn) setSirena(z, false);   // zona desarmada: sirena OFF
    evaluarPresencia(z);
  }

  Serial.printf("[CFG] Aplicada: %d zonas, %d componentes\n", nZonas, nComps);

  // Primer config de esta conexión: mandar el estado actual de todo.
  if (enviarSnapshot) {
    enviarSnapshot = false;
    for (int i = 0; i < nComps; i++) enviarLectura(comps[i]);
  }
}

// ═════════════ WebSocket (G1) ═════════════

void procesarMensaje(uint8_t* payload, size_t length) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) { Serial.printf("[WS] JSON invalido: %s\n", err.c_str()); return; }

  const char* tipo = doc["type"] | "";
  if (!strcmp(tipo, "config")) {
    aplicarConfig(doc);
  } else if (!strcmp(tipo, "ack")) {
    if (!(doc["ok"] | false)) {
      String e;
      serializeJson(doc["error"], e);
      Serial.printf("[ACK] Rechazado por el servidor: %s\n", e.c_str());
    }
  } else {
    Serial.printf("[WS] type desconocido, se ignora: %s\n", tipo);
  }
}

void webSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.printf("[WS] Conectado a %s:%d%s\n", SERVER_IP, SERVER_PORT, WS_PATH);
      wsConectado = true;
      enviarSnapshot = true;          // se manda después de recibir la config
      break;
    case WStype_DISCONNECTED:
      if (wsConectado) Serial.println("[WS] Desconectado (reintenta cada 5 s)");
      wsConectado = false;
      break;
    case WStype_TEXT:
      procesarMensaje(payload, length);
      break;
    case WStype_ERROR:
      Serial.println("[WS] Error");
      break;
    default:
      break;
  }
}

void iniciarWebSocket() {
  configTime(GMT_OFFSET_S, 0, NTP_SERVER);
  webSocket.begin(SERVER_IP, SERVER_PORT, WS_PATH);
  webSocket.setExtraHeaders("Authorization: Bearer " DEVICE_TOKEN);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(15000, 3000, 2);   // detecta un cable cortado en ~20 s
  wsIniciado = true;
}

// ═════════════ Ethernet ═════════════

void onRedEvento(arduino_event_id_t event, arduino_event_info_t info) {
  switch (event) {
    case ARDUINO_EVENT_ETH_START:
      ETH.setHostname("wt32-eth01-domotica");
      break;
    case ARDUINO_EVENT_ETH_CONNECTED:
      Serial.println("[ETH] Cable conectado");
      break;
    case ARDUINO_EVENT_ETH_GOT_IP:
      Serial.print("[ETH] IP: ");
      Serial.println(ETH.localIP());
      ethConectado = true;
      break;
    case ARDUINO_EVENT_ETH_LOST_IP:
    case ARDUINO_EVENT_ETH_DISCONNECTED:
    case ARDUINO_EVENT_ETH_STOP:
      Serial.println("[ETH] Sin red");
      ethConectado = false;
      wsConectado = false;
      break;
    default:
      break;
  }
}


// Pines libres de la WT32-ETH01 que se pueden leer
const uint8_t PINES_LIBRES[] = {2, 4, 13, 14, 32, 33, 34, 35, 36, 39};

void imprimirPines() {
  static unsigned long ultima = 0;
  if (millis() - ultima < 1000) return;   // una línea por segundo
  ultima = millis();

  Serial.print("[PINES]");
  for (uint8_t p : PINES_LIBRES) {
    Serial.printf(" G%d=%d", p, digitalRead(p));
  }
  Serial.println();
}

// ═════════════ setup / loop ═════════════

void setup() {
  // TEMPORAL: desactiva el detector de baja tensión. Si la placa se reinicia
  // al activar un relé, el problema real es la fuente: revisala.
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  delay(500);
  Serial.println("\n[BOOT] 09-domotica fase 1");

  Network.onEvent(onRedEvento);
  ETH.begin(ETH_PHY_LAN8720, WT32_PHY_ADDR, WT32_MDC, WT32_MDIO, WT32_POWER, WT32_CLK);
}

void loop() {
  // El WebSocket se arranca desde loop (no desde el evento de red, que corre en otra tarea).
  if (ethConectado && !wsIniciado) iniciarWebSocket();
  if (wsIniciado) webSocket.loop();

  leerSensores();
  revisarTemporizadores();
}
