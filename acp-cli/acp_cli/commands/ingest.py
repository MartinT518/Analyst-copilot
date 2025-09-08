"""Commands for interacting with the ingest service."""

import typer
from typing import Optional, List
from pathlib import Path

from ..client import IngestClient
from ..utils import (
    print_success, print_error, print_info, print_table,
    format_output, validate_file_path, get_file_size,
    format_file_size, show_progress, parse_key_value_pairs
)

app = typer.Typer(help="Interact with the ingest service")


@app.command()
def upload(
    file_path: str = typer.Argument(..., help="Path to file to upload"),
    metadata: Optional[List[str]] = typer.Option(None, "--metadata", "-m", help="Metadata as key=value pairs"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """Upload a document for ingestion."""
    
    # Validate file path
    if not validate_file_path(file_path):
        print_error(f"File not found: {file_path}")
        raise typer.Exit(1)
    
    # Parse metadata
    metadata_dict = {}
    if metadata:
        try:
            metadata_dict = parse_key_value_pairs(metadata)
        except ValueError as e:
            print_error(str(e))
            raise typer.Exit(1)
    
    # Show file info
    file_size = get_file_size(file_path)
    print_info(f"Uploading file: {file_path} ({format_file_size(file_size)})")
    
    if metadata_dict:
        print_info(f"Metadata: {metadata_dict}")
    
    try:
        with IngestClient() as client:
            with show_progress("Uploading file...") as progress:
                task = progress.add_task("Uploading...", total=None)
                response = client.upload_document(file_path, metadata_dict)
                progress.remove_task(task)
            
            print_success("File uploaded successfully")
            print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Upload failed: {str(e)}")
        raise typer.Exit(1)


@app.command()
def paste(
    content: str = typer.Argument(..., help="Content to paste"),
    content_type: str = typer.Option("text", "--type", "-t", help="Content type"),
    metadata: Optional[List[str]] = typer.Option(None, "--metadata", "-m", help="Metadata as key=value pairs"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """Paste content for ingestion."""
    
    # Parse metadata
    metadata_dict = {}
    if metadata:
        try:
            metadata_dict = parse_key_value_pairs(metadata)
        except ValueError as e:
            print_error(str(e))
            raise typer.Exit(1)
    
    print_info(f"Pasting content ({len(content)} characters, type: {content_type})")
    
    if metadata_dict:
        print_info(f"Metadata: {metadata_dict}")
    
    try:
        with IngestClient() as client:
            with show_progress("Processing content...") as progress:
                task = progress.add_task("Processing...", total=None)
                response = client.paste_content(content, content_type, metadata_dict)
                progress.remove_task(task)
            
            print_success("Content processed successfully")
            print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Paste failed: {str(e)}")
        raise typer.Exit(1)


@app.command()
def status(
    job_id: str = typer.Argument(..., help="Job ID to check"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """Get status of an ingestion job."""
    
    try:
        with IngestClient() as client:
            response = client.get_job_status(job_id)
            print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Failed to get job status: {str(e)}")
        raise typer.Exit(1)


@app.command()
def jobs(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of jobs to return"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """List ingestion jobs."""
    
    try:
        with IngestClient() as client:
            response = client.list_jobs(limit, offset)
            
            if output_format == "table" or output_format is None:
                jobs_data = response.get("items", [])
                if jobs_data:
                    print_table(jobs_data, "Ingestion Jobs")
                else:
                    print_info("No jobs found")
            else:
                print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Failed to list jobs: {str(e)}")
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of results to return"),
    filters: Optional[List[str]] = typer.Option(None, "--filter", help="Search filters as key=value pairs"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """Search the knowledge base."""
    
    # Parse filters
    filters_dict = {}
    if filters:
        try:
            filters_dict = parse_key_value_pairs(filters)
        except ValueError as e:
            print_error(str(e))
            raise typer.Exit(1)
    
    print_info(f"Searching for: '{query}' (limit: {limit})")
    
    if filters_dict:
        print_info(f"Filters: {filters_dict}")
    
    try:
        with IngestClient() as client:
            with show_progress("Searching...") as progress:
                task = progress.add_task("Searching...", total=None)
                response = client.search(query, limit, filters_dict)
                progress.remove_task(task)
            
            results = response.get("results", [])
            print_success(f"Found {len(results)} results")
            
            if output_format == "table" or output_format is None:
                if results:
                    # Format results for table display
                    table_data = []
                    for result in results:
                        table_data.append({
                            "Score": f"{result.get('score', 0):.3f}",
                            "Source": result.get('metadata', {}).get('source', 'Unknown'),
                            "Content": result.get('content', '')[:100] + "..." if len(result.get('content', '')) > 100 else result.get('content', '')
                        })
                    print_table(table_data, "Search Results")
                else:
                    print_info("No results found")
            else:
                print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Search failed: {str(e)}")
        raise typer.Exit(1)


@app.command()
def health():
    """Check ingest service health."""
    
    try:
        with IngestClient() as client:
            response = client.health_check()
            
            status = response.get("status", "unknown")
            if status == "healthy":
                print_success(f"Ingest service is {status}")
            else:
                print_error(f"Ingest service is {status}")
                if "error" in response:
                    print_error(f"Error: {response['error']}")
            
            print(format_output(response))
            
    except Exception as e:
        print_error(f"Health check failed: {str(e)}")
        raise typer.Exit(1)

