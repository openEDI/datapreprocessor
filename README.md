[![Build](https://github.com/openEDI/datapreprocessor/actions/workflows/build.yml/badge.svg)](https://github.com/openEDI/datapreprocessor/actions/workflows/build.yml) [![Tests](https://github.com/openEDI/datapreprocessor/actions/workflows/ci.yml/badge.svg)](https://github.com/openEDI/datapreprocessor/actions/workflows/ci.yml)

# Build

docker build -t datapreprocessor:latest .

# Port

The server runs on port 5000

# Notes

* Data model for client to connect with datapreprocessor service [Data Model](datapreprocessor/microservice/data_model.py)

* Client side tests with payload for each endpoint [minimal working example](tests/test_microservice.py)
