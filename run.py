import asyncio
from datetime import datetime
import json
import logging
import os
import random
import sys
import signal
import schedule
import time
from urllib.parse import urlparse
from pymodbus.client.tcp import ModbusTcpClient as ModbusClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.payload import BinaryPayloadDecoder
from paho.mqtt import client as MqttClient
from paho.mqtt import enums as MqttEnums
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes
from config import deserialize

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
CLIENT_ID = f"python-mqtt-{random.randint(0, 1000)}"

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

MQTT_SUBSCRIPTIONS = {
    "betriebsart": f"homeassistant/sensor/{MQTT_TOPIC}/betriebsart/state",
    "luftungsstufe": f"homeassistant/sensor/{MQTT_TOPIC}/luftungsstufe/state",
    "stossluftung": f"homeassistant/binary_sensor/{MQTT_TOPIC}/stossluftung/state",
    "einschlaffunktion": f"homeassistant/binary_sensor/{MQTT_TOPIC}/einschlaffunktion/state"
}

mqtt_client: MqttClient = None
modbus_client: ModbusClient = None

async def main() -> None:
    global mqtt_client

    try:
        print_env()
        mqtt_config, devices = deserialize("config.yaml")
        init_mqtt_client()
        announce_sensors(devices)
        poll_mqtt_topics()
        while True:
            schedule.run_pending()
            time.sleep(1)

    except Exception as exception:
        CONSOLE.info(f"{type(exception)}: {exception}")

    finally:
        if mqtt_client != None and mqtt_client.is_connected():
            mqtt_client.loop_stop()
            mqtt_client.disconnect()

def print_env():
    CONSOLE.info(f"MQTT_URI: {MQTT_URI}")
    CONSOLE.info(f"MQTT_HOST: {MQTT_HOST}")
    CONSOLE.info(f"MQTT_PORT: {MQTT_PORT}")
    CONSOLE.info(f"MQTT_USERNAME: {MQTT_USERNAME}")
    CONSOLE.info(f"MQTT_PASSWORD: {MQTT_PASSWORD}")
    CONSOLE.info(f"MQTT_TOPIC: {MQTT_TOPIC}")
    CONSOLE.info(f"MODBUS_URI: {MODBUS_URI}")
    CONSOLE.info(f"MODBUS_HOST: {MODBUS_HOST}")
    CONSOLE.info(f"MODBUS_PORT: {MODBUS_PORT}")
    CONSOLE.info(f"MODBUS_UNIT_ID: {MODBUS_UNIT_ID}")
    CONSOLE.info(f"CLIENT_ID: {CLIENT_ID}")
    CONSOLE.info(f"DEVICE_NAME: {DEVICE_NAME}")
    CONSOLE.info("")

def init_mqtt_client():
    global mqtt_client
    mqtt_client = MqttClient.Client(MqttEnums.CallbackAPIVersion.VERSION2, protocol=MqttEnums.MQTTProtocolVersion.MQTTv5);
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    mqtt_client.on_connect = on_connect_mqtt
    mqtt_client.on_disconnect = on_disconnect_mqtt
    mqtt_client.on_message = on_message_mqtt
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, properties=None)
    subscribe_mqtt_topics()
    mqtt_client.loop_start()

def subscribe_mqtt_topics():
    global mqtt_client
    for topic in MQTT_SUBSCRIPTIONS.values():
        CONSOLE.info(f"Subscribing to topic '{topic}'")
        mqtt_client.subscribe(topic, properties=None)
    CONSOLE.info("")

def poll_mqtt_topics():
    schedule.every(10).seconds.do(read_and_publish, "betriebsart", f"homeassistant/sensor/{MQTT_TOPIC}/betriebsart/state", 1, 0)
    schedule.every(10).seconds.do(read_and_publish, "luftungsstufe", f"homeassistant/sensor/{MQTT_TOPIC}/luftungsstufe/state", 1, 0)
    schedule.every(10).seconds.do(read_and_publish, "stossluftung", f"homeassistant/binary_sensor/{MQTT_TOPIC}/stossluftung/state", 1, 0)
    schedule.every(10).seconds.do(read_and_publish, "einschlaffunktion", f"homeassistant/binary_sensor/{MQTT_TOPIC}/einschlaffunktion/state", 1, 0)
    schedule.every(60).seconds.do(read_and_publish, "raumtemperatur", f"homeassistant/sensor/{MQTT_TOPIC}/raumtemperatur/state", 0.1, 1)
    schedule.every(60).seconds.do(read_and_publish, "aussentemperatur", f"homeassistant/sensor/{MQTT_TOPIC}/aussentemperatur/state", 0.1, 1)
    schedule.every(60).seconds.do(read_and_publish, "luftfeuchtigkeit", f"homeassistant/sensor/{MQTT_TOPIC}/luftfeuchtigkeit/state", 1, 0)

def publish_mqtt(topic, value):
    global mqtt_client
    CONSOLE.info(f"Publishing value '{value}' to topic '{topic}'")
    properties = Properties(PacketTypes.PUBLISH)
    properties.UserProperty = [("publisher", "powerbox2mqtt")]
    mqtt_client.publish(topic, str(value), properties=properties)

def on_message_mqtt(client, userdata, message):
    if is_own_message(message) == False:
        value = int(message.payload.decode("utf-8"))
        if message.topic == MQTT_SUBSCRIPTIONS.get("betriebsart"):
            write("betriebsart", value)
        elif message.topic == MQTT_SUBSCRIPTIONS.get("luftungsstufe"):
            write("luftungsstufe", value)
        elif message.topic == MQTT_SUBSCRIPTIONS.get("stossluftung"):
            write("stossluftung", value)
        elif message.topic == MQTT_SUBSCRIPTIONS.get("einschlaffunktion"):
            write("einschlaffunktion", value)

def is_own_message(message):
    if hasattr(message.properties, "UserProperty"):
        for tuple in message.properties.UserProperty:
            key, value = tuple
            if key == "publisher" and value == "powerbox2mqtt":
                return True
    return False

def on_connect_mqtt(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT Broker!")
    else:
        print("Failed to connect, return code %d\n", reason_code)
        terminate()

def on_disconnect_mqtt(client, userdata, flags, reason_code, properties):
    terminate()

def announce_sensor(topic: str, name: str, unique_id: str, state_topic: str, value_template: str, device_class = None, state_class = None, unit_of_measurement: str = None, json_attributes_topic = None ):
    global mqtt_client
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

def announce_sensors(devices):
    
    for device in devices:
        for component in device.components:
            if component.access_mode == "read":
                announce_sensor(
                    topic=f"{device.topic}/{component.type}/{device.name}/{component.topic}/config",
                    name=ENTITY_NAMES.get("raumtemperatur", None),
                    unique_id=f"{DEVICE_NAME} Raumtemperatur",
                    state_topic=f"{device.topic}/{component.type}/{device.name}/{component.topic}/state",
                    value_template=None,
                    device_class=component.device_class,
                    state_class=component.state_class,
                    unit_of_measurement=component.unit_of_measurement
                )
    
    # # Announcing Entity "raumtemperatur"
    # announce_sensor(
    #     topic=f"homeassistant/sensor/{MQTT_TOPIC}/raumtemperatur/config",
    #     name=ENTITY_NAMES.get("raumtemperatur", None),
    #     unique_id=f"{DEVICE_NAME} Raumtemperatur",
    #     state_topic=f"homeassistant/sensor/{MQTT_TOPIC}/raumtemperatur/state",
    #     value_template=None,
    #     device_class="temperature",
    #     state_class="Measurement",
    #     unit_of_measurement="°C"
    # )

    # # Announcing Entity "aussentemperatur"
    # announce_sensor(
    #     topic=f"homeassistant/sensor/{MQTT_TOPIC}/aussentemperatur/config",
    #     name=ENTITY_NAMES.get("aussentemperatur", None),
    #     unique_id=f"{DEVICE_NAME} Aussentemperatur",
    #     state_topic=f"homeassistant/sensor/{MQTT_TOPIC}/aussentemperatur/state",
    #     value_template=None,
    #     device_class="temperature",
    #     state_class="Measurement",
    #     unit_of_measurement="°C"
    # )

    # # Announcing Entity "luftfeuchtigkeit"
    # announce_sensor(
    #     topic=f"homeassistant/sensor/{MQTT_TOPIC}/luftfeuchtigkeit/config",
    #     name=ENTITY_NAMES.get("luftfeuchtigkeit", None),
    #     unique_id=f"{DEVICE_NAME} Luftfeuchtigkeit",
    #     state_topic=f"homeassistant/sensor/{MQTT_TOPIC}/luftfeuchtigkeit/state",
    #     value_template=None,
    #     device_class="humidity",
    #     state_class="Measurement",
    #     unit_of_measurement="%"
    # )

    # # Announcing Entity "betriebsart"
    # announce_sensor(
    #     topic=f"homeassistant/sensor/{MQTT_TOPIC}/betriebsart/config",
    #     name=ENTITY_NAMES.get("betriebsart", None),
    #     unique_id=f"{DEVICE_NAME} Betriebsart",
    #     state_topic=f"homeassistant/sensor/{MQTT_TOPIC}/betriebsart/state",
    #     value_template=None,
    #     device_class=None,
    #     state_class=None,
    #     unit_of_measurement=None
    # )

    # # Announcing Entity "luftungsstufe"
    # announce_sensor(
    #     topic=f"homeassistant/sensor/{MQTT_TOPIC}/luftungsstufe/config",
    #     name=ENTITY_NAMES.get("luftungsstufe", None),
    #     unique_id=f"{DEVICE_NAME} Luftungsstufe",
    #     state_topic=f"homeassistant/sensor/{MQTT_TOPIC}/luftungsstufe/state",
    #     value_template=None,
    #     device_class=None,
    #     state_class=None,
    #     unit_of_measurement=None
    # )

    # # Announcing Entity "stossluftung"
    # announce_sensor(
    #     topic=f"homeassistant/binary_sensor/{MQTT_TOPIC}/stossluftung/config",
    #     name=ENTITY_NAMES.get("stossluftung", None),
    #     unique_id=f"{DEVICE_NAME} Stossluftung",
    #     state_topic=f"homeassistant/binary_sensor/{MQTT_TOPIC}/stossluftung/state",
    #     value_template=None,
    #     device_class=None,
    #     state_class=None,
    #     unit_of_measurement=None
    # )

    # # Announcing Entity "einschlaffunktion"
    # announce_sensor(
    #     topic=f"homeassistant/binary_sensor/{MQTT_TOPIC}/einschlaffunktion/config",
    #     name=ENTITY_NAMES.get("einschlaffunktion", None),
    #     unique_id=f"{DEVICE_NAME} Einschlaffunktion",
    #     state_topic=f"homeassistant/binary_sensor/{MQTT_TOPIC}/einschlaffunktion/state",
    #     value_template=None,
    #     device_class=None,
    #     state_class=None,
    #     unit_of_measurement=None
    # )

def write(address, value):
    global mqtt_client
    CONSOLE.info(f"START Writing value '{value}' to address '{address}'")
    modbus_client = ModbusClient(MODBUS_HOST, port=MODBUS_PORT)
    if modbus_client.connect() == True:
        try:
            # buffer = BinaryPayloadBuilder(endian=Endian.Big)
            # buffer.add_16bit_int(0)  # Placeholder for the first byte
            # buffer.add_16bit_int(value)
            modbus_client.write_registers(MODBUS_ADDRESSES.get(address), value)
        except Exception as e:
            print(f"Error writing value to address {address}: {e}")
        finally:
            modbus_client.close()
            modbus_client = None
    time.sleep(1)
    CONSOLE.info(f"END Writing value '{value}' to address '{address}'")
    CONSOLE.info("")

def read_and_publish(address, topic, scale=1, precision=1):
    CONSOLE.info(f"START Reading value of '{address}'")
    modbus_client = ModbusClient(MODBUS_HOST, port=MODBUS_PORT)
    if modbus_client.connect() == True:
        try:
            result = modbus_client.read_holding_registers(MODBUS_ADDRESSES.get(address), 1)
            if result.isError():
                CONSOLE.error(f"Error reading value from address {address}: {result}")
            else:
                value = result.registers[0]
                scaled_value = round(value * scale, precision)
                publish_mqtt(topic, scaled_value)
        except Exception as e:
            print(f"Error reading and publishing value from address {address}: {e}")
        finally:
            modbus_client.close()
            modbus_client = None
    time.sleep(1)
    CONSOLE.info(f"END Reading value of '{address}'")
    CONSOLE.info("")

def sigterm_handler(signal, frame):
    terminate()
    
def terminate():
    CONSOLE.info("Received SIGTERM. Exiting gracefully.")
    if modbus_client != None and modbus_client.connected:
        modbus_client.close()
    if mqtt_client != None:
        mqtt_client.disconnect();
    sys.exit(0)

# run async main
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as err:
        CONSOLE.info(f"{type(err)}: {err}")
