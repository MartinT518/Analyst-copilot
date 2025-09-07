"""File utilities for handling uploads and file operations."""

import hashlib
import logging
import mimetypes
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import aiofiles
from fastapi import UploadFile

logger = logging.getLogger(__name__)


def detect_file_type(filename: Optional[str], content_type: Optional[str]) -> str:
    """
    Detect file type from filename and content type.

    Args:
        filename: Original filename
        content_type: MIME content type

    Returns:
        str: Detected file type
    """
    if not filename and not content_type:
        return "unknown"

    # Check by file extension first
    if filename:
        ext = Path(filename).suffix.lower()

        if ext == ".csv":
            return "jira_csv"  # Assume CSV is Jira export
        elif ext in [".html", ".htm"]:
            return "confluence_html"
        elif ext == ".xml":
            return "confluence_xml"
        elif ext == ".pdf":
            return "pdf"
        elif ext in [".md", ".markdown"]:
            return "markdown"
        elif ext == ".txt":
            return "paste"
        elif ext == ".zip":
            return "zip"
        elif ext in [".doc", ".docx"]:
            return "document"
        elif ext in [".json"]:
            return "json"

    # Check by MIME type
    if content_type:
        if "text/csv" in content_type:
            return "jira_csv"
        elif "text/html" in content_type:
            return "confluence_html"
        elif "application/xml" in content_type or "text/xml" in content_type:
            return "confluence_xml"
        elif "application/pdf" in content_type:
            return "pdf"
        elif "text/markdown" in content_type:
            return "markdown"
        elif "text/plain" in content_type:
            return "paste"
        elif "application/zip" in content_type:
            return "zip"
        elif "application/json" in content_type:
            return "json"

    return "unknown"


async def save_upload_file(file: UploadFile, upload_dir: str) -> str:
    """
    Save uploaded file to disk.

    Args:
        file: FastAPI UploadFile object
        upload_dir: Directory to save file

    Returns:
        str: Path to saved file
    """
    try:
        # Ensure upload directory exists
        os.makedirs(upload_dir, exist_ok=True)

        # Generate safe filename
        safe_filename = generate_safe_filename(file.filename or "upload")
        file_path = os.path.join(upload_dir, safe_filename)

        # Save file
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        logger.info(f"Saved uploaded file: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise


def generate_safe_filename(filename: str) -> str:
    """
    Generate a safe filename for storage.

    Args:
        filename: Original filename

    Returns:
        str: Safe filename
    """
    # Get file extension
    path = Path(filename)
    name = path.stem
    ext = path.suffix

    # Clean filename
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).rstrip()
    safe_name = safe_name.replace(" ", "_")

    # Limit length
    if len(safe_name) > 50:
        safe_name = safe_name[:50]

    # Add timestamp to avoid conflicts
    import time

    timestamp = str(int(time.time()))

    return f"{safe_name}_{timestamp}{ext}"


def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """
    Calculate hash of a file.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256)

    Returns:
        str: File hash
    """
    hash_func = hashlib.new(algorithm)

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Get information about a file.

    Args:
        file_path: Path to file

    Returns:
        Dict[str, Any]: File information
    """
    try:
        stat = os.stat(file_path)

        info = {
            "path": file_path,
            "name": os.path.basename(file_path),
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "extension": Path(file_path).suffix.lower(),
            "mime_type": mimetypes.guess_type(file_path)[0],
        }

        # Add hash for small files
        if stat.st_size < 10 * 1024 * 1024:  # 10MB
            info["sha256"] = calculate_file_hash(file_path)

        return info

    except Exception as e:
        logger.error(f"Failed to get file info for {file_path}: {e}")
        return {"path": file_path, "error": str(e)}


def ensure_directory(directory: str) -> bool:
    """
    Ensure directory exists, create if necessary.

    Args:
        directory: Directory path

    Returns:
        bool: True if directory exists or was created
    """
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        return False


def cleanup_old_files(directory: str, max_age_days: int = 7) -> int:
    """
    Clean up old files in a directory.

    Args:
        directory: Directory to clean
        max_age_days: Maximum age in days

    Returns:
        int: Number of files deleted
    """
    if not os.path.exists(directory):
        return 0

    import time

    current_time = time.time()
    max_age_seconds = max_age_days * 24 * 60 * 60
    deleted_count = 0

    try:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)

            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)

                if file_age > max_age_seconds:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"Deleted old file: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete {file_path}: {e}")

        logger.info(f"Cleaned up {deleted_count} old files from {directory}")
        return deleted_count

    except Exception as e:
        logger.error(f"Failed to cleanup directory {directory}: {e}")
        return 0


def get_directory_size(directory: str) -> int:
    """
    Get total size of directory in bytes.

    Args:
        directory: Directory path

    Returns:
        int: Total size in bytes
    """
    total_size = 0

    try:
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(file_path)
                except (OSError, FileNotFoundError):
                    continue
    except Exception as e:
        logger.error(f"Failed to calculate directory size for {directory}: {e}")

    return total_size


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        str: Formatted size
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math

    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    return f"{s} {size_names[i]}"


def is_text_file(file_path: str) -> bool:
    """
    Check if file is a text file.

    Args:
        file_path: Path to file

    Returns:
        bool: True if text file
    """
    try:
        # Check by extension first
        text_extensions = {
            ".txt",
            ".md",
            ".csv",
            ".json",
            ".xml",
            ".html",
            ".htm",
            ".py",
            ".js",
            ".css",
            ".yaml",
            ".yml",
            ".ini",
            ".cfg",
        }

        ext = Path(file_path).suffix.lower()
        if ext in text_extensions:
            return True

        # Check by reading first few bytes
        with open(file_path, "rb") as f:
            chunk = f.read(1024)

        # Check for null bytes (binary indicator)
        if b"\x00" in chunk:
            return False

        # Try to decode as UTF-8
        try:
            chunk.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    except Exception:
        return False


def extract_zip_file(zip_path: str, extract_dir: str) -> List[str]:
    """
    Extract ZIP file and return list of extracted files.

    Args:
        zip_path: Path to ZIP file
        extract_dir: Directory to extract to

    Returns:
        List[str]: List of extracted file paths
    """
    import zipfile

    extracted_files = []

    try:
        ensure_directory(extract_dir)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # Get list of files
            file_list = zip_ref.namelist()

            # Extract files
            for file_name in file_list:
                # Skip directories
                if file_name.endswith("/"):
                    continue

                # Extract file
                zip_ref.extract(file_name, extract_dir)
                extracted_path = os.path.join(extract_dir, file_name)
                extracted_files.append(extracted_path)

        logger.info(f"Extracted {len(extracted_files)} files from {zip_path}")
        return extracted_files

    except Exception as e:
        logger.error(f"Failed to extract ZIP file {zip_path}: {e}")
        return []


def create_temp_file(
    suffix: str = "", prefix: str = "acp_", dir: Optional[str] = None
) -> Tuple[int, str]:
    """
    Create a temporary file.

    Args:
        suffix: File suffix
        prefix: File prefix
        dir: Directory for temp file

    Returns:
        Tuple[int, str]: File descriptor and path
    """
    return tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)


def create_temp_directory(prefix: str = "acp_", dir: Optional[str] = None) -> str:
    """
    Create a temporary directory.

    Args:
        prefix: Directory prefix
        dir: Parent directory

    Returns:
        str: Path to temporary directory
    """
    return tempfile.mkdtemp(prefix=prefix, dir=dir)


def safe_remove_file(file_path: str) -> bool:
    """
    Safely remove a file.

    Args:
        file_path: Path to file

    Returns:
        bool: True if removed successfully
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Removed file: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to remove file {file_path}: {e}")
        return False


def safe_remove_directory(dir_path: str) -> bool:
    """
    Safely remove a directory and its contents.

    Args:
        dir_path: Path to directory

    Returns:
        bool: True if removed successfully
    """
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            logger.debug(f"Removed directory: {dir_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to remove directory {dir_path}: {e}")
        return False


def validate_file_path(
    file_path: str, allowed_dirs: Optional[List[str]] = None
) -> bool:
    """
    Validate file path for security.

    Args:
        file_path: Path to validate
        allowed_dirs: List of allowed directories

    Returns:
        bool: True if path is safe
    """
    try:
        # Resolve path to prevent directory traversal
        resolved_path = os.path.realpath(file_path)

        # Check for directory traversal attempts
        if ".." in file_path or file_path.startswith("/"):
            return False

        # Check against allowed directories
        if allowed_dirs:
            allowed = False
            for allowed_dir in allowed_dirs:
                allowed_dir = os.path.realpath(allowed_dir)
                if resolved_path.startswith(allowed_dir):
                    allowed = True
                    break

            if not allowed:
                return False

        return True

    except Exception:
        return False


class FileManager:
    """File manager for handling file operations."""

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        ensure_directory(self.base_dir)

    def get_file_path(self, filename: str) -> str:
        """Get full path for a filename."""
        return os.path.join(self.base_dir, filename)

    def save_file(self, filename: str, content: bytes) -> str:
        """Save file content."""
        file_path = self.get_file_path(filename)

        with open(file_path, "wb") as f:
            f.write(content)

        return file_path

    def read_file(self, filename: str) -> bytes:
        """Read file content."""
        file_path = self.get_file_path(filename)

        with open(file_path, "rb") as f:
            return f.read()

    def delete_file(self, filename: str) -> bool:
        """Delete a file."""
        file_path = self.get_file_path(filename)
        return safe_remove_file(file_path)

    def list_files(self) -> List[str]:
        """List all files in the managed directory."""
        try:
            return [
                f
                for f in os.listdir(self.base_dir)
                if os.path.isfile(os.path.join(self.base_dir, f))
            ]
        except Exception:
            return []

    def cleanup_old_files(self, max_age_days: int = 7) -> int:
        """Clean up old files."""
        return cleanup_old_files(self.base_dir, max_age_days)

    def get_directory_info(self) -> Dict[str, Any]:
        """Get information about the managed directory."""
        return {
            "path": self.base_dir,
            "size": get_directory_size(self.base_dir),
            "size_formatted": format_file_size(get_directory_size(self.base_dir)),
            "file_count": len(self.list_files()),
        }
