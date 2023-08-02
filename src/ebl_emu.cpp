// program to emulate the slave of the Arsilicii EBL to develop the master side

#include <Arduino.h>

byte cnt = 0;
byte read_byte = 0;
byte a = 0;
byte U = 0;
char answer78[] = {0x00, 0x7D, 0x00, 0x7C, 0x01};
char answerBA[] = {0x02, 0x1F, 0x00, 0x01, 0x1C};

void calcchecksum(char, byte);

void setup()
{
    Serial.begin(115200, SERIAL_8O1);
    while (!Serial)
        ;
}

void loop()
{
    if (Serial.available())
    {
        read_byte = Serial.read();
        if (read_byte == 0xBA && cnt == 0)
        {
            // generate some arbitrary freshwater data
            answerBA[1] = answerBA[1] & 0b11110001; // delete the fresh water bits
            byte freshwater = round((millis() % 3000) / 1000);
            answerBA[1] = answerBA[1] | (((1 << freshwater) | ((1 << freshwater) - 1)) & 0b1110);

            // generate some arbitrary fuse status
            answerBA[2] = answerBA[2] & 0b11111101; // delete the fuse status bit
            answerBA[2] = answerBA[2] | (round((millis() % 1000) / 1000) << 1);

            calcchecksum(answerBA, 4);
            Serial.write(answerBA, sizeof(answerBA) / sizeof(answerBA[0]));
        }
        else if (read_byte == 0x78 && cnt == 0)
        {
            cnt = 2;
        }
        else if (cnt == 2)
        {
            a = read_byte;
            cnt--;
        }
        else if (cnt == 1)
        {
            cnt = 0;
            if (a == read_byte)
            {
                // generate some arbitrary voltages
                answer78[1] = 100 + round((millis() % 2000) / 40);
                answer78[3] = 250 - answer78[1];
                calcchecksum(answer78, 4);
                Serial.write(answer78, sizeof(answer78) / sizeof(answer78[0]));

                // set the devices' status according to the command
                answerBA[0] = a && 0b00000111;
            }
        }
    }
}

void calcchecksum(char *data, byte len)
{
    data[len] = 0;
    for (int i = 0; i < len; i++)
    {
        data[len] ^= data[i];
    }
}