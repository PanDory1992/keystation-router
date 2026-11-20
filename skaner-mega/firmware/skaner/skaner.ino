// Skaner Mega v2.0 dla Keystation Pro 88 (20.11.2026). Matryca rozpoznana 19.11 (wyniki/matryca-20261119-2318.json).
//
// Budowa matrycy (dwie niezalezne polowki):
//   dol  A0..C4  (MIDI 21..60):  linie grup X1..X10 (piny 32..41), linie klawiszy Z1..Z8 (A0..A7 = PF0..PF7)
//   gora C#4..C8 (MIDI 61..108): linie grup W1..W10 (piny 22..31) oraz Y9, Y10 (piny 50, 51),
//                                linie klawiszy Y1..Y8 (piny 42..49 = PL7..PL0); Y2 od 20.11 na A8 (PK0), pin 43 pusty
//   grupa g w dole:  pierwszy styk = X(2g+2), drugi = X(2g+1), klawisz = 21 + 8g + k (k = Z(k+1))
//   grupa g w gorze: pierwszy styk = W(2g+2), drugi = W(2g+1) dla g = 0..4; g = 5: pierwszy Y9, drugi Y10
//   Dioda: sterujemy linia grupy stanem NISKIM, czytamy linie klawiszy (podciagniete do 5 V).
//
// Bezpieczenstwo: tylko stan niski albo wejscie z podciagnieciem, nigdy stan wysoki na liniach klawiatury.
//
// v2.0 (zmiany wzgledem v1.2):
//  * Ramki binarne zamiast tekstu: COBS (0x00 = koniec ramki), numer kolejny i CRC-8. Zgubiony albo przeklamany
//    bajt nie moze juz zagrac zlej nuty ani zlego velocity (w v1 "+ 60 2345" po zgubionej cyfrze = fff).
//  * Kazde zdarzenie niesie czas Megi (0,5 us), wiec komputer zna prawdziwy rytm i czas trzymania niezaleznie od USB.
//  * Wysylanie bez czekania: zdarzenia ida do kolejki, do portu tylko wtedy, gdy jest miejsce. Skan nigdy nie stoi.
//    Wlasny sterownik portu zamiast Serial z Arduino (ramka kosztuje ok. 20 us zamiast ok. 180 us).
//  * Co 1 s znak zycia z mapa brzmiacych klawiszy: komputer gasi nute, ktorej wylaczenie zginelo.
//  * Przy starcie i na zadanie test linii: czy pin dziala i czy jest do niego cos podlaczone (czas narastania).
//
// Ramki (przed COBS):  typ, seq, dane..., crc8 (CRC-8/SMBUS: wielomian 0x07, start 0x00, liczony od typu)
//   0x01 NUTA_ON   midi, us (3 B), t (4 B)         us = od zamkniecia pierwszego do drugiego styku
//   0x02 NUTA_OFF  midi, us (3 B), t (4 B)         przy otwarciu pierwszego styku; us = od otwarcia drugiego (0 = brak)
//   0x03 ODWROTNIE midi, t (4 B)                    drugi styk bez pierwszego (bez dzwieku)
//   0x10 HELLO     proto, major, minor, build (4 B), flagi (bit0 mapa pinow OK, bit1 Y2 na A8)
//   0x11 ZYCIE     t (4 B), skany/s (2 B), sredni skan us (2 B), najdluzszy us (2 B), przepelnienia (2 B),
//                  odebrane polecenia (2 B), brzmiace klawisze (11 B, bit n = MIDI 21 + n)
//   0x12 TEST      40 x licznik narastania (1 B), 5 B bitow "pin nie schodzi do zera"
// Liczby wielobajtowe: najmlodszy bajt pierwszy. Czas t: licznik 0,5 us, przekreca sie co 35,8 min.
// Polecenia z komputera (jeden bajt): 'I' = HELLO teraz, 'S' = ZYCIE teraz, 'T' = test linii.

#include <avr/io.h>

const uint8_t PROTO = 2, FW_MAJOR = 2, FW_MINOR = 0;
const uint32_t BUILD_ID = 2026112001UL;   // ten sam numer w hex/skaner.json; router porownuje i w razie potrzeby wgrywa

const uint8_t LOW_DRIVE[10] = {32, 33, 34, 35, 36, 37, 38, 39, 40, 41};          // X1..X10
const uint8_t UP_DRIVE[12]  = {22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 50, 51};  // W1..W10, Y9, Y10
const uint8_t STEPS = 12;
const uint8_t SETTLE_US = 8;      // 20.11: 8 us: zapas na styk o wiekszym oporze (Dupont, wtyczka XH)
const uint16_t LOCKOUT = 2000;    // po zmianie styku ignorujemy jego drgania przez 1 ms (w polowkach us)

uint8_t fBit[8], lBit[8];
uint8_t mapF[256], mapL[256];
bool mapOk = true;

uint8_t closed[88][2];
unsigned long tChange[88][2];
unsigned long t1[88], t3[88];
uint8_t sounding[88];

// czas z Timera1: 0,5 us na tick, rozszerzony do 32 bitow (petla wola go duzo czesciej niz co 32 ms)
unsigned long tHigh = 0; uint16_t tLast = 0;
static inline __attribute__((always_inline)) unsigned long now2() {
  uint16_t c = TCNT1;
  if (c < tLast) tHigh += 65536UL;
  tLast = c;
  return tHigh + c;
}

// --- kolejka zdarzen (skan nie czeka na port) ---------------------------------------------------------------
struct Ev { uint8_t type, note; unsigned long a, t; };
const uint8_t QN = 128;                      // potega dwojki (88 klawiszy naraz miesci sie z zapasem)
Ev q[QN];
volatile uint8_t qHead = 0, qTail = 0;
uint16_t overflows = 0;

void push(uint8_t type, uint8_t note, unsigned long a, unsigned long t) {
  uint8_t n = (qHead + 1) & (QN - 1);
  if (n == qTail) { overflows++; return; }   // pelna: zdarzenie przepada, mapa w ZYCIU naprawi zawieszona nute
  q[qHead].type = type; q[qHead].note = note; q[qHead].a = a; q[qHead].t = t;
  qHead = n;
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
      unsigned long r = (t3[n] && !closed[n][1]) ? (t - t3[n]) >> 1 : 0;
      push(0x02, midi, r, t);
      sounding[n] = 0;
      t3[n] = 0;
    }
  } else {
    if (now) {
      if (closed[n][0] && !sounding[n]) { push(0x01, midi, (t - t1[n]) >> 1, t); sounding[n] = 1; t3[n] = 0; }
      else if (!closed[n][0]) push(0x03, midi, 0, t);
    } else {
      t3[n] = t;
    }
  }
  return true;
}

uint8_t seenLow[STEPS], seenUp[STEPS];

__attribute__((noinline)) void update(uint8_t *seen, uint8_t cur, uint8_t base, uint8_t c, unsigned long t) {
  uint8_t diff = cur ^ *seen;
  if (!diff) return;
  uint8_t m = 1;
  for (uint8_t k = 0; k < 8; k++, m <<= 1) {        // maska zamiast przesuniec o k (AVR przesuwa po jednym bicie)
    if (!(diff & m)) continue;
    if (contact(base + k, c, (cur & m) ? 1 : 0, t)) *seen ^= m;
  }
}

// --- wlasny port szeregowy (USART0) ------------------------------------------------------------------------------
// 20.11: Serial z Arduino kosztowal ok. 180 us na ramke (symulator), a to opoznia odczyt styku. Tu wpis do bufora
// to kilka cykli na bajt, a przerwanie wysyla bajt po bajcie. Bufor 256 B: indeksy uint8_t przekrecaja sie same.
volatile uint8_t txBuf[256], rxBuf[16];
volatile uint8_t txHead = 0, txTail = 0, rxHead = 0, rxTail = 0;
ISR(USART0_UDRE_vect) {
  if (txHead == txTail) { UCSR0B &= ~_BV(UDRIE0); return; }
  UDR0 = txBuf[txTail++];
}
ISR(USART0_RX_vect) {
  uint8_t c = UDR0;
  uint8_t n = (rxHead + 1) & 15;
  if (n != rxTail) { rxBuf[rxHead] = c; rxHead = n; }
}
inline uint8_t txFree() { return (uint8_t)(txTail - txHead - 1); }
void uartBegin() {                    // 250 000 bodow: U2X, UBRR = 16 MHz / (8 * 250000) - 1 = 7 (bez bledu)
  UCSR0A = _BV(U2X0);                   // najpierw U2X, potem dzielnik (tak jak Arduino; simavr liczy predkosc przy zapisie UBRR)
  UBRR0H = 0; UBRR0L = 7;
  UCSR0C = _BV(UCSZ01) | _BV(UCSZ00);   // 8N1
  UCSR0B = _BV(RXEN0) | _BV(TXEN0) | _BV(RXCIE0);
}
int uartRead() {
  if (rxHead == rxTail) return -1;
  uint8_t c = rxBuf[rxTail];
  rxTail = (rxTail + 1) & 15;
  return c;
}

// --- ramki ----------------------------------------------------------------------------------------------------
uint8_t seq = 0;
uint16_t rxCount = 0;

// CRC-8/SMBUS z tablicy (we flashu): ok. 6 cykli na bajt zamiast ok. 50 przy liczeniu bit po bicie
#include <avr/pgmspace.h>
const uint8_t CRC_TABLE[256] PROGMEM = {
  0x00, 0x07, 0x0E, 0x09, 0x1C, 0x1B, 0x12, 0x15, 0x38, 0x3F, 0x36, 0x31, 0x24, 0x23, 0x2A, 0x2D,
  0x70, 0x77, 0x7E, 0x79, 0x6C, 0x6B, 0x62, 0x65, 0x48, 0x4F, 0x46, 0x41, 0x54, 0x53, 0x5A, 0x5D,
  0xE0, 0xE7, 0xEE, 0xE9, 0xFC, 0xFB, 0xF2, 0xF5, 0xD8, 0xDF, 0xD6, 0xD1, 0xC4, 0xC3, 0xCA, 0xCD,
  0x90, 0x97, 0x9E, 0x99, 0x8C, 0x8B, 0x82, 0x85, 0xA8, 0xAF, 0xA6, 0xA1, 0xB4, 0xB3, 0xBA, 0xBD,
  0xC7, 0xC0, 0xC9, 0xCE, 0xDB, 0xDC, 0xD5, 0xD2, 0xFF, 0xF8, 0xF1, 0xF6, 0xE3, 0xE4, 0xED, 0xEA,
  0xB7, 0xB0, 0xB9, 0xBE, 0xAB, 0xAC, 0xA5, 0xA2, 0x8F, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9D, 0x9A,
  0x27, 0x20, 0x29, 0x2E, 0x3B, 0x3C, 0x35, 0x32, 0x1F, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0D, 0x0A,
  0x57, 0x50, 0x59, 0x5E, 0x4B, 0x4C, 0x45, 0x42, 0x6F, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7D, 0x7A,
  0x89, 0x8E, 0x87, 0x80, 0x95, 0x92, 0x9B, 0x9C, 0xB1, 0xB6, 0xBF, 0xB8, 0xAD, 0xAA, 0xA3, 0xA4,
  0xF9, 0xFE, 0xF7, 0xF0, 0xE5, 0xE2, 0xEB, 0xEC, 0xC1, 0xC6, 0xCF, 0xC8, 0xDD, 0xDA, 0xD3, 0xD4,
  0x69, 0x6E, 0x67, 0x60, 0x75, 0x72, 0x7B, 0x7C, 0x51, 0x56, 0x5F, 0x58, 0x4D, 0x4A, 0x43, 0x44,
  0x19, 0x1E, 0x17, 0x10, 0x05, 0x02, 0x0B, 0x0C, 0x21, 0x26, 0x2F, 0x28, 0x3D, 0x3A, 0x33, 0x34,
  0x4E, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5C, 0x5B, 0x76, 0x71, 0x78, 0x7F, 0x6A, 0x6D, 0x64, 0x63,
  0x3E, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2C, 0x2B, 0x06, 0x01, 0x08, 0x0F, 0x1A, 0x1D, 0x14, 0x13,
  0xAE, 0xA9, 0xA0, 0xA7, 0xB2, 0xB5, 0xBC, 0xBB, 0x96, 0x91, 0x98, 0x9F, 0x8A, 0x8D, 0x84, 0x83,
  0xDE, 0xD9, 0xD0, 0xD7, 0xC2, 0xC5, 0xCC, 0xCB, 0xE6, 0xE1, 0xE8, 0xEF, 0xFA, 0xFD, 0xF4, 0xF3
};
uint8_t crc8(const uint8_t *p, uint8_t n) {
  uint8_t c = 0;
  while (n--) c = pgm_read_byte(&CRC_TABLE[c ^ *p++]);
  return c;
}

// raw[0] = typ, raw[1] zostanie seq, raw[2..len-1] dane; dopisuje crc, koduje COBS i wysyla tylko, gdy sie zmiesci
bool sendFrame(uint8_t *raw, uint8_t len) {
  uint8_t need = len + 3;                       // crc + bajt COBS + 0x00
  if (txFree() < need) return false;
  raw[1] = seq;
  raw[len] = crc8(raw, len);
  len++;
  // COBS prosto do bufora nadawczego: miejsce na bajt kodu rezerwujemy i wpisujemy, gdy znamy dlugosc bloku
  uint8_t h = txHead, ci = h++, code = 1;
  for (uint8_t i = 0; i < len; i++) {
    if (raw[i] == 0) { txBuf[ci] = code; code = 1; ci = h++; }
    else { txBuf[h++] = raw[i]; code++; }
  }
  txBuf[ci] = code;
  txBuf[h++] = 0;
  txHead = h;                          // dopiero teraz ramka jest widoczna dla przerwania
  UCSR0B |= _BV(UDRIE0);
  seq++;
  return true;
}

inline void put24(uint8_t *p, unsigned long v) { if (v > 0xFFFFFFUL) v = 0xFFFFFFUL; p[0] = v; p[1] = v >> 8; p[2] = v >> 16; }
inline void put32(uint8_t *p, unsigned long v) { p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24; }
inline void put16(uint8_t *p, uint16_t v) { p[0] = v; p[1] = v >> 8; }

bool sendEvent(uint8_t type, uint8_t note, unsigned long a, unsigned long t) {   // bez struct: prototypy Arduino
  uint8_t raw[16];
  raw[0] = type; raw[2] = note;
  if (type == 0x03) { put32(raw + 3, t); return sendFrame(raw, 7); }
  put24(raw + 3, a); put32(raw + 6, t);
  return sendFrame(raw, 10);
}

bool sendHello() {
  uint8_t raw[16];
  raw[0] = 0x10; raw[2] = PROTO; raw[3] = FW_MAJOR; raw[4] = FW_MINOR;
  put32(raw + 5, BUILD_ID);
  raw[9] = (mapOk ? 1 : 0) | 2;
  return sendFrame(raw, 10);
}

unsigned long hbScans = 0, hbSum = 0; uint16_t hbMax = 0;

bool sendLife() {
  uint8_t raw[32];
  raw[0] = 0x11;
  put32(raw + 2, now2());
  put16(raw + 6, hbScans > 65535UL ? 65535 : (uint16_t)hbScans);
  put16(raw + 8, hbScans ? (uint16_t)(hbSum / hbScans) : 0);
  put16(raw + 10, hbMax);
  put16(raw + 12, overflows);
  put16(raw + 14, rxCount);
  for (uint8_t i = 0; i < 11; i++) raw[16 + i] = 0;
  for (uint8_t n = 0; n < 88; n++) if (sounding[n]) raw[16 + (n >> 3)] |= 1 << (n & 7);
  return sendFrame(raw, 27);
}

// --- test linii -------------------------------------------------------------------------------------------------
// Dla kazdej linii: chwila w stanie niskim (czy pin schodzi do zera), potem podciagniecie i liczenie, ile obrotow
// petli trwa powrot do jedynki. Linia z podlaczonym kablem ma wieksza pojemnosc, wiec wraca wolniej niz pusty pin.
// Odniesienie: piny 43 i 53, do ktorych nic nie jest podlaczone. Tylko raport, nic nie blokuje.
const uint8_t TEST_N = 40;
const uint8_t TEST_PINS[TEST_N] = {
  22, 23, 24, 25, 26, 27, 28, 29, 30, 31,   // W1..W10
  32, 33, 34, 35, 36, 37, 38, 39, 40, 41,   // X1..X10
  42, A8, 44, 45, 46, 47, 48, 49, 50, 51,   // Y1..Y10 (Y2 na A8)
  A0, A1, A2, A3, A4, A5, A6, A7,           // Z1..Z8
  43, 53                                    // odniesienie: puste piny
};
bool testPending = true;

bool runTest() {
  if (txFree() < 52) return false;     // ramka testu ma 50 bajtow po kodowaniu
  uint8_t raw[52];
  raw[0] = 0x12;
  for (uint8_t i = 0; i < 5; i++) raw[2 + TEST_N + i] = 0;
  for (uint8_t i = 0; i < TEST_N; i++) {
    uint8_t p = TEST_PINS[i], port = digitalPinToPort(p);
    volatile uint8_t *ddr = portModeRegister(port), *out = portOutputRegister(port), *in = portInputRegister(port);
    uint8_t m = digitalPinToBitMask(p);
    uint16_t sum = 0; bool stuck = false;
    for (uint8_t k = 0; k < 8; k++) {
      uint8_t s = SREG; cli();
      *out &= ~m; *ddr |= m;                 // najpierw PORT = 0, potem wyjscie: nigdy stan wysoki
      delayMicroseconds(10);
      bool high = *in & m;
      *ddr &= ~m; *out |= m;                 // wejscie z podciagnieciem
      uint8_t c = 0;
      while (!(*in & m) && c < 250) c++;
      SREG = s;
      if (high) stuck = true;
      sum += c;
      delayMicroseconds(50);
    }
    raw[2 + i] = sum > 255 ? 255 : sum;
    if (stuck) raw[2 + TEST_N + (i >> 3)] |= 1 << (i & 7);
  }
  return sendFrame(raw, 2 + TEST_N + 5);
}

void setup1(uint8_t pin) {
  uint8_t p = digitalPinToPort(pin), m = digitalPinToBitMask(pin);
  *portModeRegister(p) &= ~m;        // wejscie
  *portOutputRegister(p) |= m;       // podciagniecie
}

void setup() {
  for (uint8_t i = 0; i < 10; i++) setup1(LOW_DRIVE[i]);
  for (uint8_t i = 0; i < 12; i++) setup1(UP_DRIVE[i]);
  pinMode(A8, INPUT_PULLUP);          // Y2 (od 20.11)
  pinMode(43, INPUT_PULLUP);          // pusty, tylko odniesienie testu
  pinMode(53, INPUT_PULLUP);
  for (uint8_t k = 0; k < 8; k++) {
    uint8_t pz = A0 + k, py = 42 + k;
    pinMode(pz, INPUT_PULLUP); pinMode(py, INPUT_PULLUP);
    uint8_t mz = digitalPinToBitMask(pz), my = digitalPinToBitMask(py);
    fBit[k] = 0; lBit[k] = 0;
    while (!(mz & 1)) { mz >>= 1; fBit[k]++; }
    while (!(my & 1)) { my >>= 1; lBit[k]++; }
  }
  // standardowy uklad pinow Mega 2560 (rozwiniety skan zaklada te rejestry)
  volatile uint8_t *const expPort[22] = {&PINC,&PINC,&PINC,&PINC,&PINC,&PINC,&PIND,&PING,&PING,&PING,
                                          &PINA,&PINA,&PINA,&PINA,&PINA,&PINA,&PINA,&PINA,&PINC,&PINC,&PINB,&PINB};
  const uint8_t expBit[22]  = {5,4,3,2,1,0,7,2,1,0, 0,1,2,3,4,5,6,7,7,6,3,2};
  for (uint8_t i = 0; i < 22; i++) {
    uint8_t pin = i < 10 ? LOW_DRIVE[i] : UP_DRIVE[i - 10];
    if (portInputRegister(digitalPinToPort(pin)) != expPort[i] || digitalPinToBitMask(pin) != _BV(expBit[i])) mapOk = false;
  }
  for (uint8_t k = 0; k < 8; k++)
    if (portInputRegister(digitalPinToPort(A0 + k)) != &PINF || portInputRegister(digitalPinToPort(42 + k)) != &PINL) mapOk = false;
  if (portInputRegister(digitalPinToPort(A8)) != &PINK || digitalPinToBitMask(A8) != _BV(0)) mapOk = false;
  for (uint16_t v = 0; v < 256; v++) {
    uint8_t a = 0, b = 0;
    for (uint8_t k = 0; k < 8; k++) { a |= ((v >> fBit[k]) & 1) << k; b |= ((v >> lBit[k]) & 1) << k; }
    mapF[v] = a; mapL[v] = b;
  }
  TCCR1A = 0; TCCR1B = (1 << CS11); TCNT1 = 0;   // Timer1: zegar / 8 = 2 MHz
  uartBegin();
  delay(50);
  sendHello();
}

// Jeden krok skanu, rozwiniety w czasie kompilacji: stale rejestry = pojedyncze instrukcje sbi/cbi.
// L*: linia dolnej polowki (X), U*: gornej (W/Y9/Y10). LG/LC i UG/UC: grupa i styk (0 pierwszy, 1 drugi).
// Bit 1 gornej polowki (Y2) bierzemy z PINK bit 0 (A8) zamiast z PINL (pin 43 przestal dzialac 20.11).
#define Y2FIX(cu, kk) (uint8_t)(((cu) & ~0x02) | (((kk) & 0x01) << 1))
#define STEP2(s, LD, LP, LB, LG, LC, UD, UP, UB, UG, UC) do { \
    LP &= ~_BV(LB); LD |= _BV(LB); UP &= ~_BV(UB); UD |= _BV(UB); \
    delayMicroseconds(SETTLE_US); \
    unsigned long t = now2(); uint8_t f = ~PINF, l = ~PINL, kk = ~PINK; \
    LD &= ~_BV(LB); LP |= _BV(LB); UD &= ~_BV(UB); UP |= _BV(UB); \
    uint8_t cf = mapF[f], cu = Y2FIX(mapL[l], kk); \
    if (cf != seenLow[s]) update(&seenLow[s], cf, 8 * (LG), LC, t); \
    if (cu != seenUp[s]) update(&seenUp[s], cu, 40 + 8 * (UG), UC, t); \
  } while (0)
#define STEP1(s, UD, UP, UB, UG, UC) do { \
    UP &= ~_BV(UB); UD |= _BV(UB); \
    delayMicroseconds(SETTLE_US); \
    unsigned long t = now2(); uint8_t l = ~PINL, kk = ~PINK; \
    UD &= ~_BV(UB); UP |= _BV(UB); \
    uint8_t cu = Y2FIX(mapL[l], kk); \
    if (cu != seenUp[s]) update(&seenUp[s], cu, 40 + 8 * (UG), UC, t); \
  } while (0)

void loop() {
  static unsigned long t0 = millis();
  static uint8_t lives = 0;
  static bool helloPending = false, lifePending = false;
  if (!mapOk) {                       // nietypowa plytka: nie skanujemy, tylko meldujemy sie co sekunde
    sendHello(); delay(1000); return;
  }
  unsigned long a = now2();
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
  uint16_t took = (now2() - a) >> 1;
  hbSum += took; hbScans++; if (took > hbMax) hbMax = took;

  // wysylka: najwyzej JEDNA ramka na obrot skanu (ok. 25 us), zeby kodowanie nie opoznialo odczytu styku.
  // Port i tak wysyla 13 bajtow ok. 0,5 ms, a obrot trwa ok. 0,15 ms, wiec kolejka nadaza.
  if (qTail != qHead) {
    if (sendEvent(q[qTail].type, q[qTail].note, q[qTail].a, q[qTail].t)) qTail = (qTail + 1) & (QN - 1);
  }
  for (int c = uartRead(); c >= 0; c = uartRead()) {
    rxCount++;
    if (c == 'I') helloPending = true;
    else if (c == 'S') lifePending = true;
    else if (c == 'T') testPending = true;
  }
  if (millis() - t0 >= 1000) {
    t0 += 1000;
    lifePending = true;
    if (++lives >= 10) { lives = 0; helloPending = true; }
  }
  if (qTail == qHead) {
    if (helloPending && sendHello()) helloPending = false;
    if (lifePending && sendLife()) { lifePending = false; hbScans = 0; hbSum = 0; hbMax = 0; }
    if (testPending && runTest()) testPending = false;
  }
}
