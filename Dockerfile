FROM python:3.13.0a6-alpine3.19
RUN apk add build-base
WORKDIR /app
RUN mkdir src
COPY src ./src
COPY config.json ./
RUN pip3 install schedule pymodbus paho-mqtt pyyaml debugpy jsonpath-ng flask flask-cors jsonata
CMD ["python", "src/run.py"]