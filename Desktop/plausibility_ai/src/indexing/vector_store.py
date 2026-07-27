try:
    __import__("pysqlite3")
    import sys
    sys.modules['sqlite3'] = sys.modules.pop("pysqlite3")
except ImportError:
    pass


import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction, Documents
import hashlib
import asyncio
import concurrent.futures
import logging
from typing import List, Optional
from ..models import DocumentChunk
from ..config import Config

logger = logging.getLogger(__name__)


class APIEmbeddingFunction(EmbeddingFunction):
    """Custom ChromaBD embedding function that uses api-based embeddings."""
    def __init__(self, embedding_client):
        self.embedding_client = embedding_client
        
    
    def __call__(self, input:Documents) -> List[List[float]]:
        """Generate embeddings for the given documents."""
        try:
            asyncio.get_running_loop()
            # we're in async context - run in a separate thread to avoid nested loop issues
            with concurrent.futures.ThreadPoolExecutor() as exc:
                future = exc.submit(self._run_in_new_loop, input)
                embeddings = future.result()
                return embeddings
        except RuntimeError as e:
            # no running loop - run in current thread
            return self._run_in_new_loop(input)
    
    def _run_in_new_loop(self, input: Documents):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            embeddings = loop.run_until_complete(self.embedding_client.embed(input))
            return embeddings
        finally:
            loop.close()
        

class VectorStore:
    def __init__(self, config: Config, embedding_client=None, collection_name="plausibility_docs"):
        """
        Initialize the vector store with a specific collection

        Args:
            config: Configuration object containing paths and settings.
            embedding_client: Optional embedding client instance.
            collection_name: Name of the ChromaDB collection to use.
        """
        self.config = config
        self.persist_path = config.vector_store.persist_path
        self.collection_name = collection_name
        self.embedding_client = embedding_client

        # We will use ChromaDB's persistent client
        self.client = chromadb.PersistentClient(path=self.persist_path)
        # Using a default embedding function provided by Chroma, or we can use our own.
        # Since the user requested local embeddings, we can use the sentence-transformers default from Chroma 
        # or define our own embedding function class. Chroma uses sentence-transformers/all-MiniLM-L6-v2 by default
        # if we don't specify one, which is fast and local.
        # To match the config (BAAI/bge-small-en-v1.5), we'll define a custom embedding function.
        
        from chromadb.utils import APIEmbeddingFunction
        self.embedding_fn = APIEmbeddingFunction(self.embedding_client)   
        
        self.collection = self.client.get_or_create_collection(
            name="plausibility_docs",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, chunks: List[DocumentChunk]):
        """Add chunks to ChromaDB. Will skip if ID already exists."""
        if not chunks:
            return
            
        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        
        metadatas = []
        embeddings = []
        needs_embeddings = False
        
        for c in chunks:
            # Generate custom embedding if embedding_text is provided
            if getattr(c, "embedding_text", None):
                needs_embeddings = True
                
            meta = c.to_dict()
            # Clean up None values and complex types for Chroma metadata
            # We don't want to store embedding_text in metadata since it can be large
            meta.pop("embedding_text", None)
            
            clean_meta = {}
            for k, v in meta.items():
                if v is not None and isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
            metadatas.append(clean_meta)

        if needs_embeddings:
            # Compute embeddings manually for ALL chunks being added in this batch
            # Fall back to text if embedding_text is not present
            texts_to_embed = [c.embedding_text if getattr(c, "embedding_text", None) else c.text for c in chunks]
            # Since self.embedding_fn is a class instance, it can be called directly
            embeddings = self.embedding_fn(texts_to_embed)
            
            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
        else:
            # Let Chroma compute embeddings on 'documents' automatically
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

    def query(self, query_text: str, model_name: str, top_k: int = 5, source_type: Optional[str] = None) -> List[DocumentChunk]:
        """Query ChromaDB for relevant chunks based on a model name and optional source type."""
        
        where_filter = {"model_name": model_name}
        if source_type:
            where_filter["source_type"] = source_type
            
        results = self.collection.query(
            query_texts=[query_text],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        chunks = []
        if not results["ids"] or not results["ids"][0]:
            return chunks
            
        # Results are returned as lists of lists (one per query)
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            # Convert Chroma distance back to a similarity score (cosine distance)
            distance = results["distances"][0][i]
            score = 1.0 - distance
            
            chunk = DocumentChunk.from_dict(meta)
            chunk.text = results["documents"][0][i]
            chunk.relevance_score = score
            chunks.append(chunk)
            
        return chunks
