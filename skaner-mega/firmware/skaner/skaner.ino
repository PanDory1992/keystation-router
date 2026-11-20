// Skaner Mega v1 dla Keystation Pro 88. Matryca rozpoznana 19.11.2026 (wyniki/matryca-20261119-2318.json).
//
// Budowa matrycy (dwie niezalezne polowki):
//   dol  A0..C4  (MIDI 21..60):  linie grup X1..X10 (piny 32..41), linie klawiszy Z1..Z8 (A0..A7 = PF0..PF7)
//   gora C#4..C8 (MIDI 61..108): linie grup W1..W10 (piny 22..31) oraz Y9, Y10 (piny 50, 51),
//                                linie klawiszy Y1..Y8 (piny 42..49 = PL7..PL0)
//   grupa g w dole:  pierwszy styk = X(2g+2), drugi = X(2g+1), klawisz = 21 + 8g + k (k = Z(k+1))
//   grupa g w gorze: pierwszy styk = W(2g+2), drugi = W(2g+1) dla g = 0..4; g = 5: pierwszy Y9, drugi Y10
//   Dioda: sterujemy linia grupy stanem NISKIM, czytamy linie klawiszy (podciagniete do 5 V).
//
// Bezpieczenstwo: tylko stan niski albo wejscie z podciagnieciem, nigdy stan wysoki na liniach klawiatury.
// Polowki nie maja wspolnych linii (sprawdzone rozpoznaniem), wiec sterujemy po jednej linii w kazdej naraz.
//
// Wyjscie 250 000 bodow (od 20.11), linie tekstu:
//   SKANER v1
//   + <midi> <us>     nuta wlaczona; us = czas od zamkniecia pierwszego do drugiego styku
//   - <midi> <us>     nuta wylaczona przy otwarciu pierwszego styku; us = od otwarcia drugiego do pierwszego (0: brak)
//   ! <midi> R        drugi styk zamknal sie bez pierwszego (odrzucone, bez dzwieku)
//   H <skanow/2s> <us na skan>

#include <avr/io.h>

const uint8_t LOW_DRIVE[10] = {32, 33, 34, 35, 36, 37, 38, 39, 40, 41};          // X1..X10
const uint8_t UP_DRIVE[12]  = {22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 50, 51};  // W1..W10, Y9, Y10
const uint8_t STEPS = 12;
// Kolejnosc w skanie: w kazdej grupie najpierw linia pierwszego styku, potem drugiego. Gdy oba styki
// zamkna sie miedzy dwoma skanami (bardzo mocne uderzenie), pierwszy zostanie zauwazony pierwszy i nuta zagra.
const uint8_t SETTLE_US = 8;      // 20.11: 8 us (bylo 3): zapas na styk o wiekszym oporze (Dupont, wtyczka XH)
const uint16_t LOCKOUT = 2000;      // po zmianie styku ignorujemy jego drgania przez 1 ms (w polowkach us)

volatile uint8_t *lowDdr[10], *lowPort[10], *upDdr[12], *upPort[12];
uint8_t lowMask[10], upMask[12];
uint8_t fBit[8], lBit[8];           // bit w PINF / PINL dla klawisza k
uint8_t mapF[256], mapL[256];
bool mapOk = true;               // standardowy uklad pinow Mega 2560 (sprawdzany w setup)       // bajt portu -> bajt klawiszy (bit k = klawisz k)

// stan stykow: styk c (0 = pierwszy, 1 = drugi) klawisza n (0..87)
uint8_t closed[88][2];
unsigned long tChange[88][2];
unsigned long t1[88], t3[88];
uint8_t sounding[88];

inline void setup1(uint8_t pin, volatile uint8_t **ddr, volatile uint8_t **port, uint8_t *mask) {
  uint8_t p = digitalPinToPort(pin);
  *ddr = portModeRegister(p);
  *port = portOutputRegister(p);
  *mask = digitalPinToBitMask(pin);
  **ddr &= ~*mask;          // wejscie
  **port |= *mask;          // podciagniecie
}

// czas z Timera1: 0,5 us na tick, rozszerzony do 32 bitow (skan trwa duzo krocej niz 32 ms)
unsigned long tHigh = 0; uint16_t tLast = 0;
static inline __attribute__((always_inline)) unsigned long now2() {        // w polowkach mikrosekundy
  uint16_t c = TCNT1;
  if (c < tLast) tHigh += 65536UL;
  tLast = c;
  return tHigh + c;
}

inline void drive(volatile uint8_t *ddr, volatile uint8_t *port, uint8_t m) { *port &= ~m; *ddr |= m; }
inline void release(volatile uint8_t *ddr, volatile uint8_t *port, uint8_t m) { *ddr &= ~m; *port |= m; }

void say(char kind, uint8_t midi, unsigned long half) {   // czas podajemy w us
  Serial.print(kind); Serial.print(' '); Serial.print(midi); Serial.print(' '); Serial.println(half >> 1);
}

bool contact(uint8_t n, uint8_t c, uint8_t now, unsigned long t) {
  if (now == closed[n][c]) return true;
  if ((unsigned long)(t - tChange[n][c]) < LOCKOUT) return false;
  closed[n][c] = now;
  tChange[n][c] = t;
  uint8_t midi = 21 + n;
  if (c == 0) {
    if (now) t1[n] = t;
    else if (sounding[n]) {
      unsigned long r = (t3[n] && !closed[n][1]) ? t - t3[n] : 0;
      say('-', midi, r);
      sounding[n] = 0;
      t3[n] = 0;
    }
  } else {
    if (now) {
      if (closed[n][0] && !sounding[n]) { say('+', midi, t - t1[n]); sounding[n] = 1; t3[n] = 0; }
      else if (!closed[n][0]) { Serial.print(F("! ")); Serial.print(midi); Serial.println(F(" R")); }
    } else {
      t3[n] = t;
    }
  }
  return true;
}

uint8_t seenLow[STEPS], seenUp[STEPS];   // ostatni przyjety stan stykow dla kazdego kroku (bit k = klawisz k)

// tylko bity, ktore sie zmienily, ida do contact(): pusty skan trwa ok. 0,25 ms
__attribute__((noinline)) void update(uint8_t *seen, uint8_t cur, uint8_t base, uint8_t c, unsigned long t) {
  uint8_t diff = cur ^ *seen;
  if (!diff) return;
  for (uint8_t k = 0; k < 8; k++) {
    if (!(diff >> k & 1)) continue;
    uint8_t now = cur >> k & 1;
    if (contact(base + k, c, now, t)) *seen ^= (1 << k);
  }
}

void setup() {
  for (uint8_t i = 0; i < 10; i++) setup1(LOW_DRIVE[i], &lowDdr[i], &lowPort[i], &lowMask[i]);
  for (uint8_t i = 0; i < 12; i++) setup1(UP_DRIVE[i], &upDdr[i], &upPort[i], &upMask[i]);
  for (uint8_t k = 0; k < 8; k++) {
    uint8_t pz = A0 + k, py = 42 + k;
    pinMode(pz, INPUT_PULLUP); pinMode(py, INPUT_PULLUP);
    uint8_t mz = digitalPinToBitMask(pz), my = digitalPinToBitMask(py);
    fBit[k] = 0; lBit[k] = 0;
    while (!(mz & 1)) { mz >>= 1; fBit[k]++; }
    while (!(my & 1)) { my >>= 1; lBit[k]++; }
  }
  // sprawdzenie, czy plytka ma standardowy uklad pinow Mega 2560 (rozwiniety skan zaklada te rejestry)
  volatile uint8_t *const expPort[22] = {&PINC,&PINC,&PINC,&PINC,&PINC,&PINC,&PIND,&PING,&PING,&PING,
                                          &PINA,&PINA,&PINA,&PINA,&PINA,&PINA,&PINA,&PINA,&PINC,&PINC,&PINB,&PINB};
  const uint8_t expBit[22]  = {5,4,3,2,1,0,7,2,1,0, 0,1,2,3,4,5,6,7,7,6,3,2};
  for (uint8_t i = 0; i < 22; i++) {
    uint8_t pin = i < 10 ? LOW_DRIVE[i] : UP_DRIVE[i - 10];
    if (portInputRegister(digitalPinToPort(pin)) != expPort[i] || digitalPinToBitMask(pin) != _BV(expBit[i])) mapOk = false;
  }
  for (uint8_t k = 0; k < 8; k++) {
    if (portInputRegister(digitalPinToPort(A0 + k)) != &PINF || portInputRegister(digitalPinToPort(42 + k)) != &PINL) mapOk = false;
  }
  for (uint16_t v = 0; v < 256; v++) {
    uint8_t a = 0, b = 0;
    for (uint8_t k = 0; k < 8; k++) { a |= ((v >> fBit[k]) & 1) << k; b |= ((v >> lBit[k]) & 1) << k; }
    mapF[v] = a; mapL[v] = b;
  }
  TCCR1A = 0; TCCR1B = (1 << CS11); TCNT1 = 0;   // Timer1: zegar / 8 = 2 MHz
  Serial.begin(250000);   // 20.11: 250 kbit zamiast 1 Mbit: mostek CH340 zawieszal sie przy 1 Mbit
  delay(200);
  Serial.println(F("SKANER v1.1"));
}

// Jeden krok skanu, rozwiniety w czasie kompilacji: stale rejestry = pojedyncze instrukcje sbi/cbi.
// L*: linia dolnej polowki (X), U*: gornej (W/Y9/Y10). LG/LC i UG/UC: grupa i styk (0 pierwszy, 1 drugi).
#define STEP2(s, LD, LP, LB, LG, LC, UD, UP, UB, UG, UC) do { \
    LP &= ~_BV(LB); LD |= _BV(LB); UP &= ~_BV(UB); UD |= _BV(UB); \
    delayMicroseconds(SETTLE_US); \
    unsigned long t = now2(); uint8_t f = ~PINF, l = ~PINL; \
    LD &= ~_BV(LB); LP |= _BV(LB); UD &= ~_BV(UB); UP |= _BV(UB); \
    uint8_t cf = mapF[f], cu = mapL[l]; \
    if (cf != seenLow[s]) update(&seenLow[s], cf, 8 * (LG), LC, t); \
    if (cu != seenUp[s]) update(&seenUp[s], cu, 40 + 8 * (UG), UC, t); \
  } while (0)
#define STEP1(s, UD, UP, UB, UG, UC) do { \
    UP &= ~_BV(UB); UD |= _BV(UB); \
    delayMicroseconds(SETTLE_US); \
    unsigned long t = now2(); uint8_t l = ~PINL; \
    UD &= ~_BV(UB); UP |= _BV(UB); \
    uint8_t cu = mapL[l]; \
    if (cu != seenUp[s]) update(&seenUp[s], cu, 40 + 8 * (UG), UC, t); \
  } while (0)


void loop() {
  static unsigned long scans = 0, sumUs = 0, t0 = millis();
  if (!mapOk) { Serial.println(F("BLAD MAPY PINOW")); delay(2000); return; }
  unsigned long a = now2();
  // w kazdej grupie najpierw linia pierwszego styku (X2, X4.. / W2, W4.. / Y9), potem drugiego
  STEP2(1, DDRC, PORTC, 4, 0, 0,  DDRA, PORTA, 1, 0, 0);   // X2  | W2
  STEP2(0, DDRC, PORTC, 5, 0, 1,  DDRA, PORTA, 0, 0, 1);   // X1  | W1
  STEP2(3, DDRC, PORTC, 2, 1, 0,  DDRA, PORTA, 3, 1, 0);   // X4  | W4
  STEP2(2, DDRC, PORTC, 3, 1, 1,  DDRA, PORTA, 2, 1, 1);   // X3  | W3
  STEP2(5, DDRC, PORTC, 0, 2, 0,  DDRA, PORTA, 5, 2, 0);   // X6  | W6
  STEP2(4, DDRC, PORTC, 1, 2, 1,  DDRA, PORTA, 4, 2, 1);   // X5  | W5
  STEP2(7, DDRG, PORTG, 2, 3, 0,  DDRA, PORTA, 7, 3, 0);   // X8  | W8
  STEP2(6, DDRD, PORTD, 7, 3, 1,  DDRA, PORTA, 6, 3, 1);   // X7  | W7
  STEP2(9, DDRG, PORTG, 0, 4, 0,  DDRC, PORTC, 6, 4, 0);   // X10 | W10
  STEP2(8, DDRG, PORTG, 1, 4, 1,  DDRC, PORTC, 7, 4, 1);   // X9  | W9
  STEP1(10, DDRB, PORTB, 3, 5, 0);                        // Y9
  STEP1(11, DDRB, PORTB, 2, 5, 1);                        // Y10
  sumUs += (now2() - a) >> 1; scans++;
  if (millis() - t0 >= 2000) {
    Serial.print(F("H ")); Serial.print(scans); Serial.print(' '); Serial.println(sumUs / scans);
    scans = 0; sumUs = 0; t0 = millis();
  }
}
