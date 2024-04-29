import yaml

class MQTTConfig:
    def __init__(self, host, username=None, password=None):
        self.host = host
        self.username = username
        self.password = password

    @classmethod
    def from_yaml(cls, yaml_data):
        return cls(**yaml_data)

class Component:
    def __init__(self, type, unique_id, topic=None, device_class=None, state_class=None, unit_of_measurement=None, access_mode=None, modbus_address=None):
        self.type = type
        self.unique_id = unique_id
        self.topic = topic
        self.device_class = device_class
        self.state_class = state_class
        self.unit_of_measurement = unit_of_measurement
        self.access_mode = access_mode
        self.modbus_address = modbus_address

    @classmethod
    def from_yaml(cls, yaml_data):
        return cls(**yaml_data)

class Device:
    def __init__(self, name, topic, components):
        self.name = name
        self.topic = topic
        self.components = components

    @classmethod
    def from_yaml(cls, yaml_data):
        name = yaml_data.get('name')
        components = [Component.from_yaml(component_data) for component_data in yaml_data.get('components', [])]
        return cls(name, yaml_data.get('topic'), components)

def deserialize(file_path):
    try:
        with open(file_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
            
            mqtt_config = MQTTConfig.from_yaml(yaml_data.get('mqtt_config', {}))
            devices = [Device.from_yaml(device_data) for device_data in yaml_data.get('devices', [])]

            return mqtt_config, devices
    except FileNotFoundError:
        print("Error: File not found.")
    except yaml.YAMLError as exc:
        print("Error in YAML format:", exc)

file_path = 'config.yaml'
mqtt_config, devices = deserialize(file_path)

if mqtt_config:
    # Print MQTT config
    print("MQTT Config:")
    print("Host:", mqtt_config.host)
    print("Username:", mqtt_config.username)
    print("Password:", mqtt_config.password)

if devices:
    # Print devices
    print("\nDevices:")
    for device in devices:
        print("Device Name:", device.name)
        print("Device Topic:", device.topic)
        print("Components:")
        for component in device.components:
            print("  Type:", component.type)
            print("  Unique ID:", component.unique_id)
            print("  Topic:", component.topic)
            print("  Device Class:", component.device_class)
            print("  State Class:", component.state_class)
            print("  Unit of Measurement:", component.unit_of_measurement)
            print("  Access Mode:", component.access_mode)
            print("  Modbus Address:", component.modbus_address)
            print()
