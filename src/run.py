from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin
import json
from jsonpath_ng import parse
import jsonata
import modbus2mqtt as modbus2mqtt
from logger import Logger

app = Flask(__name__)
cors = CORS(app, origins=["http://localhost:3000"])

def sigterm_handler(signal, frame):
    Logger.info("Received SIGTERM. Exiting gracefully.")
    modbus2mqtt.stop()

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

@app.route('/service/start', methods=["POST", "GET"])
def start_service():
    modbus2mqtt.start()
    return jsonify({'message': 'Service started'})

@app.route('/service/stop', methods=["POST", "GET"])
def stop_service():
    modbus2mqtt.stop()
    return jsonify({'message': 'Service stopped'})

@app.route('/mqttconfig', methods=["GET"])
def get_mqtt_config():
    try:
        transform = jsonata.Context()
        template = "$.mqtt_config"
        result = transform(template, config)
        return result
    except:
        return jsonify({'error': 'Book not found'}), 404

@app.route('/devices', methods=["GET"])
def get_devices():
    try:
        transform = jsonata.Context()
        template = '''$map($.devices, function($item) { {"name": $item.name, "unique_id": $item.unique_id} })'''
        result = transform(template, config)
        return result
    except:
        return jsonify({'error': 'Book not found'}), 404

@app.route('/devices/<string:device_name>', methods=["GET"])
def get_device(device_name):
    try:
        transform = jsonata.Context()
        template = f'$.devices[unique_id="{device_name}"]'
        result = transform(template, config)
        return result
    except:
        return jsonify({'error': 'Device not found'}), 404

@app.route('/devices/<string:device_name>/components', methods=["GET"])
def get_components(device_name):
    try:
        transform = jsonata.Context()
        template = f'$.devices[unique_id="{device_name}"].components'
        result = transform(template, config)
        return result
    except:
        return jsonify({'error': 'Book not found'}), 404

@app.route('/devices/<string:device_name>/components/<string:component_name>', methods=["GET"])
def get_component(device_name, component_name):
    try:
        transform = jsonata.Context()
        template = f'$.devices[unique_id="{device_name}"].components[unique_id="{component_name}"]'
        result = transform(template, config)
        return result
    except:
        return jsonify({'error': 'Component not found'}), 404

if __name__ == '__main__':
    app.run(host="0.0.0.0")


# # GET request to fetch all books
# @app.route('/books', methods=["GET"])
# def get_books():
#     return jsonify(books)

# # GET request to fetch a specific book by its ID
# @app.route('/books/<int:book_id>', methods=["GET"])
# def get_book(book_id):
#     book = next((book for book in books if book['id'] == book_id), None)
#     if book:
#         return jsonify(book)
#     else:
#         return jsonify({'error': 'Book not found'}), 404

# # POST request to add a new book
# @app.route('/books', methods=['POST'])
# def add_book():
#     new_book = request.json
#     books.append(new_book)
#     return jsonify({'message': 'Book added successfully'}), 201

# # PUT request to update an existing book
# @app.route('/books/<int:book_id>', methods=['PUT'])
# def update_book(book_id):
#     book = next((book for book in books if book['id'] == book_id), None)
#     if book:
#         book.update(request.json)
#         return jsonify({'message': 'Book updated successfully'})
#     else:
#         return jsonify({'error': 'Book not found'}), 404

# # DELETE request to delete a book by its ID
# @app.route('/books/<int:book_id>', methods=['DELETE'])
# def delete_book(book_id):
#     global books
#     books = [book for book in books if book['id'] != book_id]
#     return jsonify({'message': 'Book deleted successfully'})


