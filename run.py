import asyncio
from datetime import datetime
import json
import logging
import os
import random
import sys
import schedule
import time
from urllib.parse import urlparse
from pymodbus.client.tcp import ModbusTcpClient as ModbusClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.payload import BinaryPayloadDecoder
from paho.mqtt import client as mqtt
from paho.mqtt import enums

_LOGGER: logging.Logger = logging.getLogger(__name__)
_LOGGER.addHandler(logging.StreamHandler(sys.stdout))
CONSOLE: logging.Logger = logging.getLogger("console")
CONSOLE.addHandler(logging.StreamHandler(sys.stdout))
CONSOLE.setLevel(logging.INFO)

MQTT_URI = os.getenv("MQTT_URI");
MQTT_HOST = urlparse(MQTT_URI).hostname
MQTT_PORT = urlparse(MQTT_URI).port or 1883
MQTT_TOPIC = os.getenv("MQTT_TOPIC");
MQTT_USERNAME = os.getenv("MQTT_USERNAME");
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD");
MODBUS_URI = os.getenv("MODBUS_URI");
MODBUS_HOST = urlparse(MODBUS_URI).hostname
MODBUS_PORT = urlparse(MODBUS_URI).port or 502
MODBUS_UNIT_ID = os.getenv("MODBUS_UNIT_ID");
DEVICE_NAME = os.getenv("DEVICE_NAME");

CLIENT_ID = f'python-mqtt-{random.randint(0, 1000)}'
FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60

ENTITY_NAMES = {
    "aussentemperatur": f"{MQTT_TOPIC}_aussentemperatur",
    "raumtemperatur": f"{MQTT_TOPIC}_raumtemperatur",
    "luftfeuchtigkeit": f"{MQTT_TOPIC}_luftfeuchtigkeit",
    "betriebsart": f"{MQTT_TOPIC}_betriebsart",
    "luftungsstufe": f"{MQTT_TOPIC}_luftungsstufe",
    "stossluftung": f"{MQTT_TOPIC}_stossluftung",
    "einschlaffunktion": f"{MQTT_TOPIC}_einschlaffunktion"
}

MODBUS_ADDRESSES = {
    "aussentemperatur": 703,
    "raumtemperatur": 700,
    "luftfeuchtigkeit": 750,
    "betriebsart": 550,
    "luftungsstufe": 554,
    "stossluftung": 551,
    "einschlaffunktion": 559,
};

def print_env():
    print(f"MQTT_URI: {MQTT_URI}")
    print(f"MQTT_HOST: {MQTT_HOST}")
    print(f"MQTT_PORT: {MQTT_PORT}")
    print(f"MQTT_USERNAME: {MQTT_USERNAME}")
    print(f"MQTT_PASSWORD: {MQTT_PASSWORD}")
    print(f"MQTT_TOPIC: {MQTT_TOPIC}")
    print(f"MODBUS_URI: {MODBUS_URI}")
    print(f"MODBUS_HOST: {MODBUS_HOST}")
    print(f"MODBUS_PORT: {MODBUS_PORT}")
    print(f"MODBUS_UNIT_ID: {MODBUS_UNIT_ID}")
    print(f"CLIENT_ID: {CLIENT_ID}")
    print(f"DEVICE_NAME: {DEVICE_NAME}")

def connect_mqtt():
    client = mqtt.Client(enums.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(MQTT_HOST, MQTT_PORT)
    return client

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker!")
    else:
        print("Failed to connect, return code %d\n", reason_code)

def on_disconnect(client, userdata, flags, reason_code, properties):
    logging.info("Disconnected with result code: %s", reason_code)
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

def announce_sensor( mqtt_client: mqtt.Client, topic: str, name: str, unique_id: str, state_topic: str, value_template: str, device_class = None, state_class = None, unit_of_measurement: str = None, json_attributes_topic = None ):
    msg = {
        "name": name,
        "state_topic": state_topic,
        "value_template": value_template,
        "state_class": state_class,
        "unique_id": unique_id
    }
    if device_class != None: msg["device_class"] = device_class
    if unit_of_measurement != None: msg["unit_of_measurement"] = unit_of_measurement
    if json_attributes_topic != None: msg["json_attributes_topic"] = json_attributes_topic
    CONSOLE.info(f"Announcing sensor: {msg}")
    CONSOLE.info("")
    mqtt_client.publish( topic, json.dumps( msg ) )

def announce_sensors(mqtt_client):

    # Announcing Entity 'raumtemperatur'
    announce_sensor(
        mqtt_client=mqtt_client,
        topic=f"homeassistant/sensor/{MQTT_TOPIC}/raumtemperatur/config",
        name=ENTITY_NAMES.get("raumtemperatur", None),
        unique_id=f"{DEVICE_NAME} Raumtemperatur",
        state_topic=f"homeassistant/sensor/{MQTT_TOPIC}/raumtemperatur/state",
        value_template=None,
        device_class="temperature",
        state_class="Measurement",
        unit_of_measurement="°C"
    )

    # Announcing Entity 'aussentemperatur'
    announce_sensor(
        mqtt_client=mqtt_client,
        topic=f"homeassistant/sensor/{MQTT_TOPIC}/aussentemperatur/config",
        name=ENTITY_NAMES.get("aussentemperatur", None),
        unique_id=f"{DEVICE_NAME} Aussentemperatur",
        state_topic=f"homeassistant/sensor/{MQTT_TOPIC}/aussentemperatur/state",
        value_template=None,
        device_class="temperature",
        state_class="Measurement",
        unit_of_measurement="°C"
    )

    # Announcing Entity 'luftfeuchtigkeit'
    announce_sensor(
        mqtt_client=mqtt_client,
        topic=f"homeassistant/sensor/{MQTT_TOPIC}/luftfeuchtigkeit/config",
        name=ENTITY_NAMES.get("luftfeuchtigkeit", None),
        unique_id=f"{DEVICE_NAME} Luftfeuchtigkeit",
        state_topic=f"homeassistant/sensor/{MQTT_TOPIC}/luftfeuchtigkeit/state",
        value_template=None,
        device_class="humidity",
        state_class="Measurement",
        unit_of_measurement="%"
    )

    # Announcing Entity 'betriebsart'
    announce_sensor(
        mqtt_client=mqtt_client,
        topic=f"homeassistant/sensor/{MQTT_TOPIC}/betriebsart/config",
        name=ENTITY_NAMES.get("betriebsart", None),
        unique_id=f"{DEVICE_NAME} Betriebsart",
        state_topic=f"homeassistant/sensor/{MQTT_TOPIC}/betriebsart/state",
        value_template=None,
        device_class=None,
        state_class=None,
        unit_of_measurement=None
    )

    # Announcing Entity 'luftungsstufe'
    announce_sensor(
        mqtt_client=mqtt_client,
        topic=f"homeassistant/sensor/{MQTT_TOPIC}/luftungsstufe/config",
        name=ENTITY_NAMES.get("luftungsstufe", None),
        unique_id=f"{DEVICE_NAME} Luftungsstufe",
        state_topic=f"homeassistant/sensor/{MQTT_TOPIC}/luftungsstufe/state",
        value_template=None,
        device_class=None,
        state_class=None,
        unit_of_measurement=None
    )

    # Announcing Entity 'stossluftung'
    announce_sensor(
        mqtt_client=mqtt_client,
        topic=f"homeassistant/binary_sensor/{MQTT_TOPIC}/stossluftung/config",
        name=ENTITY_NAMES.get("stossluftung", None),
        unique_id=f"{DEVICE_NAME} Stossluftung",
        state_topic=f"homeassistant/binary_sensor/{MQTT_TOPIC}/stossluftung/state",
        value_template=None,
        device_class=None,
        state_class=None,
        unit_of_measurement=None
    )

    # Announcing Entity 'einschlaffunktion'
    announce_sensor(
        mqtt_client=mqtt_client,
        topic=f"homeassistant/binary_sensor/{MQTT_TOPIC}/einschlaffunktion/config",
        name=ENTITY_NAMES.get("einschlaffunktion", None),
        unique_id=f"{DEVICE_NAME} Einschlaffunktion",
        state_topic=f"homeassistant/binary_sensor/{MQTT_TOPIC}/einschlaffunktion/state",
        value_template=None,
        device_class=None,
        state_class=None,
        unit_of_measurement=None
    )

async def write(address, value):
    CONSOLE.info(f"START Writing value '{value}' to address '{address}'")
    connection = ModbusClient(MODBUS_HOST, port=MODBUS_PORT)
    connection.connect()
    try:
        buffer = BinaryPayloadBuilder(endian=Endian.Big)
        buffer.add_16bit_int(0)  # Placeholder for the first byte
        buffer.add_16bit_int(value)
        connection.write_registers(MODBUS_ADDRESSES.get(address), buffer.build())
    except Exception as e:
        print(f"Error writing value to address {address}: {e}")
    finally:
        connection.close()
    await asyncio.sleep(1)
    CONSOLE.info(f"END Writing value '{value}' to address '{address}'")


def read_and_publish(mqtt_client: mqtt.Client, address, topic, scale=1, precision=1):
    CONSOLE.info(f"START Reading value of '{address}'")
    modbus_client = ModbusClient(MODBUS_HOST, port=MODBUS_PORT)
    modbus_client.connect()
    try:
        result = modbus_client.read_holding_registers(MODBUS_ADDRESSES.get(address), 2)
        if result.isError():
            CONSOLE.error(f"Error reading value from address {address}: {result}")
        else:
            decoder = BinaryPayloadDecoder.fromRegisters(result.registers, endian=Endian.Big)
            value = decoder.decode_16bit_int()
            scaled_value = round(value * scale, precision)
            CONSOLE.info(f"Publishing value '{scaled_value}' to topic '{topic}'")
            mqtt_client.publish(topic, str(scaled_value))
    except Exception as e:
        print(f"Error reading and publishing value from address {address}: {e}")
    finally:
        modbus_client.close()
    CONSOLE.info(f"END Reading value of '{address}'")

async def main() -> None:
    try:
        
        print_env()
        
        mqtt_client = connect_mqtt()
        mqtt_client.loop_start()
        
        announce_sensors(mqtt_client)
        
        schedule.every(10).seconds.do(read_and_publish, mqtt_client, "betriebsart", f"homeassistant/sensor/{MQTT_TOPIC}/betriebsart/state", 1, 0)
        schedule.every(10).seconds.do(read_and_publish, mqtt_client, "luftungsstufe", f"homeassistant/sensor/{MQTT_TOPIC}/luftungsstufe/state", 1, 0)
        schedule.every(10).seconds.do(read_and_publish, mqtt_client, "stossluftung", f"homeassistant/binary_sensor/{MQTT_TOPIC}/stossluftung/state", 1, 0)
        schedule.every(10).seconds.do(read_and_publish, mqtt_client, "einschlaffunktion", f"homeassistant/binary_sensor/{MQTT_TOPIC}/einschlaffunktion/state", 1, 0)
        schedule.every(60).seconds.do(read_and_publish, mqtt_client, "raumtemperatur", f"homeassistant/sensor/{MQTT_TOPIC}/raumtemperatur/state", 0.1, 1)
        schedule.every(60).seconds.do(read_and_publish, mqtt_client, "aussentemperatur", f"homeassistant/sensor/{MQTT_TOPIC}/aussentemperatur/state", 0.1, 1)
        schedule.every(60).seconds.do(read_and_publish, mqtt_client, "luftfeuchtigkeit", f"homeassistant/sensor/{MQTT_TOPIC}/luftfeuchtigkeit/state", 1, 0)

        while True:
            schedule.run_pending()
            time.sleep(1)

    except Exception as exception:
        CONSOLE.info(f"{type(exception)}: {exception}")

    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

# run async main
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as err:
        CONSOLE.info(f"{type(err)}: {err}")
