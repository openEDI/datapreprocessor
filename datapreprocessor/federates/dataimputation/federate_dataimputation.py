import os
import sys
import copy
import json
import logging
from importlib.util import find_spec

import tensorflow
import helics as h
import oedisi.types.data_types as OEDISITypes

from datapreprocessor.app.dataimputation.data_imputation_postprocessing import update_window_and_impute

formatStr='%(asctime)s::%(name)s::%(filename)s::%(funcName)s::'+\
	'%(levelname)s::%(message)s::%(threadName)s::%(process)d'
logging.basicConfig(stream=sys.stdout,level=logging.INFO,format=formatStr)
logger=logging.getLogger(__name__)


class DataImputationFederate:

	def __init__(self,config,inputMapping,componentDefinition,staticInputs,federate_name='dataimputation',dt=1):
		self.config=config
		self.staticInputs=staticInputs
		self.inputMapping=inputMapping

		self.config['federate_config']['subscriptions']=[]
		self.config['federate_config']['publications']=[]
		for entry in inputMapping:
			self.config['federate_config']['subscriptions'].append(\
				{'global':True,'type':'string','key':inputMapping[entry]})

		# mapping
		self.mapping={'subid2type':{},'pubid2type':{},'subFunc':{},'pubFunc':{}}

		for entry in componentDefinition['dynamic_inputs']:
			key=inputMapping[entry['port_id']]
			assert entry['type'] in OEDISITypes.__dict__,f'The following type is unavailable {entry["type"]}'
			self.mapping['subid2type'][key]=entry['type']
			self.mapping['subFunc'][key]=OEDISITypes.__dict__[entry['type']]

		for entry in componentDefinition['dynamic_outputs']:
			key=f'{federate_name}/{entry["port_id"]}'
			assert entry['type'] in OEDISITypes.__dict__,f'The following type is unavailable {entry["type"]}'
			self.mapping['pubid2type'][key]=entry['type']
			self.mapping['pubFunc'][key]=OEDISITypes.__dict__[entry['type']]
			self.config['federate_config']['publications'].append({'global':True,'type':'string','key':key})

		self.federate_name = federate_name

		self.dt=dt
		logger.info('completed init')


#=======================================================================================================================
	def setup(self,testMode=False):
		# setup model
		spec=find_spec('datapreprocessor.app.dataimputation')
		self.model_path=os.path.join(spec.submodule_search_locations[0],'model',self.staticInputs['model_path'])
		self.model_format = self.staticInputs['model_format']
		self.window_size = self.staticInputs['window_size']
		self.input_features = self.staticInputs['input_features']
		self.window_id = 0

		# node data
		self.node_data_dict = {'pdemand':{},'qdemand':{}}
		pdemand=self.node_data_dict['pdemand']
		qdemand=self.node_data_dict['qdemand']
		initMeasurement=self.staticInputs['initial_measurements']

		for node_id in self.staticInputs['monitored_nodes']:
			pdemand[node_id]={
				"data_raw_window":[initMeasurement[node_id]]*self.window_size,\
				"data_ffill_window":[initMeasurement[node_id]]*self.window_size,\
				"hour_window":[0]*self.window_size,
				"timestamp_window":[0.0]*self.window_size
			}
			qdemand[node_id]={
				"data_raw_window":[initMeasurement[node_id]]*self.window_size,\
				"data_ffill_window":[initMeasurement[node_id]]*self.window_size,\
				"hour_window":[0]*self.window_size,
				"timestamp_window":[0.0]*self.window_size
			}

		# streaming data
		self.streaming_data_dict = {}
		for node_id in self.staticInputs['monitored_nodes']:
			self.streaming_data_dict[node_id]={
				"pdemand":{"data_ffill":0.0},
				"qdemand":{"data_ffill":0.0}
			}

		logger.info('creating federate')
		if testMode:
			logger.info('in testMode')
			self.start_broker(1)
		self.federate=h.helicsCreateValueFederateFromConfig(json.dumps(self.config['federate_config']))
		self.pub=self.federate.publications
		self.sub=self.federate.subscriptions
		logger.info('completed setup')


#=======================================================================================================================
	def simulate(self,simEndTime=None):
		if not simEndTime:
			simEndTime=self.config['simulation_config']['end_time']
		self.federate.enter_executing_mode()
		logger.info('entered execution mode')

		grantedTime=0
		grantedTime = h.helicsFederateRequestTime(self.federate,grantedTime)

		while grantedTime<simEndTime:
			# get subscriptions
			subs=self.get_sub(checkForUpdate=True,returnAsDict=True)
			subsPortId={e:subs[self.inputMapping[e]] for e in self.inputMapping}
			logger.info('Received subscription')

			# alg
			data=self.impute(**subsPortId)
			missingPubKeys=set(self.pub.keys()).difference(data.keys())
			assert not missingPubKeys, f'missing the following pub keys:{missingPubKeys}'

			# set publications
			self.set_pub(data)
			logger.info(f'Sent Publication::::{data.keys()}')

			grantedTime = h.helicsFederateRequestTime(self.federate,grantedTime+1)
			logger.info(f'grantedTime::::{grantedTime}')

		logger.info('completed simulation')


#=======================================================================================================================
	def start_broker(self,nFeds):
		logger.info('starting broker')
		initstring = "-f {} --name=mainbroker".format(nFeds)
		self.broker = h.helicsCreateBroker("zmq", "", initstring)
		assert h.helicsBrokerIsConnected(self.broker)==1,"broker connection failed"
		logger.info('created broker')


#=======================================================================================================================
	def get_sub(self,checkForUpdate=False,returnAsDict=True):
		data={}
		for entry in self.sub:
			data[entry]={}
			typeFunc=self.mapping['subFunc'][entry]
			if checkForUpdate:
				if self.sub[entry].is_updated():
					temp=typeFunc.model_validate(self.sub[entry].json) # validate
					data[entry]=self.sub[entry].json if returnAsDict else temp
			else:
				temp=typeFunc.model_validate(self.sub[entry].json) # validate
				data[entry]=self.sub[entry].json if returnAsDict else temp
		return data


#=======================================================================================================================
	def set_pub(self,data:dict):
		for entry in self.pub:
			typeFunc=self.mapping['pubFunc'][entry]
			if data[entry]:
				self.pub[entry].publish(typeFunc(**data[entry]).model_dump_json())


#=======================================================================================================================
	def impute(self,powers_real,powers_imaginary):
		data={f'{self.federate_name}/powers_real':copy.deepcopy(powers_real),\
			f'{self.federate_name}/powers_imaginary':copy.deepcopy(powers_imaginary)}

		pdict=data[f'{self.federate_name}/powers_real']
		qdict=data[f'{self.federate_name}/powers_imaginary']
		if pdict:
			thisTimeStamp=pdict['time']

		for n in range(len(pdict)):
			if pdict['ids'][n] in self.staticInputs['monitored_nodes']:
				monitoredNode=pdict['ids'][n]
				val=pdict['values'][n]

				#Update pdemand ffill only if missing data is not detected
				if val != 0.0: #Check if data is not missing
					self.streaming_data_dict[monitoredNode]['pdemand'].update({"data_ffill":val})

				#update all other values
				self.streaming_data_dict[monitoredNode]['pdemand'].update({"timestamp":thisTimeStamp,\
					"hour":thisTimeStamp.hour,"data_raw":val})

				# process and update
				p_update=update_window_and_impute(
					self.streaming_data_dict[monitoredNode]['pdemand'],
					self.autoencoder_dict['pdemand'],
					monitoredNode,
					self.window_size,
					self.node_data_dict['pdemand'],
					self.window_id,
					self.input_features
				)
				pdict['values'][n]=p_update['AE']

		for n in range(len(qdict)):
			if qdict['ids'][n] in self.staticInputs['monitored_nodes']:
				monitoredNode=qdict['ids'][n]
				val=qdict['values'][n]

				#Update qdemand ffill only if missing data is not detected
				if val != 0.0: #Check if data is not missing
					self.streaming_data_dict[monitoredNode]['qdemand'].update({"data_ffill":val})

				#update all other values
				self.streaming_data_dict[monitoredNode]['qdemand'].update({"timestamp":thisTimeStamp,\
					"hour":thisTimeStamp.hour,"data_raw":val})

				# process and update
				q_update=update_window_and_impute(
					self.streaming_data_dict[monitoredNode]['qdemand'],
					self.autoencoder_dict['qdemand'],
					monitoredNode,
					self.window_size,
					self.node_data_dict['qdemand'],
					self.window_id,
					self.input_features
				)
				qdict['values'][n]=q_update['AE']

		return data


#=======================================================================================================================
	def finalize(self):
		h.helicsFederateFree(self.federate)
		h.helicsCloseLibrary()
		logger.info('Finalized -- objects released')


#=======================================================================================================================
if __name__=='__main__':
	baseDir=os.path.dirname(os.path.abspath(__file__))
	config=json.load(open(os.path.join(baseDir,'config_dataimputation.json')))
	inputMapping=json.load(open(os.path.join(baseDir,'input_mapping.json')))
	componentDefinition=json.load(open(os.path.join(baseDir,'component_definition.json')))
	staticInputs=json.load(open(os.path.join(baseDir,'static_inputs.json')))

	dff=DataImputationFederate(config,inputMapping,componentDefinition,staticInputs)
	dff.setup()
	dff.simulate()
	dff.finalize()


