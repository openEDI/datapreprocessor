from typing import Dict, List

from pydantic import BaseModel


class StaticInputsDataImputationExternal(BaseModel):
	casename:str
	monitored_nodes: List[str]
	initial_measurements:Dict[str,float]


class StaticInputsDataImputationInternal(BaseModel):
	casename:str
	model_path: str
	model_format: str
	monitored_nodes: List[str]
	initial_measurements:Dict[str,float]
	window_size:int
	input_features: List[str]


class InputMappingDataImputation(BaseModel):
	powers_real: str
	powers_imaginary: str
