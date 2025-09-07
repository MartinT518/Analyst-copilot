"""Code parser for extracting structured information from codebases."""

import logging
import os
import subprocess  # nosec B404
from typing import Any, Dict, List


logger = logging.getLogger(__name__)


class CodeParser:
    """Parser for extracting code structure and dependencies."""

    def __init__(self):
        """Initialize the code parser."""
        self.supported_languages = [
            "java",
            "python",
            "javascript",
            "typescript",
            "csharp",
            "go",
        ]

    async def parse(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse code content and extract structured information.

        Args:
            content: Code content or path to codebase
            metadata: Additional metadata

        Returns:
            List of parsed code documents
        """
        try:
            # Check if content is a file path
            if os.path.exists(content):
                return await self._parse_codebase(content, metadata)
            else:
                return await self._parse_code_content(content, metadata)

        except Exception as e:
            logger.error(f"Code parsing failed: {e}")
            return []

    async def _parse_codebase(
        self, codebase_path: str, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse an entire codebase using IntelliJ inspection.

        Args:
            codebase_path: Path to codebase
            metadata: Additional metadata

        Returns:
            List of parsed code documents
        """
        try:
            # Run IntelliJ inspection
            inspection_results = await self._run_intellij_inspection(codebase_path)

            # Parse inspection results
            parsed_documents = []
            for result in inspection_results:
                doc = {
                    "id": f"code_{result['file_path'].replace('/', '_')}",
                    "title": f"Code Analysis: {result['file_path']}",
                    "content": result["summary"],
                    "metadata": {
                        **metadata,
                        "source_type": "code",
                        "file_path": result["file_path"],
                        "language": result["language"],
                        "classes": result["classes"],
                        "methods": result["methods"],
                        "dependencies": result["dependencies"],
                        "complexity_score": result["complexity_score"],
                    },
                }
                parsed_documents.append(doc)

            return parsed_documents

        except Exception as e:
            logger.error(f"Codebase parsing failed: {e}")
            return []

    async def _run_intellij_inspection(self, codebase_path: str) -> List[Dict[str, Any]]:
        """Run IntelliJ inspection on codebase.

        Args:
            codebase_path: Path to codebase

        Returns:
            List of inspection results
        """
        try:
            # This would run IntelliJ's inspect.sh tool
            # For now, we'll simulate the results
            results = []

            # Find code files
            code_files = self._find_code_files(codebase_path)

            for file_path in code_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Analyze file
                    analysis = self._analyze_code_file(file_path, content)
                    results.append(analysis)

                except Exception as e:
                    logger.warning(f"Failed to analyze file {file_path}: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"IntelliJ inspection failed: {e}")
            return []

    def _find_code_files(self, codebase_path: str) -> List[str]:
        """Find code files in the codebase.

        Args:
            codebase_path: Path to codebase

        Returns:
            List of code file paths
        """
        code_files = []
        extensions = {
            ".java": "java",
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".cs": "csharp",
            ".go": "go",
        }

        for root, dirs, files in os.walk(codebase_path):
            # Skip common non-source directories
            dirs[:] = [
                d
                for d in dirs
                if d not in [".git", "node_modules", "__pycache__", "target", "build"]
            ]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                if ext in extensions:
                    code_files.append(file_path)

        return code_files

    def _analyze_code_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Analyze a single code file.

        Args:
            file_path: Path to file
            content: File content

        Returns:
            Analysis results
        """
        ext = os.path.splitext(file_path)[1].lower()
        language = {
            ".java": "java",
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".cs": "csharp",
            ".go": "go",
        }.get(ext, "unknown")

        # Basic analysis
        classes = self._extract_classes(content, language)
        methods = self._extract_methods(content, language)
        dependencies = self._extract_dependencies(content, language)
        complexity = self._calculate_complexity(content)

        # Generate natural language summary
        summary = self._generate_code_summary(file_path, language, classes, methods, dependencies)

        return {
            "file_path": file_path,
            "language": language,
            "classes": classes,
            "methods": methods,
            "dependencies": dependencies,
            "complexity_score": complexity,
            "summary": summary,
        }

    def _extract_classes(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Extract class information from code."""
        classes = []

        if language == "java":
            import re

            class_pattern = r"class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?"
            for match in re.finditer(class_pattern, content):
                classes.append(
                    {
                        "name": match.group(1),
                        "extends": match.group(2),
                        "implements": (match.group(3).split(",") if match.group(3) else []),
                    }
                )

        elif language == "python":
            import re

            class_pattern = r"class\s+(\w+)(?:\(([^)]+)\))?:"
            for match in re.finditer(class_pattern, content):
                classes.append(
                    {
                        "name": match.group(1),
                        "inherits": match.group(2).split(",") if match.group(2) else [],
                    }
                )

        return classes

    def _extract_methods(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Extract method information from code."""
        methods = []

        if language == "java":
            import re

            method_pattern = (
                r"(?:public|private|protected)?\s*(?:static)?\s*(\w+)\s+(\w+)\s*\([^)]*\)"
            )
            for match in re.finditer(method_pattern, content):
                methods.append(
                    {
                        "name": match.group(2),
                        "return_type": match.group(1),
                        "visibility": ("public" if "public" in match.group(0) else "private"),
                    }
                )

        elif language == "python":
            import re

            method_pattern = r"def\s+(\w+)\s*\([^)]*\):"
            for match in re.finditer(method_pattern, content):
                methods.append({"name": match.group(1), "return_type": "unknown"})

        return methods

    def _extract_dependencies(self, content: str, language: str) -> List[str]:
        """Extract dependencies from code."""
        dependencies = []

        if language == "java":
            import re

            import_pattern = r"import\s+([^;]+);"
            for match in re.finditer(import_pattern, content):
                dependencies.append(match.group(1))

        elif language == "python":
            import re

            import_pattern = r"(?:from\s+(\S+)\s+)?import\s+(\S+)"
            for match in re.finditer(import_pattern, content):
                if match.group(1):
                    dependencies.append(f"{match.group(1)}.{match.group(2)}")
                else:
                    dependencies.append(match.group(2))

        return dependencies

    def _calculate_complexity(self, content: str) -> int:
        """Calculate code complexity score."""
        # Simple complexity calculation
        complexity = 0

        # Count control structures
        complexity += content.count("if")
        complexity += content.count("for")
        complexity += content.count("while")
        complexity += content.count("switch")
        complexity += content.count("case")
        complexity += content.count("catch")
        complexity += content.count("try")

        return complexity

    def _generate_code_summary(
        self,
        file_path: str,
        language: str,
        classes: List,
        methods: List,
        dependencies: List,
    ) -> str:
        """Generate natural language summary of code."""
        summary_parts = [f"Code file {os.path.basename(file_path)} written in {language}."]

        if classes:
            class_names = [cls["name"] for cls in classes]
            summary_parts.append(f"Contains {len(classes)} class(es): {', '.join(class_names)}.")

        if methods:
            method_names = [method["name"] for method in methods[:5]]  # First 5 methods
            summary_parts.append(
                f"Defines {len(methods)} method(s) including: {', '.join(method_names)}."
            )

        if dependencies:
            dep_names = dependencies[:5]  # First 5 dependencies
            summary_parts.append(f"Depends on: {', '.join(dep_names)}.")

        return " ".join(summary_parts)

    async def _parse_code_content(
        self, content: str, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse code content directly."""
        # For direct code content, we'll do basic analysis
        analysis = self._analyze_code_file("inline_code", content)

        doc = {
            "id": "inline_code",
            "title": "Inline Code Analysis",
            "content": analysis["summary"],
            "metadata": {
                **metadata,
                "source_type": "code",
                "language": analysis["language"],
                "classes": analysis["classes"],
                "methods": analysis["methods"],
                "dependencies": analysis["dependencies"],
                "complexity_score": analysis["complexity_score"],
            },
        }

        return [doc]
