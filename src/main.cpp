#include <Arduino.h>
#define LIN_RX 16
#define LIN_TX 17
byte a = 0;

void setup()
{
  Serial.begin(115200);
  while (!Serial)
    ;
  Serial1.begin(19200, SERIAL_8E1, LIN_RX, LIN_TX);
  while (!Serial1)
    ;
}

void loop()
{
  if (Serial1.available())
  {
    a = Serial1.read();
    if (a == 0x49)
      Serial.println();
    if (a <= 15)
      Serial.print("0");
    Serial.print(a, HEX);
    Serial.print(" ");

  }

}
