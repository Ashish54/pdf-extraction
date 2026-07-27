import click
import asyncio
from pathlib import Path
import logging

from .config import load_config
from .extraction.breach_extractor import BreachExtractor
from .retrieval.rag_retriever import RAGRetriever
from .analysis.llm_client import LLMClient
from .analysis.prompt_builder import PromptBuilder
from .analysis.response_parser import ResponseParser
from .output.excel_annotator import ExcelAnnotator
from .indexing.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

@click.group()
@click.option("--config", default="config/config.yaml", help="Path to config file")
@click.pass_context
def cli(ctx, config):
    ctx.ensure_object(dict)
    config_path = Path(config)
    if not config_path.exists():
        click.echo(f"Error: Config file not found at {config}")
        ctx.exit(1)
    ctx.obj["config"] = load_config(config_path)

@cli.command()
@click.pass_context
def index(ctx):
    """Run offline indexing of documentation and code."""
    from .indexing.pdf_parser import PDFParser
    from .indexing.code_parser import CodeParser
    
    config = ctx.obj["config"]
    vector_store = VectorStore(config)
    pdf_parser = PDFParser(config, vector_store)
    
    click.echo("Starting PDF indexing...")
    pdf_parser.index_directory()
    click.echo("PDF Indexing complete.")
    
    code_dir = Path(config.paths.code_directory)
    if code_dir.exists():
        click.echo(f"Starting code indexing from {code_dir}...")
        for py_file in code_dir.rglob("*.py"):
            # Determine model name from directory or file name
            model_name = "unknown_model"
            for substring, mapped_model in config.model_mapping.items():
                if substring in py_file.name or substring in str(py_file.parent):
                    model_name = mapped_model
                    break
                    
            parser = CodeParser(model_name)
            chunks = parser.parse_python_file(py_file)
            if chunks:
                vector_store.add_chunks(chunks)
                click.echo(f"  Indexed {len(chunks)} chunks from {py_file.name}")
        click.echo("Code Indexing complete.")
    else:
        click.echo(f"Code directory {code_dir} not found. Skipping code indexing.")

@cli.command()
@click.argument("report_path")
@click.option("--output", default=None, help="Output Excel path")
@click.pass_context
def analyze(ctx, report_path, output):
    """Analyze a plausibility Excel report."""
    config = ctx.obj["config"]
    asyncio.run(_analyze_async(config, report_path, output))

async def _analyze_async(config, report_path, output):
    # Setup components
    extractor = BreachExtractor()
    vector_store = VectorStore(config)
    retriever = RAGRetriever(config, vector_store)
    llm = LLMClient(config)
    prompt_builder = PromptBuilder()
    parser = ResponseParser()
    
    # 1. Extract
    breaches = extractor.extract_breaches(report_path)
    if not breaches:
        click.echo("No breached rows found in the report.")
        return
        
    # 2. Build Prompts
    prompts = []
    contexts = []
    
    click.echo(f"Retrieving context for {len(breaches)} breaches...")
    for breach in breaches:
        context_chunks = retriever.retrieve(breach)
        system, user = prompt_builder.build(breach, context_chunks)
        prompts.append((system, user))
        contexts.append(context_chunks)
        
    # 3. Analyze
    click.echo(f"Sending {len(prompts)} requests to LLM concurrently...")
    raw_responses = await llm.analyze_batch(prompts, config.analysis.max_concurrent_requests if hasattr(config, "analysis") else 5)
    
    # 4. Parse
    results = []
    for breach, raw_resp in zip(breaches, raw_responses):
        if isinstance(raw_resp, Exception):
            logger.error(f"Error analyzing breach: {raw_resp}")
            # parser._error_result is used on failure
            res = parser._error_result(breach, str(raw_resp), str(raw_resp))
        else:
            res = parser.parse(raw_resp, breach)
        results.append(res)
        
    # 5. Annotate
    annotator = ExcelAnnotator()
    out_path = annotator.annotate(report_path, results, output)
    
    click.echo("\nAnalysis Complete!")
    click.echo(f"Output saved to: {out_path}")
    await llm.close()

if __name__ == "__main__":
    cli()
