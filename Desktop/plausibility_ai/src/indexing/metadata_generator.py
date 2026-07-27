import json
import logging
from pathlib import Path
import pymupdf4llm

from ..config import Config
from ..analysis.llm_client import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a technical document analyzer for financial risk models. 
Given the first few pages of a model documentation PDF, extract key metadata about the model.
Respond ONLY in valid JSON format with the following exact keys:
{
    "model_name": "Name of the model (derive from title)",
    "model_type": "e.g., Interest Rate, Credit Risk, Valuation, Stress Testing, etc.",
    "purpose": "A 1-2 sentence summary of what the model does",
    "key_inputs": ["list", "of", "core", "inputs"],
    "key_outputs": ["list", "of", "core", "outputs"]
}
If any information is not clearly stated, infer it reasonably or use "Unknown".
"""

class MetadataGenerator:
    """
    Reads all model PDF documents, extracts the first few pages, 
    and uses the LLM to generate structured metadata summarizing each model.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.llm_client = LLMClient(config)
        
    async def generate_for_pdf(self, pdf_path: Path) -> dict:
        logger.info(f"Extracting text from {pdf_path.name}...")
        
        try:
            # Extract markdown for the first 3 pages
            md_pages = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
        except Exception as e:
            logger.error(f"Failed to read PDF {pdf_path.name}: {e}")
            return {"filename": pdf_path.name, "error": str(e)}
        
        # Take the first 3 pages to find title, abstract, executive summary
        intro_text = ""
        for i in range(min(3, len(md_pages))):
            intro_text += md_pages[i].get("text", "") + "\n\n"
            
        # Truncate text just to be safe with context windows
        user_prompt = f"Extract metadata for the following model documentation:\n\n{intro_text[:12000]}"
        
        logger.info(f"Calling LLM to generate metadata for {pdf_path.name}...")
        try:
            response_text = await self.llm_client.analyze(user_prompt, SYSTEM_PROMPT)
        except Exception as e:
            logger.error(f"LLM call failed for {pdf_path.name}: {e}")
            return {"filename": pdf_path.name, "error": str(e)}
        
        # Clean response if it contains markdown code blocks
        clean_text = response_text.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].strip()
            
        try:
            metadata = json.loads(clean_text)
            metadata["filename"] = pdf_path.name
            return metadata
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON for {pdf_path.name}. Raw response: {response_text}")
            return {"filename": pdf_path.name, "error": "JSON parse error", "raw_response": response_text}

    async def generate_all(self, output_file: str = "model_metadata.json"):
        pdf_dir = Path(self.config.paths.pdf_directory)
        if not pdf_dir.exists():
            logger.error(f"PDF directory {pdf_dir} does not exist.")
            return
            
        pdf_files = list(pdf_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDFs in {pdf_dir}. Generating metadata...")
        
        if not pdf_files:
            return
            
        metadata_list = []
        # Process sequentially to avoid aggressively rate-limiting the LLM, 
        # though this could be done via analyze_batch if preferred.
        for pdf_path in pdf_files:
            meta = await self.generate_for_pdf(pdf_path)
            metadata_list.append(meta)
            
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(metadata_list, f, indent=4)
            
        logger.info(f"Successfully wrote metadata for {len(metadata_list)} models to {output_file}")
        
    async def close(self):
        await self.llm_client.close()

# Convenience wrapper to run from CLI easily
if __name__ == "__main__":
    import asyncio
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    async def run():
        # Quick and dirty path resolution for standalone execution
        sys.path.append(str(Path(__file__).parent.parent.parent))
        from plausibility_ai.config import load_config
        
        config_path = "config/config.yaml"
        if not Path(config_path).exists():
            print(f"Error: Could not find {config_path}")
            return
            
        config = load_config(config_path)
        generator = MetadataGenerator(config)
        await generator.generate_all("data/model_metadata.json")
        await generator.close()
        
    asyncio.run(run())
