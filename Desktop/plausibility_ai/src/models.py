from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any

class Severity(str, Enum):
    CRITICAL = "Critical"
    MAJOR = "Major"
    MODERATE = "Moderate"
    MINOR = "Minor"
    INFORMATIONAL = "Informational"

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class BreachRecord:
    sheet_name: str
    row_number: int
    model_name: str
    rule_name: str
    mnemonic: str
    breach_value: str
    threshold_value: str
    breach_type: str
    scenario_shocks: Dict[str, Any] = field(default_factory=dict)
    additional_columns: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DocumentChunk:
    chunk_id: str
    source_type: str  # "documentation" | "code"
    model_name: str
    model_id: Optiona[str] = None
    model_folder: Optional[str]=(None)
    
    # Doc specific
    document_title: Optional[str] = None
    section_path: Optional[str] = None
    page_number: Optional[int] = None
    
    # Code specific
    file_path: Optional[str] = None
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    
    text: str = ""
    relevance_score: Optional[float] = None
    
    def citation_string(self) -> str:
        if self.source_type == "documentation":
            return f"[Doc: {self.document_title} > {self.section_path}, Page {self.page_number}]"
        else:
            name = self.function_name or self.class_name or "global"
            return f"[Code: {self.file_path}:{self.line_start}-{self.line_end}, {name}]"
    
    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_type": self.source_type,
            "model_name": self.model_name,
            "document_title": self.document_title,
            "section_path": self.section_path,
            "page_number": self.page_number,
            "file_path": self.file_path,
            "function_name": self.function_name,
            "class_name": self.class_name,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "text": self.text,
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> "DocumentChunk":
        d = dict(data)
        d.pop("relevance_score", None) # Do not populate from db
        return cls(**d)

@dataclass
class Evidence:
    source: str
    reference: str
    excerpt: str
    chunk_id: Optional[str] = None

@dataclass
class AnalysisResult:
    breach: BreachRecord
    severity: Severity
    comment: str
    root_cause: str
    evidence: List[Evidence]
    confidence: Confidence
    uncertainty_notes: str
    raw_llm_response: str
    expected_behavior: bool = False
    requires_investigation: bool = False


@dataclass
class MnemonicInfo:
    """Information about a mnemonic from SGInput metadata."""
    indicator: str
    description: str
    description: str
    unit: str
    shock_type: str # absolute or relative


@dataclass
class SGInputContext:
    shocks: Dict[str, Dict[str, float]]
    metadata: Dict[str, MnemonicInfo]
    market_data: Dict[str, float]
    folder_path: Path

@dataclass
class SimpleAnalysisResult:
    breach: BreachRecord
    severity: Severity
    comment: str
    raw_response: str = ""


    