import json
import os
from importlib.util import find_spec

from datapreprocessor.federates.dataimputation.federate_dataimputation import DataImputationFederate


def test_dataimputation_federate():
	spec=find_spec('datapreprocessor.federates.dataimputation.federate_dataimputation')
	baseDir=os.path.dirname(os.path.abspath(spec.origin))
	config=json.load(open(os.path.join(baseDir,'config_dataimputation.json')))
	inputMapping=json.load(open(os.path.join(baseDir,'input_mapping.json')))
	componentDefinition=json.load(open(os.path.join(baseDir,'component_definition.json')))
	staticInputs=json.load(open(os.path.join(baseDir,'static_inputs.json')))

	dff=DataImputationFederate(config,inputMapping,componentDefinition,staticInputs)
	dff.setup(True)
	dff.simulate()
	dff.finalize()
