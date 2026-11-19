// Skaner Mega: rozpoznanie matrycy klawiatury Keystation Pro 88.
//
// Bezpieczenstwo: kazdy pin jest wejsciem z podciagnieciem do 5 V. Naraz tylko JEDEN pin
// staje sie wyjsciem i tylko w stanie NISKIM, na kilkanascie mikrosekund. Nigdy nie wystawiamy
// stanu wysokiego, wiec dwa przewody polaczone w klawiaturze nie moga zrobic zwarcia.
//
// Wyjscie (115200 bodow, jedna linia na zdarzenie):
//   ROZPOZNANIE v1 <liczba pinow>
//   PIN <indeks> <etykieta> <pin Megi>
//   LOW <indeks>            pin niski bez sterowania (podejrzany przewod do masy)
//   R <i> <j>               w spoczynku: sterowanie i ciagnie j (przewody polaczone na stale)
//   GOTOWE
//   E + <i> <j> <us>        styk zamkniety: sterowanie i ciagnie j
//   E - <i> <j> <us>        styk otwarty
//   H <skanow> <us na skan> co 2 s, znak zycia

const uint8_t N = 38;
const uint8_t PINS[N] = {
  22, 23, 24, 25, 26, 27, 28, 29, 30, 31,   // W1..W10
  32, 33, 34, 35, 36, 37, 38, 39, 40, 41,   // X1..X10
  42, 43, 44, 45, 46, 47, 48, 49, 50, 51,   // Y1..Y10
  A0, A1, A2, A3, A4, A5, A6, A7            // Z1..Z8
};

volatile uint8_t *inReg[N], *outReg[N], *ddrReg[N];
uint8_t mask[N];
uint64_t conn[N];      // conn[i] bit j: sterowanie i ciagnie j w dol
uint64_t rest[N];

void label(uint8_t i) {
  char g = 'W' + (i < 30 ? i / 10 : 3);
  uint8_t k = (i < 30 ? i % 10 : i - 30) + 1;
  Serial.print(g); Serial.print(k);
}

inline void asInput(uint8_t i) {           // wejscie z podciagnieciem
  uint8_t s = SREG; cli();
  *ddrReg[i] &= ~mask[i];
  *outReg[i] |= mask[i];
  SREG = s;
}
inline void driveLow(uint8_t i) {          // najpierw PORT=0, potem DDR=1: nigdy stan wysoki
  uint8_t s = SREG; cli();
  *outReg[i] &= ~mask[i];
  *ddrReg[i] |= mask[i];
  SREG = s;
}
inline bool isLow(uint8_t j) { return !(*inReg[j] & mask[j]); }

void scan(uint64_t *out, unsigned long *when) {
  for (uint8_t i = 0; i < N; i++) {
    driveLow(i);
    delayMicroseconds(12);
    if (when) when[i] = micros();
    uint64_t m = 0;
    for (uint8_t j = 0; j < N; j++) if (j != i && isLow(j)) m |= (uint64_t)1 << j;
    out[i] = m;
    asInput(i);
    delayMicroseconds(12);
  }
}

unsigned long when[N];

void setup() {
  for (uint8_t i = 0; i < N; i++) {
    uint8_t p = PINS[i];
    uint8_t port = digitalPinToPort(p);
    inReg[i] = portInputRegister(port);
    outReg[i] = portOutputRegister(port);
    ddrReg[i] = portModeRegister(port);
    mask[i] = digitalPinToBitMask(p);
    asInput(i);
  }
  Serial.begin(115200);
  delay(300);
  Serial.print(F("ROZPOZNANIE v1 ")); Serial.println(N);
  for (uint8_t i = 0; i < N; i++) {
    Serial.print(F("PIN ")); Serial.print(i); Serial.print(' ');
    label(i); Serial.print(' '); Serial.println(PINS[i]);
  }
  for (uint8_t i = 0; i < N; i++) if (isLow(i)) { Serial.print(F("LOW ")); Serial.println(i); }
  // spoczynek: 5 skanow, zostaje to, co widac w kazdym (stale polaczenia)
  for (uint8_t i = 0; i < N; i++) rest[i] = ~(uint64_t)0;
  for (uint8_t k = 0; k < 5; k++) {
    scan(conn, 0);
    for (uint8_t i = 0; i < N; i++) rest[i] &= conn[i];
    delay(5);
  }
  for (uint8_t i = 0; i < N; i++)
    for (uint8_t j = 0; j < N; j++)
      if (rest[i] >> j & 1) { Serial.print(F("R ")); Serial.print(i); Serial.print(' '); Serial.println(j); }
  for (uint8_t i = 0; i < N; i++) conn[i] = rest[i];
  Serial.println(F("GOTOWE"));
}

void loop() {
  static uint64_t now[N];
  static unsigned long scans = 0, t0 = millis(), sumUs = 0;
  unsigned long a = micros();
  scan(now, when);
  sumUs += micros() - a; scans++;
  for (uint8_t i = 0; i < N; i++) {
    uint64_t d = now[i] ^ conn[i];
    if (!d) continue;
    for (uint8_t j = 0; j < N; j++) {
      if (!(d >> j & 1)) continue;
      Serial.print(F("E ")); Serial.print((now[i] >> j & 1) ? '+' : '-'); Serial.print(' ');
      Serial.print(i); Serial.print(' '); Serial.print(j); Serial.print(' '); Serial.println(when[i]);
    }
    conn[i] = now[i];
  }
  if (millis() - t0 >= 2000) {
    Serial.print(F("H ")); Serial.print(scans); Serial.print(' '); Serial.println(sumUs / scans);
    scans = 0; sumUs = 0; t0 = millis();
  }
}
