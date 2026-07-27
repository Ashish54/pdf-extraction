from openai.api_resources.abstract import createable_api_resource
import ast
from pathlib import Path
import hashlib
from typing import List
from ..models import DocumentChunk
import logging

logger = logging.getLogger(__name__)

class CodeParser:
    def __init__(self, model_name: str):
        self.model_name = model_name
        
    def parse_python_file(self, file_path: Path, relative_to: Optional[Path] = None) -> List[DocumentChunk]:
        """
        Parse a Python file into DocumentChunks at function/class granularity.
        Args:
            file_path: Path to the Python file
            relative_to: Optional base path for resolving relative paths
        Returns:
            List[DocumentChunk]: List of DocumentChunks
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return []
            
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            logger.error(f"Syntax error parsing {file_path}: {e}")
            return []
            
        chunks = []
        lines = source.splitlines()
        
        # compute relative path for cleaner metadata
        if relative_to:
            rel_path = str(file_path.relative_to(relative_to))
        else:
            rel_path = str(file_path.name)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                chunk = self._process_class(node, lines, file_path, rel_path)
                if chunk:
                    chunks.append(chunk)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if isinstance(node, ast.FunctionDef) and self._is_top_level(node, tree):
                    chunk = self._process_function(node, lines, file_path, rel_path)
                    if chunk:
                        chunks.append(chunk)
        return chunks
        
    def _is_top_level(self, node: ast.FunctionDef, tree: ast.AST) -> bool:
        """
        Check if a node is defined at the top level of the module
        """
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                for child in parent.body:
                    if child is node:
                        return False
        return True
    
    def _process_function(self, node: ast.FunctionDef, lines: List[str], file_path: Path, rel_path: str) -> Optional[DocumentChunk]:
        """
        Process a function definition node into a DocumentChunk
        """
        try:
            start = node.lineno - 1
            end = node.end_lineno
            class_source = "\n".join(lines[start:end])
            docstring = ast.get_docstring(node) or ""
            
            # Extract base classes
            bases = [self._get_name(base) for base in node.bases]
            bases_str = f"Bases: {bases}" if bases else ""
            # Extract method names
            methods = [
                n.name for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            # Build search-friendly summary
            search_summary = f" Class: {node.name}{bases_str}"
            if docstring:
                search_summary += f" | Docstring: {docstring}"
            if methods:
                search_summary += f" | Methods: {methods}"
            search_summary += f"\n File: {rel_path}"

            # Build chunk text wth raw source
            chunk_text = f"#Class: {mode.name}\n"
            chunk_text += f"# File: {file_path.name}\n"
            chunk_text += f"Line: {node.lineno}"
            if docstring:
                chunk_text += f"\n# Docstring\n{docstring}"
            if methods:
                chunk_text += f"\n# Methods\n{methods}"
            chunk_text += f"\n# Source code\n{class_source}"

            # Generate deterministic chunk ID
            chunk_id_str = f"{rel_path}:class:{node.name}:{node.lineno}}"
            chunk_id = f"{self.model_name}:code:{hashlib.md5(chunk_id_str.encode("utf-8")).hexdigest()[:12]}"

            return DocumentChunk(
                chunk_id=chunk_id,
                source_type="code_documentation",
                model_name=self.model_name,
                file_path=rel_path,
                class_name=node.name,
                line_start=node.lineno,
                line_end=node.end_lineno,
                text=chunk_text,
            )
        except Exception as e:
            logger.error(f"Failed to process function {node.name} in {rel_path}: {e}")
            return None
    
    def _process_function(self, node: ast.FunctionDef, lines: List[str], file_path: Path, rel_path: str, class_name: Optional[str]) -> Optional[DocumentChunk]:
        """
        Process a class definition node into a DocumentChunk
        """
        try:
            start = node.lineno - 1
            end = node.end_lineno
            function_source = "\n".join(lines[start:end])
            docstring = ast.get_docstring(node) or ""
            
            # Extract function signature
            args = []
            for arg in node.args.args:
                args.append(arg.arg)
            signature = f"{node.name}({', '.join(args)})"
            
            # Build search-friendly summary for embedding

            search_summary = f" Function: {signature}"
            if class_name:
                search_summary = f"Class: {class_name} | Method: {signature}"
            if docstring:
                search_summary += f"| Docstring: {docstring}"
            search_summary += f"\n File: {rel_path}"

            chunk_text = f"# {'Method' if class_name else 'Function'}: {node.name}\n"
            if class_name:
                chunk_text += f"# Class: {class_name}\n"
            chunk_text += f"# File: {rel_path}\n"
            chunk_text += f"# Lines: {node.lineno}--{node.end_lineno}\n"
            if docstring:
                chunk_text += f"\n# Docstring\n{docstring}"
            chunk_text += f"\n# Source code\n{function_source}"
            
            # generate deterministic chunk id
            chunk_id_str = f"{rel_path}:function:{node.name}:{node.lineno}"
            chunk_id = f"{self.model_name}:code:{hashlib.md5(chunk_id_str.encode("utf-8")).hexdigest()[:12]}"
            
            return DocumentChunk(
                chunk_id=chunk_id,
                source_type="code_documentation",
                model_name=self.model_name,
                file_path=file_path.name,
                function_name=node.name,
                class_name=class_name,
                line_start=node.lineno,
                line_end=node.end_lineno,
                text=chunk_text,
            )
        except Exception as e:
            logger.error(f"Failed to process function {node.name} in {rel_path}: {e}")
            return None

    def _get_name(self, node:ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return str(node)

    def parse_directory(self, directory_path: Path, exclude_pattern: Optional[List[str]]) -> List[DocumentChunk]:
        """
        recursively parse all python files in a directory and its sub-directories
        
        Args:
            directory_path: Path to the directory to parse
            exclude_pattern: Optional list of patterns to exclude
            
        Returns:
            List[DocumentChunk]: List of DocumentChunks
        """
        if exclude_pattern is None:
            exclude_pattern = [
                "__pycache__",
                ".venv",
                ".env",
                ".git",
                ".eggs",
                "build",
                "dist",
                "venv",
                "build"
            ]
        try:
            directory_path = Path(directory_path).resolve()
            if not directory_path.exists():
                logger.error(f"Directory {directory_path} does not exist")
                return []
            if not directory_path.is_dir():
                logger.error(f"Directory {directory_path} is not a directory")
                return []
            python_files = list(directory_path.rglob("*.py"))
            all_chunks = []
            for py_file in python_files:
                should_exclude = any(pattern in str(py_file) for pattern in exclude_pattern)
                if should_exclude:
                    logger.info(f"Excluding {py_file}")
                    continue
                chunks = self.parse_file(py_file, directory_path)
                if chunks:
                    all_chunks.extend(chunks)
            
            return all_chunks
        except Exception as e:
            logger.error(f"Failed to parse directory {directory_path}: {e}")
            return []