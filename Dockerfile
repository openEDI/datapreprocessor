FROM ubuntu:24.04
RUN apt update && apt -y upgrade

# python deps
RUN apt install -y python3 python3-pip python3-virtualenv zip wget git
RUN mkdir ~/venv && cd ~/venv && virtualenv datapreprocessor

# install
COPY . /home/datapreprocessor
RUN /bin/bash -c 'source ~/venv/datapreprocessor/bin/activate && cd /home/datapreprocessor/ && python3 -m pip install -e .'

ENTRYPOINT ["/bin/bash", "-c","source ~/venv/datapreprocessor/bin/activate && python3 /home/datapreprocessor/datapreprocessor/microservice/server.py"]
