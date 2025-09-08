"""Core code analysis service for extracting structured information from codebases."""

import ast
import os
import asyncio
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import structlog
import tree_sitter
from tree_sitter import Language, Parser
import libcst as cst
from jedi import Script
import magic
import chardet

from ..config import get_settings

logger = structlog.get_logger(__name__)


class CodeAnalysisService:
    """Service for analyzing code repositories and extracting structured information."""
    
    def __init__(self):
        """Initialize the code analysis service."""
        self.settings = get_settings()
        self.logger = logger.bind(service="code_analysis")
        
        # Initialize tree-sitter parsers
        self.parsers = {}
        self._init_parsers()
        
        # Analysis statistics
        self.files_analyzed = 0
        self.total_lines_analyzed = 0
        self.errors_encountered = 0
    
    def _init_parsers(self):
        """Initialize tree-sitter parsers for supported languages."""
        try:
            # Note: In production, you would build the language libraries
            # For this demo, we'll use AST parsing for Python and basic text analysis for others
            self.logger.info("Initializing code parsers")
            
            # Python AST parser is built-in
            self.parsers["python"] = "ast"
            
            # For other languages, we'll use basic text analysis
            for lang in self.settings.supported_languages:
                if lang != "python":
                    self.parsers[lang] = "text"
                    
        except Exception as e:
            self.logger.warning("Failed to initialize some parsers", error=str(e))
    
    async def analyze_repository(
        self,
        repo_path: str,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Analyze a code repository and extract structured information.
        
        Args:
            repo_path: Path to the repository
            include_patterns: File patterns to include
            exclude_patterns: File patterns to exclude
            
        Returns:
            Analysis results with structured code information
        """
        self.logger.info("Starting repository analysis", repo_path=repo_path)
        
        try:
            repo_path = Path(repo_path)
            if not repo_path.exists():
                raise ValueError(f"Repository path does not exist: {repo_path}")
            
            # Get repository metadata
            repo_info = await self._get_repository_info(repo_path)
            
            # Find analyzable files
            files_to_analyze = await self._find_files(
                repo_path,
                include_patterns or ["**/*"],
                exclude_patterns or [
                    "**/.git/**", "**/node_modules/**", "**/__pycache__/**",
                    "**/venv/**", "**/env/**", "**/.env/**", "**/build/**",
                    "**/dist/**", "**/*.pyc", "**/*.pyo", "**/*.pyd"
                ]
            )
            
            self.logger.info(f"Found {len(files_to_analyze)} files to analyze")
            
            # Analyze files in batches
            analysis_results = []
            batch_size = 10
            
            for i in range(0, len(files_to_analyze), batch_size):
                batch = files_to_analyze[i:i + batch_size]
                batch_results = await asyncio.gather(
                    *[self._analyze_file(file_path, repo_path) for file_path in batch],
                    return_exceptions=True
                )
                
                for result in batch_results:
                    if isinstance(result, Exception):
                        self.errors_encountered += 1
                        self.logger.warning("File analysis failed", error=str(result))
                    else:
                        analysis_results.append(result)
            
            # Extract high-level insights
            insights = await self._extract_insights(analysis_results, repo_path)
            
            # Create final analysis result
            final_result = {
                "repository_info": repo_info,
                "files_analyzed": len(analysis_results),
                "total_files_found": len(files_to_analyze),
                "analysis_results": analysis_results,
                "insights": insights,
                "statistics": {
                    "files_analyzed": self.files_analyzed,
                    "total_lines_analyzed": self.total_lines_analyzed,
                    "errors_encountered": self.errors_encountered,
                    "languages_detected": list(set(r.get("language") for r in analysis_results if r.get("language")))
                }
            }
            
            self.logger.info(
                "Repository analysis completed",
                files_analyzed=len(analysis_results),
                total_lines=self.total_lines_analyzed
            )
            
            return final_result
            
        except Exception as e:
            self.logger.error("Repository analysis failed", error=str(e))
            raise
    
    async def _get_repository_info(self, repo_path: Path) -> Dict[str, Any]:
        """Get basic repository information.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Repository metadata
        """
        info = {
            "path": str(repo_path),
            "name": repo_path.name,
            "size_bytes": 0,
            "file_count": 0,
            "is_git_repo": False,
            "git_info": {}
        }
        
        try:
            # Calculate repository size and file count
            for root, dirs, files in os.walk(repo_path):
                info["file_count"] += len(files)
                for file in files:
                    file_path = Path(root) / file
                    try:
                        info["size_bytes"] += file_path.stat().st_size
                    except (OSError, IOError):
                        continue
            
            # Check if it's a git repository
            git_dir = repo_path / ".git"
            if git_dir.exists():
                info["is_git_repo"] = True
                info["git_info"] = await self._get_git_info(repo_path)
            
        except Exception as e:
            self.logger.warning("Failed to get repository info", error=str(e))
        
        return info
    
    async def _get_git_info(self, repo_path: Path) -> Dict[str, Any]:
        """Get git repository information.
        
        Args:
            repo_path: Path to git repository
            
        Returns:
            Git metadata
        """
        git_info = {}
        
        try:
            import git
            repo = git.Repo(repo_path)
            
            git_info = {
                "current_branch": repo.active_branch.name if repo.active_branch else "detached",
                "commit_count": len(list(repo.iter_commits())),
                "last_commit": {
                    "hash": repo.head.commit.hexsha[:8],
                    "message": repo.head.commit.message.strip(),
                    "author": str(repo.head.commit.author),
                    "date": repo.head.commit.committed_datetime.isoformat()
                },
                "remotes": [remote.url for remote in repo.remotes],
                "is_dirty": repo.is_dirty()
            }
            
        except Exception as e:
            self.logger.warning("Failed to get git info", error=str(e))
            git_info = {"error": str(e)}
        
        return git_info
    
    async def _find_files(
        self,
        repo_path: Path,
        include_patterns: List[str],
        exclude_patterns: List[str]
    ) -> List[Path]:
        """Find files to analyze based on patterns.
        
        Args:
            repo_path: Repository path
            include_patterns: Patterns to include
            exclude_patterns: Patterns to exclude
            
        Returns:
            List of file paths to analyze
        """
        import pathspec
        
        # Create pathspec objects
        include_spec = pathspec.PathSpec.from_lines("gitwildmatch", include_patterns)
        exclude_spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude_patterns)
        
        files_to_analyze = []
        
        for root, dirs, files in os.walk(repo_path):
            # Filter directories to avoid walking excluded paths
            dirs[:] = [d for d in dirs if not exclude_spec.match_file(str(Path(root) / d))]
            
            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(repo_path)
                
                # Check if file matches include patterns and doesn't match exclude patterns
                if (include_spec.match_file(str(relative_path)) and 
                    not exclude_spec.match_file(str(relative_path))):
                    
                    # Check file extension
                    if file_path.suffix.lower() in self.settings.allowed_file_extensions:
                        # Check file size
                        try:
                            size_mb = file_path.stat().st_size / (1024 * 1024)
                            if size_mb <= self.settings.max_file_size_mb:
                                files_to_analyze.append(file_path)
                        except (OSError, IOError):
                            continue
        
        return files_to_analyze
    
    async def _analyze_file(self, file_path: Path, repo_path: Path) -> Dict[str, Any]:
        """Analyze a single file and extract structured information.
        
        Args:
            file_path: Path to file
            repo_path: Repository root path
            
        Returns:
            File analysis results
        """
        try:
            # Get file metadata
            stat = file_path.stat()
            relative_path = file_path.relative_to(repo_path)
            
            # Detect file encoding and read content
            content = await self._read_file_content(file_path)
            if content is None:
                return {"error": "Could not read file content", "file_path": str(relative_path)}
            
            # Detect language
            language = self._detect_language(file_path, content)
            
            # Count lines
            lines = content.split('\n')
            line_count = len(lines)
            self.total_lines_analyzed += line_count
            
            # Basic file analysis
            analysis = {
                "file_path": str(relative_path),
                "absolute_path": str(file_path),
                "language": language,
                "size_bytes": stat.st_size,
                "line_count": line_count,
                "encoding": self._detect_encoding(file_path),
                "last_modified": stat.st_mtime,
                "analysis_timestamp": asyncio.get_event_loop().time()
            }
            
            # Language-specific analysis
            if language == "python":
                analysis.update(await self._analyze_python_file(content, file_path))
            elif language in ["javascript", "typescript"]:
                analysis.update(await self._analyze_js_file(content, file_path))
            elif language == "sql":
                analysis.update(await self._analyze_sql_file(content, file_path))
            else:
                analysis.update(await self._analyze_generic_file(content, file_path))
            
            self.files_analyzed += 1
            return analysis
            
        except Exception as e:
            self.logger.warning("File analysis failed", file_path=str(file_path), error=str(e))
            return {
                "file_path": str(file_path.relative_to(repo_path)),
                "error": str(e),
                "analysis_timestamp": asyncio.get_event_loop().time()
            }
    
    async def _read_file_content(self, file_path: Path) -> Optional[str]:
        """Read file content with encoding detection.
        
        Args:
            file_path: Path to file
            
        Returns:
            File content or None if failed
        """
        try:
            # Try UTF-8 first
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                # Detect encoding
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                    encoding = chardet.detect(raw_data)['encoding']
                
                if encoding:
                    return raw_data.decode(encoding)
                else:
                    return None
            except Exception:
                return None
        except Exception:
            return None
    
    def _detect_language(self, file_path: Path, content: str) -> str:
        """Detect programming language from file path and content.
        
        Args:
            file_path: Path to file
            content: File content
            
        Returns:
            Detected language
        """
        # Map file extensions to languages
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.sql': 'sql',
            '.md': 'markdown',
            '.txt': 'text',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css'
        }
        
        extension = file_path.suffix.lower()
        if extension in extension_map:
            return extension_map[extension]
        
        # Try to detect from content
        if content.strip().startswith('#!/usr/bin/env python') or 'import ' in content:
            return 'python'
        elif 'function ' in content or 'const ' in content or 'let ' in content:
            return 'javascript'
        elif 'SELECT ' in content.upper() or 'CREATE TABLE' in content.upper():
            return 'sql'
        
        return 'unknown'
    
    def _detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding.
        
        Args:
            file_path: Path to file
            
        Returns:
            Detected encoding
        """
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(1024)  # Read first 1KB
                result = chardet.detect(raw_data)
                return result.get('encoding', 'unknown')
        except Exception:
            return 'unknown'
    
    async def _analyze_python_file(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Analyze Python file using AST.
        
        Args:
            content: File content
            file_path: File path
            
        Returns:
            Python-specific analysis results
        """
        analysis = {
            "classes": [],
            "functions": [],
            "imports": [],
            "variables": [],
            "docstrings": [],
            "complexity_score": 0
        }
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "line_number": node.lineno,
                        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                        "docstring": ast.get_docstring(node),
                        "decorators": [self._get_decorator_name(d) for d in node.decorator_list]
                    }
                    analysis["classes"].append(class_info)
                
                elif isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "line_number": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                        "docstring": ast.get_docstring(node),
                        "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
                        "is_async": isinstance(node, ast.AsyncFunctionDef)
                    }
                    analysis["functions"].append(func_info)
                
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            analysis["imports"].append({
                                "module": alias.name,
                                "alias": alias.asname,
                                "line_number": node.lineno
                            })
                    else:  # ImportFrom
                        for alias in node.names:
                            analysis["imports"].append({
                                "module": node.module,
                                "name": alias.name,
                                "alias": alias.asname,
                                "line_number": node.lineno
                            })
                
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            analysis["variables"].append({
                                "name": target.id,
                                "line_number": node.lineno,
                                "type": type(node.value).__name__
                            })
            
            # Calculate complexity (simplified)
            analysis["complexity_score"] = len(analysis["functions"]) + len(analysis["classes"]) * 2
            
        except SyntaxError as e:
            analysis["syntax_error"] = str(e)
        except Exception as e:
            analysis["analysis_error"] = str(e)
        
        return analysis
    
    def _get_decorator_name(self, decorator) -> str:
        """Get decorator name from AST node.
        
        Args:
            decorator: AST decorator node
            
        Returns:
            Decorator name
        """
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{decorator.value.id}.{decorator.attr}"
        else:
            return "unknown"
    
    async def _analyze_js_file(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript file.
        
        Args:
            content: File content
            file_path: File path
            
        Returns:
            JavaScript-specific analysis results
        """
        analysis = {
            "functions": [],
            "classes": [],
            "imports": [],
            "exports": [],
            "variables": []
        }
        
        # Simple regex-based analysis (in production, use proper parser)
        import re
        
        # Find function declarations
        func_pattern = r'(?:function\s+(\w+)|(\w+)\s*=\s*(?:function|\([^)]*\)\s*=>))'
        for match in re.finditer(func_pattern, content):
            func_name = match.group(1) or match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            analysis["functions"].append({
                "name": func_name,
                "line_number": line_num,
                "type": "function"
            })
        
        # Find class declarations
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            analysis["classes"].append({
                "name": class_name,
                "line_number": line_num
            })
        
        # Find imports
        import_pattern = r'import\s+.*?from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content):
            module = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            analysis["imports"].append({
                "module": module,
                "line_number": line_num
            })
        
        return analysis
    
    async def _analyze_sql_file(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Analyze SQL file.
        
        Args:
            content: File content
            file_path: File path
            
        Returns:
            SQL-specific analysis results
        """
        analysis = {
            "tables": [],
            "views": [],
            "procedures": [],
            "functions": [],
            "statements": []
        }
        
        # Simple regex-based analysis
        import re
        
        # Find table creations
        table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)'
        for match in re.finditer(table_pattern, content, re.IGNORECASE):
            table_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            analysis["tables"].append({
                "name": table_name,
                "line_number": line_num
            })
        
        # Find view creations
        view_pattern = r'CREATE\s+VIEW\s+(\w+)'
        for match in re.finditer(view_pattern, content, re.IGNORECASE):
            view_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            analysis["views"].append({
                "name": view_name,
                "line_number": line_num
            })
        
        return analysis
    
    async def _analyze_generic_file(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Analyze generic text file.
        
        Args:
            content: File content
            file_path: File path
            
        Returns:
            Generic analysis results
        """
        lines = content.split('\n')
        
        analysis = {
            "word_count": len(content.split()),
            "character_count": len(content),
            "blank_lines": sum(1 for line in lines if not line.strip()),
            "comment_lines": 0,
            "code_lines": 0
        }
        
        # Estimate comment and code lines
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            elif stripped.startswith(('#', '//', '/*', '*', '--')):
                analysis["comment_lines"] += 1
            else:
                analysis["code_lines"] += 1
        
        return analysis
    
    async def _extract_insights(self, analysis_results: List[Dict[str, Any]], repo_path: Path) -> Dict[str, Any]:
        """Extract high-level insights from analysis results.
        
        Args:
            analysis_results: List of file analysis results
            repo_path: Repository path
            
        Returns:
            High-level insights
        """
        insights = {
            "language_distribution": {},
            "total_functions": 0,
            "total_classes": 0,
            "most_complex_files": [],
            "dependency_analysis": {},
            "code_quality_metrics": {}
        }
        
        # Language distribution
        for result in analysis_results:
            lang = result.get("language", "unknown")
            insights["language_distribution"][lang] = insights["language_distribution"].get(lang, 0) + 1
        
        # Count functions and classes
        for result in analysis_results:
            if "functions" in result:
                insights["total_functions"] += len(result["functions"])
            if "classes" in result:
                insights["total_classes"] += len(result["classes"])
        
        # Find most complex files
        complex_files = []
        for result in analysis_results:
            if "complexity_score" in result:
                complex_files.append({
                    "file_path": result["file_path"],
                    "complexity_score": result["complexity_score"]
                })
        
        complex_files.sort(key=lambda x: x["complexity_score"], reverse=True)
        insights["most_complex_files"] = complex_files[:10]
        
        # Basic dependency analysis
        all_imports = []
        for result in analysis_results:
            if "imports" in result:
                all_imports.extend(result["imports"])
        
        # Count import frequency
        import_counts = {}
        for imp in all_imports:
            module = imp.get("module", "unknown")
            import_counts[module] = import_counts.get(module, 0) + 1
        
        insights["dependency_analysis"] = {
            "total_imports": len(all_imports),
            "unique_modules": len(import_counts),
            "most_used_modules": sorted(import_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        }
        
        # Code quality metrics
        total_lines = sum(r.get("line_count", 0) for r in analysis_results)
        total_files = len(analysis_results)
        
        insights["code_quality_metrics"] = {
            "average_file_size": total_lines / total_files if total_files > 0 else 0,
            "total_lines_of_code": total_lines,
            "files_with_errors": sum(1 for r in analysis_results if "error" in r),
            "analysis_coverage": (total_files - sum(1 for r in analysis_results if "error" in r)) / total_files if total_files > 0 else 0
        }
        
        return insights

