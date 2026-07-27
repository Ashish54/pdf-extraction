from typing import List
from ..models import BreachRecord, DocumentChunk
from ..config import Config
from ..indexing.vector_store import VectorStore
import logging

logger = logging.getLogger(__name__)

class RAGRetriever:
    def __init__(self, config: Config, vector_store: VectorStore):
        self.config = config
        self.vector_store = vector_store
        
    def retrieve(self, breach: BreachRecord) -> List[DocumentChunk]:
        """
        Retrieves context for a given breach using vector similarity search.
        """
        query_text = self._build_query(breach)
        logger.debug(f"Retrieval query: {query_text}")
        
        # Retrieve documentation chunks
        doc_chunks = self.vector_store.query(
            query_text=query_text,
            model_name=breach.model_name,
            top_k=self.config.retrieval.top_k_docs,
            source_type="documentation"
        )
        
        # Retrieve code chunks (if any are indexed)
        code_chunks = self.vector_store.query(
            query_text=query_text,
            model_name=breach.model_name,
            top_k=self.config.retrieval.top_k_code,
            source_type="code"
        )
        
        # Filter by similarity threshold
        threshold = self.config.retrieval.similarity_threshold
        valid_docs = [c for c in doc_chunks if c.relevance_score is not None and c.relevance_score >= threshold]
        valid_code = [c for c in code_chunks if c.relevance_score is not None and c.relevance_score >= threshold]
        
        return valid_docs + valid_code
        
    def _build_query(self, breach: BreachRecord) -> str:
        """Build a semantic query for vector search."""
        parts = [
            f"Model: {breach.model_name}",
            f"Validation rule: {breach.rule_name}",
            f"Rule mnemonic: {breach.mnemonic}",
            f"The {breach.breach_type} occurred because the observed value ({breach.breach_value}) exceeded the threshold ({breach.threshold_value})."
        ]
        
        if breach.scenario_shocks:
            shock_desc = ", ".join(f"{k}: {v}" for k, v in breach.scenario_shocks.items() if v)
            parts.append(f"Under scenario shocks: {shock_desc}")
            
        return " ".join(parts)
