from dataclasses import dataclass
import yaml
import json
import logging
from pathlib import Path
from ..config import Config

logger = logging.getLogger(__name__)

@dataclass
Class ControlMapping:
    control_name: str
    country_names: List[str]
    model_name: List[str]
    model_ids: List[str]
    

class PlausibilityMapping:
    def __init__(self, mapping_file: Optional[Path]=None, model_info_file: Optional[Path]=None):
        self.mapping_file = mapping_file
        self.model_info_file = model_info_file
        self.control_mappings = {}
        self.model_info = {}
        if mapping_file and mapping_file.exists():
            self._load_mapping()
        if model_info_file and model_info_file.exists():
            self._load_model_info()
            
    def _load_mapping(self):
        """Load the YAML mapping file."""
        try:
            with open(self.mapping_file, 'r', encoding="utf-8") as f:
                data = yaml.safe_load(f)
            mappings = data.get('plausibility_model_mapping',[])
            
            for item in mappings:
                control_name = item.get("Control name", "").strip()
                if not control_name:
                    continue
                country_str = item.get("Country names","")
                countries = [c.strip() for c in country_str.split(":") if c.strip()]
                model_name = item.get("Model name","").strip()
                model_id_str = item.get("Model id","").strip()
                model_ids = [mid.stript() for mid in model_id_str.split(";") if mid.strip()]
                
                self.control_mappings[control_name] = ControlMapping(
                    control_name=control_name,
                    country_names=countries,
                    model_name=model_name,
                    model_ids=model_ids
                )
            logger.info(f"Loaded plausibility mapping from {self.mapping_path}")
        except FileNotFoundError:
            logger.error(f"Mapping file not found: {self.mapping_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing mapping file: {e}")
            raise
            
    def _load_model_info(self):
        """
        load the model info json files
        """
        with open(self.model_info_file, 'r', encoding="utf-8") as f:
            self.model_info = json.load(f)
        logger.info(f"Loaded model info from {self.model_info_file}")
        
    def get_model_ids_for_control(self, control_name: str, country_code: str=None) -> List[str]:
        """
        get the model ids for a control name

        
        """
        if control_name not in self.control_mappings:
            logger.debug(f" No mapping found for control name{control_name}")
            return []
        
        mapping = self.control_mappings[control_name]
        if country_code and country_code in mapping.country_names:
            return mapping.model_ids
        elif country_code is None:
            return mapping.model_ids
        else:
            logger.debug(f"Country code {country_code} not found in mapping for control {control_name}")
            return []

    
    def get_model_names_for_control(self, control_name: str) -> List[str]:
        """
        Get model names for a control name
        """
        if control_name not in self.control_mappings:
            logger.debug(f" No mapping found for control name{control_name}")
            return []
        
        mapping = self.control_mappings[control_name]
        return mapping.model_name
    
    def get_model_folder_for_id(self, model_id: str) -> Optional[str]:
        """
        Get model folder for a model id
        """
        model_info = self.model_info.get(model_id)
        if model_info:
            return model_info.get("ModelFolder")
        logger.warning(f"No model info found for model id: {model_id}")
        return None
    
    def get_search_filters(self, control_name: str, country_code: str = None) -> Dict[str, Any]:
        """
        Get search filters for a control name
        """
        model_ids = self.get_model_ids_for_control(control_name, country_code)
        model_names = self.get_model_names_for_control(control_name)
        model_folders = [
            self.get_model_folder_for_id(model_id) for model_id in model_ids if self.get_model_folder_for_id(model_id)
        ]
        return {

            "model_ids": model_ids,
            "model_names": model_names,
            "model_folders": model_folders,
            "has_mapping": len(model_ids) > 0
        }

        