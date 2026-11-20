// Symulator matrycy Keystation dla skanera Mega (simavr). Prawdziwy program skaner.elf na wirtualnym ATmega2560,
// a styki klawiszy sa modelowane tak jak w klawiaturze: dioda + styk miedzy linia grupy a linia klawisza.
// Gdy skaner ciagnie linie grupy w dol, linie klawiszy z zamknietym stykiem na tej grupie czytaja 0.
//
// Uzycie: matrix_sim skaner.elf scenariusz.txt wyjscie.txt [czas_us]
// Scenariusz (posortowany po czasie):  "<t_us> k <midi> <styk 0|1> <0|1>"  albo  "<t_us> rx <bajt>"
// Wyjscie: "<t_us> <bajt>" dla kazdego bajtu wyslanego przez UART0.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sim_avr.h"
#include "sim_elf.h"
#include "avr_ioport.h"
#include "avr_uart.h"

typedef struct { char port; int bit; } line_t;
// linie grup: X1..X10, W1..W10, Y9, Y10
static const line_t X[10] = {{'C',5},{'C',4},{'C',3},{'C',2},{'C',1},{'C',0},{'D',7},{'G',2},{'G',1},{'G',0}};
static const line_t W[10] = {{'A',0},{'A',1},{'A',2},{'A',3},{'A',4},{'A',5},{'A',6},{'A',7},{'C',7},{'C',6}};
static const line_t Y9 = {'B',3}, Y10 = {'B',2};
// linie klawiszy: Z1..Z8 = PF0..PF7; Y1..Y8 = PL7..PL0, ale Y2 od 20.11 wieczorem na PB1 (pin 52)
static line_t Z[8], Y[8];

static int ddr_addr(char p) {
  switch (p) { case 'A': return 0x21; case 'B': return 0x24; case 'C': return 0x27; case 'D': return 0x2A;
               case 'G': return 0x33; case 'F': return 0x30; case 'K': return 0x107; case 'L': return 0x10A; }
  return -1;
}

static avr_t *avr;
static int contacts[88][2];
static FILE *out;
static int y2_on_43 = 0;

static int driven_low(line_t l) {
  int d = ddr_addr(l.port);
  return (avr->data[d] >> l.bit & 1) && !(avr->data[d + 1] >> l.bit & 1);
}

static void first_second(int n, line_t *f, line_t *s, line_t *key) {
  if (n < 40) { int g = n / 8, k = n % 8; *f = X[2 * g + 1]; *s = X[2 * g]; *key = Z[k]; }
  else {
    int m = n - 40, g = m / 8, k = m % 8;
    if (g < 5) { *f = W[2 * g + 1]; *s = W[2 * g]; } else { *f = Y9; *s = Y10; }
    *key = Y[k];
  }
}

static int last_level[2][8];
static void apply(void) {
  int lvl[2][8];
  for (int i = 0; i < 8; i++) lvl[0][i] = lvl[1][i] = 1;
  for (int n = 0; n < 88; n++) {
    line_t f, s, key; first_second(n, &f, &s, &key);
    int half = n < 40 ? 0 : 1, k = n < 40 ? n % 8 : (n - 40) % 8;
    if ((contacts[n][0] && driven_low(f)) || (contacts[n][1] && driven_low(s))) lvl[half][k] = 0;
  }
  for (int h = 0; h < 2; h++) for (int k = 0; k < 8; k++) {
    if (lvl[h][k] == last_level[h][k]) continue;
    last_level[h][k] = lvl[h][k];
    line_t key = h ? Y[k] : Z[k];
    avr_raise_irq(avr_io_getirq(avr, AVR_IOCTL_IOPORT_GETIRQ(key.port), key.bit), lvl[h][k]);
  }
}

static void uart_out(struct avr_irq_t *irq, uint32_t value, void *param) {
  fprintf(out, "%.2f %u\n", avr->cycle / 16.0, value & 0xFF);
}

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "matrix_sim elf scen out [us]\n"); return 2; }
  double limit = argc > 4 ? atof(argv[4]) : 2e6;
  if (getenv("Y2_ON_43")) y2_on_43 = 1;           // stary uklad (Y2 na pinie 43 = PL6)
  for (int k = 0; k < 8; k++) { Z[k].port = 'F'; Z[k].bit = k; Y[k].port = 'L'; Y[k].bit = 7 - k; }
  if (!y2_on_43) { Y[1].port = 'B'; Y[1].bit = 1; }
  elf_firmware_t fw; memset(&fw, 0, sizeof fw);
  if (elf_read_firmware(argv[1], &fw)) { fprintf(stderr, "elf?\n"); return 1; }
  avr = avr_make_mcu_by_name("atmega2560");
  avr_init(avr); avr->frequency = 16000000; avr_load_firmware(avr, &fw);
  uint32_t flags = 0;
  avr_ioctl(avr, AVR_IOCTL_UART_GET_FLAGS('0'), &flags);
  flags &= ~AVR_UART_FLAG_STDIO;
  avr_ioctl(avr, AVR_IOCTL_UART_SET_FLAGS('0'), &flags);
  out = fopen(argv[3], "w");
  avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_OUTPUT), uart_out, NULL);
  avr_irq_t *rx = avr_io_getirq(avr, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_INPUT);
  for (int h = 0; h < 2; h++) for (int k = 0; k < 8; k++) last_level[h][k] = -1;
  FILE *sc = fopen(argv[2], "r");
  double next_t = -1; char kind[8]; int a = 0, b = 0, c = 0;
  if (sc && fscanf(sc, "%lf %7s", &next_t, kind) == 2) {
    if (!strcmp(kind, "k")) fscanf(sc, "%d %d %d", &a, &b, &c); else fscanf(sc, "%d", &a);
  } else next_t = -1;
  uint8_t prev[16] = {0};
  const int regs[6] = {0x21, 0x24, 0x27, 0x2A, 0x33, 0};
  for (;;) {
    double now = avr->cycle / 16.0;
    if (now > limit) break;
    while (next_t >= 0 && now >= next_t) {
      if (!strcmp(kind, "k")) contacts[a - 21][b] = c;
      else avr_raise_irq(rx, a);
      if (fscanf(sc, "%lf %7s", &next_t, kind) == 2) {
        if (!strcmp(kind, "k")) fscanf(sc, "%d %d %d", &a, &b, &c); else fscanf(sc, "%d", &a);
      } else next_t = -1;
      memset(prev, 0xEE, sizeof prev);   // wymus przeliczenie
    }
    int changed = 0;
    for (int i = 0; i < 5; i++) {
      uint8_t d = avr->data[regs[i]], p = avr->data[regs[i] + 1];
      if (d != prev[2 * i] || p != prev[2 * i + 1]) { prev[2 * i] = d; prev[2 * i + 1] = p; changed = 1; }
    }
    if (changed) {
      apply();
      static FILE *tr = NULL; static int lastx2 = 0;
      if (getenv("TRACE")) {
        if (!tr) tr = fopen("trace.txt", "w");
        int x2 = driven_low(X[1]);
        if (x2 && !lastx2) fprintf(tr, "%.2f\n", avr->cycle / 16.0);
        lastx2 = x2;
      }
    }
    int st = avr_run(avr);
    if (st == cpu_Done || st == cpu_Crashed) { fprintf(stderr, "cpu stop %d\n", st); break; }
  }
  fclose(out);
  return 0;
}
