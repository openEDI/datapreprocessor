import os
import shlex
import signal
import subprocess
import time
from importlib.util import find_spec

import pytest
import requests


@pytest.fixture
def init():
	spec=find_spec('datapreprocessor.microservice.server')
	proc=subprocess.Popen(shlex.split(f'python3 {spec.origin}'),preexec_fn=os.setpgrp)
	time.sleep(3)
	yield
	# better than proc.kill()
	os.killpg(os.getpgid(proc.pid), signal.SIGTERM)


def test_dataimputation(init):
	payload={'static_inputs':{},'input_mapping':{}}
	payload['static_inputs']={'casename':'case123',\
		'monitored_nodes':['60.1'],'initial_measurements':{'60.1':1.0}}
	payload['input_mapping']={'powers_real':'','powers_imaginary':''}

	url='http://127.0.0.1:5000'
	res=requests.post(url=url+'/run/dataimputation',json=payload)
	assert res.status_code==200
	data=res.json()

	res=requests.get(url=url+'/status',params={'uuid':data['uuid']})
	assert res.status_code==200

	res=requests.get(url=url+'/results',params={'uuid':data['uuid']})
	assert res.status_code==200





