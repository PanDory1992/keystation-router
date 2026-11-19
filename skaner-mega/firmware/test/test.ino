// Skaner Mega: test plytki. Mruga dioda L (pin 13) i co 0,5 s wysyla "MEGA OK".
// Nic nie steruje pinami klawiatury: wszystkie zostaja wejsciami.
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  Serial.println(F("TEST v1"));
}

void loop() {
  static unsigned long last = 0;
  unsigned long now = millis();
  if (now - last >= 500) {
    last = now;
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    Serial.print(F("MEGA OK "));
    Serial.println(now);
  }
}
