import openpyxl
from typing import List, Dict, Any
from ..models import BreachRecord
import logging

logger = logging.getLogger(__name__)

# Sheet-specific column mapping for different reports formats
SHEET_MAPPINGS = {
    "Summary":
    {
        "control_name": "Control Name",
        "type": "Type",
        "rating": "Rating",
        "quarters": "Quarters",
        "breach_description": "Breach",
        "comments": "Comments"
    },
    "Plausibility COREVARS": {
        "flag": "Flag",
        "mnemonic_class": "Mnemonic Class",
        "breach": "Breach",
        "breach_type": "Breach Type",
        "mnemonics": "Mnemonics",
        "comments": "Comments"
    },
    "Plausibility Unexpected Input": {
        "mnemonic": "Mnemonic",
        "shock_type": "ShockType",
        "unit": "Unit",
        "sampling_sequence": "Sampling Sequence",
        "breach_type": "BreachType",
        "threshold_value": "ThresholdValue",
        "details": "Details",
        "breached_threshold": "breached_threshold",
        "value": "Value",
        "diff": "Diff",
        "unit_type": "UnitType",
        "comments": "Comments",
    },
    "LTEC Baseline": {
        "mnemonics": "Mnemonics",
        "low_sd": "LowSD",
        "changes": "Changes",
        "quarters": "Quarters",
        "threshold": "Threshold",
        "breach": "Breach",
        "comments": "Comments",    
    }, 
}



class BreachExtractor:
    def extract_breaches(self, report_path: str) -> List[BreachRecord]:
        """
        Extract all breached/flagged rows from the plausibility Excel report.
        """
        logger.info(f"Extracting breaches from {report_path}")
        wb = openpyxl.load_workbook(report_path, data_only=True)
        breaches = []
        
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if ws.max_row <= 1:
                continue
                
            # Parse headers
            headers = {str(cell.value).strip(): cell.column - 1 for cell in ws[1] if cell.value}
            
            # Determin if this sheet has a known mapping or use generic approach
            sheet_mapping = SHEET_MAPPINGS.get(sheet_name)
            
            # Extract breaches for this sheet
            sheet_breaches = self._extract_from_sheet(ws, sheet_name, headers, sheet_mapping)
            breaches.extend(sheet_breaches)
        logger.info(f" Extracted {len(breaches)} breaches from {report_path}")
        return breaches
    
    def _is_breach_row(
        self, row: List[Any], headers: Dict[str, int], sheet_mapping: Dict[str, str]
    ) -> bool:
        """
        Determine if a row represents a breach based on the sheet mapping.
        """
        if "breach" in sheet_mapping:
            breach_col = sheet_mapping["breach"]
            if breach_col in headers:
                idx = headers[breach_col]
                if idx < len(row) and row[idx] is True:
                    return True
        if "breach_type" in sheet_mapping:
            breach_type_col = sheet_mapping["breach_type"]
            if breach_type_col in headers:
                idx = headers[breach_type_col]
                if idx < len(row) and row[idx] is True:
                    return True
        
        # For summary sheet, check if Breach column
        if "breach_desciption" in sheet_mapping:
            breach_desc_col = sheet_mapping["breach_description"]
            if breach_desc_col in headers:
                idx = headers[breach_desc_col]
                if idx < len(row) and row[idx] is True:
                    return True
        return False
    
    def _extract_from_sheet(self, ws, sheet_name, headers, sheet_mapping) -> List[BreachRecord]:
        """
        Extract breaches from a single sheet using the provided mapping.
        """
        breaches = []

        for row_idx in range(2, ws.max_row + 1):
            row = [cell.value for cell in ws[row_idx]]
            
            if not self._is_breach_row(row, headers, sheet_mapping):
                continue
            
            def get_val(mapping_key: str, default: str=""):
                col_name = sheet_mapping.get(mapping_key)
                if col_name and col_name in headers:
                    idx = headers[col_name]
                    if idx < len(row) and row[idx] is not None:
                        return str(row[idx]).strip()
                return default
            
            model_name = get_val("type") or get_val("mnemonic_class") or sheet_name
            rule_name = get_val("control_name") or get_val("breach_type") or sheet_name
            mnemonic = get_val("mnemonic") or get_val("mnemonics") or ""

            # Extract the breach value and threshold
            breach_value = (
                get_val("value") or 
                get_val("diff") or 
                get_val("breach") or 
                get_val("breached_threshold")
            )
            threshold_value = (
                get_val("threshold_value") or
                get_val("threshold") or
                ""
            )
            # Determine the breach type
            breach_type = get_val("breach_type") or "Breach"

            # collect additional columns not in the mapping
            additional = {}
            mapped_col_names = set(sheet_mapping.values())
            for col_name, col_index in headers.items():
                if col_name not in mapped_col_names:
                    additional[col_name] = row[col_index]
            
            shocks = {}
            shock_col = get_val("shock_type")
            if shock_col:
                shocks[shock_col] = shock_col
            
            # build the breach record
            breach = BreachRecord(
                sheet_name=sheet_name,
                row_number=row_idx,
                mnemonic=mnemonic,
                model_name=model_name,
                rule_name=rule_name,
                breach_type=breach_type,
                breach_value=breach_value,
                scenario_shocks=shocks,
                threshold_value=threshold_value,
                additional_columns=additional
            )
            

            if sheet_name == "Summary":
                model_name = get_val("model_name")
                rule_name = get_val("control_name")
                rule_type = get_val("type")
                status = get_val("rating")
                quarters = get_val("quarters")
                breach = get_val("breach_description")
                comments = get_val("comments")
            
            
                if mapping_key in sheet_mapping:
                    header = sheet_mapping[mapping_key]
                    if header in headers:
                        idx = headers[header]
                        if idx < len(row) and row[idx] is not None:
                            return str(row[idx]).strip()
                return default
            # Identify missing required columns
            required_cols = [COLUMN_MAP["status"], COLUMN_MAP["model_name"], COLUMN_MAP["rule_name"]]
            missing = [c for c in required_cols if c not in headers]
            
            if missing:
                logger.warning(f"Sheet '{sheet_name}' missing required columns: {missing}. Skipping.")
                continue
                
            for row_idx in range(2, ws.max_row + 1):
                row = [cell.value for cell in ws[row_idx]]
                
                # Check if row is within range and has a status
                status_idx = headers.get(COLUMN_MAP["status"])
                if status_idx >= len(row) or row[status_idx] is None:
                    continue
                    
                status = str(row[status_idx]).strip()
                if status not in BREACH_STATUSES:
                    continue
                    
                # Extract shocks
                shocks = {}
                for shock_col in COLUMN_MAP.get("shock_columns", []):
                    if shock_col in headers and headers[shock_col] < len(row):
                        val = row[headers[shock_col]]
                        if val is not None:
                            shocks[shock_col] = val
                            
                # Extract additional data
                mapped_cols = list(COLUMN_MAP.values()) + COLUMN_MAP.get("shock_columns", [])
                additional = {}
                for h, i in headers.items():
                    if h not in mapped_cols and i < len(row):
                        val = row[i]
                        if val is not None:
                            additional[h] = val
                            
                # Safely get values
                def get_val(key, default=""):
                    idx = headers.get(COLUMN_MAP.get(key))
                    if idx is not None and idx < len(row):
                        return str(row[idx]) if row[idx] is not None else default
                    return default
                    
                breach = BreachRecord(
                    sheet_name=sheet_name,
                    row_number=row_idx,
                    model_name=model_name,
                    rule_name=rule_name,
                    mnemonic=mnemonic,
                    breach_value=breach_value,
                    threshold_value=threshold_value,
                    breach_type=status,
                    scenario_shocks=shocks,
                    additional_columns=additional
                )
                breaches.append(breach)
        if breaches:        
            logger.info(f"Extracted {len(breaches)} breaches from sheet {sheet_name}")
        return breaches
