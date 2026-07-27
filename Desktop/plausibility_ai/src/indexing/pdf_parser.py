import os
import hashlib
from pathlib import Path
from typing import List, Optional
import pymupdf4llm
from ..models import DocumentChunk
from ..config import Config
from .vector_store import VectorStore
import logging

logger = logging.getLogger(__name__)

class PDFParser:
    def __init__(self, config: Config, vector_store: VectorStore):
        self.config = config
        self.vector_store = vector_store

    def _determine_model_name(self, filename: str) -> str:
        """Map filename to model name based on config."""
        for substring, model_name in self.config.model_mapping.items():
            if substring in filename:
                return model_name
        return "unknown_model"

    def _chunk_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """Simple token-based or character-based chunking."""
        # A simple character-based chunking as approximation for tokens
        # Assuming ~4 characters per token
        char_chunk_size = chunk_size * 4
        char_overlap = chunk_overlap * 4
        
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + char_chunk_size, text_len)
            
            # Try to snap to the nearest newline or period if possible
            if end < text_len:
                last_newline = text.rfind('\n', start, end)
                if last_newline != -1 and last_newline > start + (char_chunk_size // 2):
                    end = last_newline + 1
                else:
                    last_period = text.rfind('.', start, end)
                    if last_period != -1 and last_period > start + (char_chunk_size // 2):
                        end = last_period + 1

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)
            
            start = end - char_overlap
            
            # Prevent infinite loop if overlap is larger than progress
            if start <= 0 or end == text_len:
                break
                
        return chunks

    def process_pdf(self, pdf_path: Path) -> List[DocumentChunk]:
        """Parse a single PDF and return document chunks."""
        logger.info(f"Parsing PDF: {pdf_path.name}")
        model_name = self._determine_model_name(pdf_path.name)
        
        # Use pymupdf4llm to extract text in markdown format
        try:
            md_pages = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
        except Exception as e:
            logger.error(f"Error parsing {pdf_path.name}: {e}")
            return []

        document_title = pdf_path.stem
        all_chunks = []
        
        for page_data in md_pages:
            page_text = page_data.get("text", "")
            page_num = page_data.get("metadata", {}).get("page", 1)
            
            # Chunk the text
            text_chunks = self._chunk_text(
                page_text, 
                self.config.indexing.chunk_size, 
                self.config.indexing.chunk_overlap
            )
            
            for i, chunk_text in enumerate(text_chunks):
                # Create a deterministic chunk ID
                chunk_id_str = f"{pdf_path.name}_{page_num}_{i}_{hashlib.md5(chunk_text.encode()).hexdigest()[:8]}"
                
                chunk = DocumentChunk(
                    chunk_id=chunk_id_str,
                    source_type="documentation",
                    model_name=model_name,
                    document_title=document_title,
                    page_number=page_num,
                    text=chunk_text
                )
                all_chunks.append(chunk)
                
        return all_chunks

    def index_directory(self):
        """Process all PDFs in the configured directory and store in ChromaDB."""
        pdf_dir = Path(self.config.paths.pdf_directory)
        if not pdf_dir.exists():
            logger.warning(f"PDF directory {pdf_dir} does not exist.")
            return

        all_pdf_files = list(pdf_dir.glob("*.pdf"))
        logger.info(f"Found {len(all_pdf_files)} PDFs in {pdf_dir}")
        
        for pdf_path in all_pdf_files:
            chunks = self.process_pdf(pdf_path)
            if chunks:
                logger.info(f"Adding {len(chunks)} chunks to vector store for {pdf_path.name}")
                self.vector_store.add_chunks(chunks)
                
        logger.info("Indexing complete.")
