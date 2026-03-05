import copy
import json
import os
import shlex
import subprocess
import uuid
from http import HTTPStatus
from importlib.util import find_spec

import psutil
from flask import Flask, Response, request

from datapreprocessor.microservice.data_model import (
	InputMappingDataImputation,
	StaticInputsDataImputationExternal,
	StaticInputsDataImputationInternal,
)

procMap={}
spec=find_spec('datapreprocessor.federates.dataimputation.federate_dataimputation')
baseDir=os.path.dirname(os.path.abspath(spec.origin))
dataImputationDefaultStaticInputsInternal=json.load(open(os.path.join(baseDir,'static_inputs.json')))
dataImputationDefaultStaticInputsInternal=StaticInputsDataImputationInternal(\
	**dataImputationDefaultStaticInputsInternal).model_dump()# validate data with data model


#=======================================================================================================================
def run_dataimputation():
	data=request.json
	assert not set(['static_inputs','input_mapping']).difference(data.keys())
	staticInputsExternal=StaticInputsDataImputationExternal(**data['static_inputs']).model_dump()
	inputMapping=InputMappingDataImputation(**data['input_mapping']).model_dump()
	staticInputsInternal=copy.deepcopy(dataImputationDefaultStaticInputsInternal)
	staticInputsInternal.update(staticInputsExternal)

	runUUID=uuid.uuid4().hex

	dirPath=f'/tmp/{runUUID}'
	directive=f'mkdir -p {dirPath} && cp -r {baseDir}/* {dirPath}'
	flag=os.system(directive)
	assert flag==0

	# update based on payload
	json.dump(staticInputsInternal,open(os.path.join(dirPath,'static_inputs.json'),'w'))
	json.dump(inputMapping,open(os.path.join(dirPath,'input_mapping.json'),'w'))

	runPath=os.path.join(dirPath,'federate_dataimputation.py')
	directive=f'python3 {runPath}'
	proc=subprocess.Popen(shlex.split(directive),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
	procMap[runUUID]=proc.pid

	res=Response(status=HTTPStatus.OK)
	res.mimetype='application/json'
	res.response=json.dumps({"success":True,"uuid":runUUID})
	return res


#=======================================================================================================================
def status():
	runUUID = request.args.get('uuid')
	if runUUID in procMap:
		procStatus='completed'
		procExists=psutil.pid_exists(procMap[runUUID])
		if procExists:
			p=psutil.Process(procMap[runUUID])
			if p.status()!='zombie':
				procStatus='running'
		res=Response(status=HTTPStatus.OK)
		res.mimetype='application/json'
		res.response=json.dumps({"success":True,"status":procStatus})
	else:
		res=Response(status=HTTPStatus.BAD_REQUEST)
		res.mimetype='application/json'
		res.response=json.dumps({"success":False,"error":f"UUID {runUUID} does not exist"})
	return res


#=======================================================================================================================
def results():
	runUUID = request.args.get('uuid')
	if runUUID in procMap:
		res=Response(status=HTTPStatus.OK)
		res.mimetype='application/json'
		res.response=json.dumps({"success":True,"data":{}})
	else:
		res=Response(status=HTTPStatus.BAD_REQUEST)
		res.mimetype='application/json'
		res.response=json.dumps({"success":False,"error":f"UUID {runUUID} does not exist"})
	return res


#=======================================================================================================================
if __name__ == '__main__':
	app = Flask(__name__)
	app.add_url_rule(rule='/run/dataimputation',methods=['POST'],view_func=run_dataimputation)
	app.add_url_rule(rule='/status',methods=['GET'],view_func=status)
	app.add_url_rule(rule='/results',methods=['GET'],view_func=results)
	app.run(host='0.0.0.0',port=5000,debug=False,use_reloader=True,threaded=True)


