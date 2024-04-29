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
    def __init__(self, type, name, unique_id, device_class=None, state_class=None, unit_of_measurement=None, access_mode=None, modbus_address=None, poll_interval=60, scale=1, precision=1):
        self.type = type
        self.unique_id = unique_id
        self.name = name
        self.device_class = device_class
        self.state_class = state_class
        self.unit_of_measurement = unit_of_measurement
        self.access_mode = access_mode
        self.modbus_address = modbus_address
        self.poll_interval = poll_interval
        self.scale = scale
        self.precision = precision

    @classmethod
    def from_yaml(cls, yaml_data):
        return cls(**yaml_data)

class Device:
    def __init__(self, name, unique_id, topic, host, unit_id, components):
        self.name = name
        self.unique_id = unique_id;
        self.topic = topic
        self.host = host
        self.unit_id = unit_id
        self.components = components

    @classmethod
    def from_yaml(cls, yaml_data):
        name = yaml_data.get('name')
        unique_id = yaml_data.get('unique_id')
        topic = yaml_data.get('topic')
        host = yaml_data.get('host')
        unit_id = yaml_data.get('unit_id')
        components = [Component.from_yaml(component_data) for component_data in yaml_data.get('components', [])]
        return cls(name, unique_id, topic,host, unit_id, components)

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
