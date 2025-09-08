"""Utility functions for ACP CLI."""

import json
import yaml
from typing import Any, Dict, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from tabulate import tabulate

from .config import config_manager


console = Console()


def format_output(data: Any, format_type: str = None) -> str:
    """Format data for output.
    
    Args:
        data: Data to format
        format_type: Output format (table, json, yaml)
        
    Returns:
        Formatted string
    """
    if format_type is None:
        config = config_manager.load_config()
        format_type = config.output_format
    
    if format_type == "json":
        return json.dumps(data, indent=2, default=str)
    elif format_type == "yaml":
        return yaml.dump(data, default_flow_style=False)
    elif format_type == "table":
        return format_table(data)
    else:
        return str(data)


def format_table(data: Any) -> str:
    """Format data as a table.
    
    Args:
        data: Data to format
        
    Returns:
        Formatted table string
    """
    if isinstance(data, dict):
        if "items" in data and isinstance(data["items"], list):
            # Handle paginated responses
            return format_table(data["items"])
        else:
            # Convert dict to list of key-value pairs
            table_data = [[k, v] for k, v in data.items()]
            return tabulate(table_data, headers=["Key", "Value"], tablefmt="grid")
    
    elif isinstance(data, list):
        if not data:
            return "No data available"
        
        if isinstance(data[0], dict):
            # List of dictionaries - use keys as headers
            headers = list(data[0].keys())
            rows = [[item.get(header, "") for header in headers] for item in data]
            return tabulate(rows, headers=headers, tablefmt="grid")
        else:
            # List of simple values
            return tabulate([[item] for item in data], headers=["Value"], tablefmt="grid")
    
    else:
        return str(data)


def print_success(message: str) -> None:
    """Print success message.
    
    Args:
        message: Success message
    """
    console.print(f"✅ {message}", style="green")


def print_error(message: str) -> None:
    """Print error message.
    
    Args:
        message: Error message
    """
    console.print(f"❌ {message}", style="red")


def print_warning(message: str) -> None:
    """Print warning message.
    
    Args:
        message: Warning message
    """
    console.print(f"⚠️  {message}", style="yellow")


def print_info(message: str) -> None:
    """Print info message.
    
    Args:
        message: Info message
    """
    console.print(f"ℹ️  {message}", style="blue")


def print_panel(title: str, content: str, style: str = "blue") -> None:
    """Print content in a panel.
    
    Args:
        title: Panel title
        content: Panel content
        style: Panel style
    """
    panel = Panel(content, title=title, border_style=style)
    console.print(panel)


def print_table(data: List[Dict[str, Any]], title: str = None) -> None:
    """Print data as a rich table.
    
    Args:
        data: Data to display
        title: Table title
    """
    if not data:
        print_warning("No data to display")
        return
    
    table = Table(title=title)
    
    # Add columns
    headers = list(data[0].keys())
    for header in headers:
        table.add_column(header.replace("_", " ").title())
    
    # Add rows
    for item in data:
        row = [str(item.get(header, "")) for header in headers]
        table.add_row(*row)
    
    console.print(table)


def confirm_action(message: str) -> bool:
    """Ask for user confirmation.
    
    Args:
        message: Confirmation message
        
    Returns:
        True if confirmed, False otherwise
    """
    response = console.input(f"{message} [y/N]: ")
    return response.lower() in ("y", "yes")


def show_progress(description: str):
    """Show a progress spinner.
    
    Args:
        description: Progress description
        
    Returns:
        Progress context manager
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    )


def validate_file_path(file_path: str) -> bool:
    """Validate that a file path exists.
    
    Args:
        file_path: Path to validate
        
    Returns:
        True if valid, False otherwise
    """
    from pathlib import Path
    return Path(file_path).exists()


def get_file_size(file_path: str) -> int:
    """Get file size in bytes.
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in bytes
    """
    from pathlib import Path
    return Path(file_path).stat().st_size


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def parse_key_value_pairs(pairs: List[str]) -> Dict[str, str]:
    """Parse key=value pairs from command line.
    
    Args:
        pairs: List of key=value strings
        
    Returns:
        Dictionary of parsed pairs
    """
    result = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid key=value pair: {pair}")
        key, value = pair.split("=", 1)
        result[key.strip()] = value.strip()
    return result

