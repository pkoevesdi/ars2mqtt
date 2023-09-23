#!/usr/bin/env python
import sys
import logging
import serial
import time
import functools
import json
from paho.mqtt import client as mqtt

def sendCommand(cmd):
    ser.parity='O'
    ser.write(cmd.to_bytes())
    ser.parity='E'
    if cmd==0x78:
        ser.write(commandbyte.to_bytes())
        ser.write(commandbyte.to_bytes())

ser = serial.Serial('/dev/ttyAMA0', 19200, timeout=0.5)

while not ser.isOpen:
    pass
print("connected to " + ser.portstr)

broker = 'localhost'
port = 1883
client_id = 'RPiZero2W'
username = 'mosquitto'
password = '***REMOVED***'

def on_connect(mqttc, obj, flags, rc):
    print('connected to mqtt broker')

def on_message(mqttc, obj, msg):
    global commandbyte, abfragetime
#    print(msg.topic, msg.payload)
    try:
        topicitem = msg.topic.split("/")[-2]
    except:
        return
    bitnum = tableCommands[topicitem]
    bit = int.from_bytes(msg.payload)-48
    commandbyte &= ~(1 << bitnum) # lösche bit
    commandbyte |= bit << bitnum  # setze bit auf empfangenen Wert
    if topicitem in switchontoo and bit:
        bitnum = tableCommands[switchontoo[topicitem]]
        commandbyte |= 1 << bitnum  # setze bit auf empfangenen Wert
    if topicitem in switchofftoo and ~bit:
        bitnum = tableCommands[switchofftoo[topicitem]]
        commandbyte &= ~(1 << bitnum) # lösche bit
    if topicitem=='pumpe':
        commandbyte &= 0x7f # lösche msb (Wassersensorenabfrage 'ein')
        abfragetime = time.monotonic()

FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60

def on_disconnect(client, userdata, rc):
    logging.info("Disconnected with result code: %s", rc)
    reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
    while reconnect_count < MAX_RECONNECT_COUNT:
        logging.info("Reconnecting in %d seconds...", reconnect_delay)
        time.sleep(reconnect_delay)

        try:
            client.reconnect()
            logging.info("Reconnected successfully!")
            return
        except Exception as err:
            logging.error("%s. Reconnect failed. Retrying...", err)

        reconnect_delay *= RECONNECT_RATE
        reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
        reconnect_count += 1
    logging.info("Reconnect failed after %s attempts. Exiting...", reconnect_count)

mqttc = mqtt.Client()
mqttc.username_pw_set(username, password)
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_disconnect = on_disconnect
mqttc.connect_async(broker, port, 60)
mqttc.reconnect()
mqttc.loop_start()

tableBA={
    "0":{
        "0":{'unique_id':'pumpe','name':'Pumpe','component':'light','icon':'mdi:water-pump'},
        "1":{'unique_id':'licht','name':'Licht','component':'light','icon':'mdi:lightbulb-on-outline'},
        "2":{'unique_id':'aussenlicht','name':'Außenlicht','component':'light','icon':'mdi:wall-sconce-flat'}
        },
    "1":{
        "1":{'unique_id':'frischwasser','component':'sensor','name':'Frischwasser','device_class':'enum','icon':'mdi:car-coolant-level',
#        'value_template':'{% set mapper =  {'\
#            '"0" : "< 1/3",'\
#            '"1" : "1/3 ... 1/2",'\
#            '"2" : "1/2 ... 2/3",'\
#            '"3" : "2/3 ... 3/4",'\
#            '"4" : "> 3/4"} %}'\
#            '{{mapper[value] if value in mapper else "ungültig"}}'
},
        "2":{'unique_id':'frischwasser','component':'sensor'},
        "3":{'unique_id':'frischwasser','component':'sensor'},
        "5":{'unique_id':'grauwasser','name':'Grauwasser','component':'binary_sensor','device_class':'problem'}
        },
    "2":{
        "1":{'unique_id':'sicherung','name':'Sicherung','component':'binary_sensor','device_class':'problem'},
        "5":{'unique_id':'landstrom','name':'Landstrom','component':'binary_sensor','device_class':'plug'},
        "6":{'unique_id':'frischwasser','component':'sensor'}
        }
        }

for bytenum, bytedict in tableBA.items():
    for bitnum, params in bytedict.items():
        if not 'name' in params: continue
        topic='homeassistant/'+params['component']+'/'+params['unique_id']
        payload = {"~":topic,
        "cmd_t": "~/set",
        "stat_t": "~/state",
        "payload_off":0,
        "payload_on":1
        }
        for key, value in params.items():
            payload[key]=value
        if params['component']=='light':
            payload['cmd_t']="~/set"
            mqttc.subscribe(topic+"/set", 0)
        mqttc.publish(topic+'/config', json.dumps(payload),retain=True)
        mqttc.publish(topic+"/state", 0, retain=True)

table78={"1":{'unique_id':'batt_aufbau','name':'Aufbaubatterie','component':'sensor','icon':'mdi:battery','device_class':'voltage','unit_of_measurement':'V','state_class':'measurement'},
"3":{'unique_id':'batt_starter','name':'Starterbatterie','component':'sensor','icon':'mdi:battery','device_class':'voltage','unit_of_measurement':'V','state_class':'measurement'}}

for bytenum, params in table78.items():
    topic = "homeassistant/"+params['component']+"/"+params['unique_id']
    payload = {"~":topic,
    "name": params['name'],
    "stat_t": "~/state",
    "unique_id": params['unique_id'],
    "device": {"identifiers": ["arsbridge"], "name": "Ars" }
    }
    for key, value in params.items():
        payload[key]=value
    mqttc.publish(topic+'/config',json.dumps(payload),retain=True)
    mqttc.publish(topic+"/state", 0, retain=True)

tableCommands={'pumpe':0,'licht':1,'aussenlicht':2}
switchontoo={'aussenlicht':'licht'}
switchofftoo={'licht':'aussenlicht'}

bytesBAold=[0, 0, 0, 0]
bytes78old=[0, 0, 0, 0]
alpha = 0.7
commandbyte = 0x80
commandbyteold = 0
frametime = 10
abfragetime = time.monotonic() - 60

print('entering loop...')

while True:
    lasttime = time.monotonic()
    sendCommand(0xba)
    bytesBA = list(ser.read(6))
#    print([hex(x) for x in bytesBA])
    if len(bytesBA)>=6 and bytesBA[0]==0xba and functools.reduce(lambda x, y: x ^ y, bytesBA[1:6])==0:
        bytesBA=bytesBA[1:5]
#        diffs=sum([[[i, j, (x[0] & 1<<j)>>j] for j in range(8) if (x[0]^x[1]) & 1<<j] for i, x in enumerate(zip(bytesBA,bytesBAold)) if x[0]!=x[1]],[])
#        if diffs:
#            bytesBAold=bytesBA
#            for i in diffs:
#                if str(i[0]) in tableBA and str(i[1]) in tableBA[str(i[0])]:
#                    topic=f"homeassistant/{tableBA[str(i[0])][str(i[1])]['component']}/{tableBA[str(i[0])][str(i[1])]['unique_id']}/state"
#                    if tableBA[str(i[0])][str(i[1])]['component'] == "sensor":
#                        payload = sum([[(bytesBA[int(k1)] & 1<<int(k2))>>int(k2) for k2, v2 in v1.items() if tableBA[k1][k2]['unique_id'] == tableBA[str(i[0])][str(i[1])]['unique_id']] for k1, v1 in tableBA.items()],[]).count(1)
#                    else:
#                        payload = i[2]
#                    mqttc.publish(topic, payload)
        for i1,val in tableBA.items():
            for i2 in val.items():
                topic=f"homeassistant/{tableBA[i1][i2[0]]['component']}/{tableBA[i1][i2[0]]['unique_id']}/state"
                if tableBA[i1][i2[0]]['component'] == "sensor":
                    payload = sum([[(bytesBA[int(k1)] & 1<<int(k2))>>int(k2) for k2, v2 in v1.items() if tableBA[k1][k2]['unique_id'] == tableBA[i1][i2[0]]['unique_id']] for k1, v1 in tableBA.items()],[]).count(1)
                else:
                    payload = (bytesBA[int(i1)] & 1<<int(i2[0]))>>int(i2[0])
                mqttc.publish(topic, payload)
    ser.reset_input_buffer()
    while time.monotonic() - lasttime <= 0.008:
        pass

    sendCommand(0x78)
    bytes78 = list(ser.read(8))
#    print([hex(x) for x in bytes78])
    if len(bytes78)>=8 and bytes78[0]==0x78 and functools.reduce(lambda x, y: x ^ y, bytes78[3:8])==0:
        bytes78=bytes78[3:7]
        # Exponentielle Glättung:
        for i in table78.items():
            bytes78[int(i[0])] = int(alpha*bytes78[int(i[0])]+(1-alpha)*bytes78old[int(i[0])])
#        diffs=[[i, x[0]/10] for i, x in enumerate(zip(bytes78,bytes78old)) if x[0]!=x[1]]
#        if diffs:
#            bytes78old=bytes78
#            for i in diffs:
#                if str(i[0]) in table78:
#                    mqttc.publish(f"homeassistant/sensor/{table78[str(i[0])]['unique_id']}/state", i[1])
            bytes78old=bytes78
            mqttc.publish(f"homeassistant/sensor/{i[1]['unique_id']}/state", bytes78[int(i[0])]/10)
    ser.reset_input_buffer()

    if commandbyte & 0x80 and time.monotonic() - abfragetime > 60:
        commandbyte &= 0x7f # lösche msb (Wassersensorenabfrage 'ein')
        abfragetime = time.monotonic()
    elif ~commandbyte & 0x80 and time.monotonic() - abfragetime > 1:
        commandbyte |= 0x80 # setze msb (Wassersensorenabfrage 'aus')

    while time.monotonic() - lasttime <= 0.008:
        pass
    while time.monotonic() - lasttime <= frametime and len(bytesBA)>0 and commandbyte&0x7f == bytesBA[0]&0x7f:
        pass
#    if time.monotonic() - lasttime > 1:
#        commandbyteold = commandbyte

ser.close()
mqttc.loop_stop()
print("closed")
