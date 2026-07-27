import os
import yaml
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from pathlib import Path

@dataclass
class AuthConfig:
    mode: str = "devpod"
    broker_url: str = "https://localhost.net/"
    broker_version: str = "v2"
    broker_env: Optional[str] = None
    scopes: Optional[Any] = None
    auto_refresh: bool = True
    verify_ssl: bool = True
    ssl_certificate_path: str = "/cacert.pem"

    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    def __post_init__(self):
        """load secrets from environment variables if not provided"""
        if self.mode == "service" or self.mode == "managed_identity":
            env_prefix = "AIAAS_AUTH"
            self.client_id = os.getenv(f"{env_prefix}_CLIENT_ID") or self.client_id
            self.client_secret = os.getenv(f"{env_prefix}_CLIENT_SECRET") or self.client_secret
            self.tenant_id = os.getenv(f"{env_prefix}_TENANT_ID") or self.tenant_id


@dataclass
class LLMConfig:
    endpoint: str
    base_url: str = "https//baseurl.net"
    model_name: str = "Qwen/Qwen3.6-27B"
    context_window: int = 8192
    max_output_tokens: int = 4096
    temperature: float = 0.1
    timeout_seconds: int = 300
    max_retries: int = 1
    verify_ssl: bool = False

    def __post_init__(self):
        if self.endpoint is not None:
            self.base_url = "https://api.openai.com/v1"
    

@dataclass
class RetrievalConfig:
    strategy: str = "rag"
    top_k_docs: int = 5
    top_k_code: int = 5
    similarity_threshold: float = 0.3

@dataclass
class AnalysisConfig:
    max_concurrent_requests: int = 2
    retry_attempts: int = 1
    retry_backoff_multiplier: float = 1.0
    retry_min_wait: int = 2
    retry_max_wait: int = 10

@dataclass
class EmbeddingConfig:
    model_name: str = "BAAI/bge-small-en-v1.5"
    device: str = "cpu"

    use_api: bool = False
    api_model_name: str = "Qwen/Qwen3-Embedding-8B"

    # Token limits for embedding
    max_tokens: int = 6000
    chars_per_token: int = 4


@dataclass
class VectorStoreConfig:
    type: str = "chromadb"
    persist_path: str = "./data/chromadb"

@dataclass
class IndexingConfig:
    chunk_size: int = 512
    chunk_overlap: int = 64

@dataclass
class PathsConfig:
    pdf_directory: str = "./data/pdfs"
    code_docs_directory: str = "./data/code-docs"
    code_directory: str = "./data/code"

@dataclass
class Config:
    llm: LLMConfig
    retrieval: RetrievalConfig
    embedding: EmbeddingConfig
    vector_store: VectorStoreConfig
    indexing: IndexingConfig
    paths: PathsConfig
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    auth: Optional[AuthConfig] = None
    model_mapping: Dict[str, str] = field(default_factory=dict)

def load_config(config_path: str | Path) -> Config:
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    auth_config = None
    if "auth" in data:
        auth_config = AuthConfig(**data["auth"])
        
    return Config(
        llm=LLMConfig(**data.get("llm", {})),
        retrieval=RetrievalConfig(**data.get("retrieval", {})),
        embedding=EmbeddingConfig(**data.get("embedding", {})),
        vector_store=VectorStoreConfig(**data.get("vector_store", {})),
        indexing=IndexingConfig(**data.get("indexing", {})),
        paths=PathsConfig(**data.get("paths", {})),
        analysis=AnalysisConfig(**data.get("analysis", {})),
        auth=auth_config,
        model_mapping=data.get("model_mapping", {})
    )
