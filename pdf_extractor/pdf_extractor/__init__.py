"""pdf_extractor: keep only configured sections of a large PDF, losslessly."""

from .api import ExtractReport, extract
from .config import ExtractConfig, load_config

__version__ = "0.2.0"
__all__ = [
    "extract",
    "ExtractReport",
    "ExtractConfig",
    "load_config",
    "__version__",
]
