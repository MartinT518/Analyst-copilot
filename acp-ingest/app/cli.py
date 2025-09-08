"""Command Line Interface for ACP Ingest service."""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.json import JSON

console = Console()


class ACPClient:
    """Client for interacting with ACP Ingest API."""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {}
        
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def upload_file(
        self,
        file_path: str,
        origin: str,
        sensitivity: str,
        source_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Upload a file for ingestion."""
        async with httpx.AsyncClient(timeout=300.0) as client:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                data = {
                    'origin': origin,
                    'sensitivity': sensitivity,
                    'metadata': json.dumps(metadata or {})
                }
                
                if source_type:
                    data['source_type'] = source_type
                
                response = await client.post(
                    f"{self.base_url}/ingest/upload",
                    files=files,
                    data=data,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
    
    async def paste_text(
        self,
        text: str,
        origin: str,
        sensitivity: str,
        ticket_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Paste text for ingestion."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            data = {
                'text': text,
                'origin': origin,
                'sensitivity': sensitivity,
                'metadata': metadata or {}
            }
            
            if ticket_id:
                data['ticket_id'] = ticket_id
            
            response = await client.post(
                f"{self.base_url}/ingest/paste",
                json=data,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/ingest/status/{job_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def list_jobs(
        self,
        skip: int = 0,
        limit: int = 10,
        status: Optional[str] = None,
        origin: Optional[str] = None
    ) -> Dict[str, Any]:
        """List jobs."""
        async with httpx.AsyncClient() as client:
            params = {'skip': skip, 'limit': limit}
            if status:
                params['status'] = status
            if origin:
                params['origin'] = origin
            
            response = await client.get(
                f"{self.base_url}/ingest/jobs",
                params=params,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search knowledge chunks."""
        async with httpx.AsyncClient() as client:
            data = {
                'query': query,
                'limit': limit,
                'similarity_threshold': similarity_threshold,
                'filters': filters or {}
            }
            
            response = await client.post(
                f"{self.base_url}/search",
                json=data,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()


def get_client() -> ACPClient:
    """Get ACP client with configuration."""
    base_url = os.getenv('ACP_BASE_URL', 'http://localhost:8000')
    api_key = os.getenv('ACP_API_KEY')
    
    return ACPClient(base_url=base_url, api_key=api_key)


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """ACP Ingest CLI - On-premises AI-powered analysis system."""
    pass


@cli.command()
@click.option('--source', '-s', required=True, help='Path to file or directory to ingest')
@click.option('--origin', '-o', required=True, help='Customer or source identifier')
@click.option('--sensitivity', '-l', 
              type=click.Choice(['public', 'internal', 'confidential', 'restricted']),
              default='internal', help='Data sensitivity level')
@click.option('--source-type', '-t', help='Source type (auto-detected if not provided)')
@click.option('--metadata', '-m', help='Additional metadata as JSON string')
@click.option('--wait', '-w', is_flag=True, help='Wait for processing to complete')
def ingest(source: str, origin: str, sensitivity: str, source_type: Optional[str], 
           metadata: Optional[str], wait: bool):
    """Ingest files or directories."""
    
    async def _ingest():
        client = get_client()
        
        # Parse metadata
        metadata_dict = {}
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON in metadata[/red]")
                sys.exit(1)
        
        source_path = Path(source)
        
        if not source_path.exists():
            console.print(f"[red]Source path does not exist: {source}[/red]")
            sys.exit(1)
        
        jobs = []
        
        if source_path.is_file():
            # Single file
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"Uploading {source_path.name}...", total=None)
                
                try:
                    result = await client.upload_file(
                        file_path=str(source_path),
                        origin=origin,
                        sensitivity=sensitivity,
                        source_type=source_type,
                        metadata=metadata_dict
                    )
                    jobs.append(result)
                    progress.update(task, description=f"✓ Uploaded {source_path.name}")
                    
                except Exception as e:
                    console.print(f"[red]Upload failed: {e}[/red]")
                    sys.exit(1)
        
        elif source_path.is_dir():
            # Directory - find all supported files
            supported_extensions = {'.csv', '.html', '.htm', '.xml', '.pdf', '.md', '.txt', '.zip'}
            files = [f for f in source_path.rglob('*') 
                    if f.is_file() and f.suffix.lower() in supported_extensions]
            
            if not files:
                console.print(f"[yellow]No supported files found in {source}[/yellow]")
                return
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                for file_path in files:
                    task = progress.add_task(f"Uploading {file_path.name}...", total=None)
                    
                    try:
                        result = await client.upload_file(
                            file_path=str(file_path),
                            origin=origin,
                            sensitivity=sensitivity,
                            source_type=source_type,
                            metadata=metadata_dict
                        )
                        jobs.append(result)
                        progress.update(task, description=f"✓ Uploaded {file_path.name}")
                        
                    except Exception as e:
                        console.print(f"[red]Failed to upload {file_path.name}: {e}[/red]")
                        continue
        
        # Display results
        if jobs:
            table = Table(title="Ingestion Jobs")
            table.add_column("Job ID", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Message")
            
            for job in jobs:
                table.add_row(
                    job['job_id'],
                    job['status'],
                    job['message']
                )
            
            console.print(table)
            
            # Wait for completion if requested
            if wait:
                await _wait_for_jobs(client, [job['job_id'] for job in jobs])
    
    asyncio.run(_ingest())


@cli.command()
@click.option('--text', '-t', help='Text content to ingest (or read from stdin)')
@click.option('--origin', '-o', required=True, help='Customer or source identifier')
@click.option('--sensitivity', '-l',
              type=click.Choice(['public', 'internal', 'confidential', 'restricted']),
              default='internal', help='Data sensitivity level')
@click.option('--ticket-id', help='Ticket or document ID')
@click.option('--metadata', '-m', help='Additional metadata as JSON string')
@click.option('--wait', '-w', is_flag=True, help='Wait for processing to complete')
def paste(text: Optional[str], origin: str, sensitivity: str, ticket_id: Optional[str],
          metadata: Optional[str], wait: bool):
    """Ingest pasted text content."""
    
    async def _paste():
        client = get_client()
        
        # Get text content
        if not text:
            if sys.stdin.isatty():
                console.print("[yellow]Enter text content (Ctrl+D to finish):[/yellow]")
            text_content = sys.stdin.read().strip()
        else:
            text_content = text
        
        if not text_content:
            console.print("[red]No text content provided[/red]")
            sys.exit(1)
        
        # Parse metadata
        metadata_dict = {}
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON in metadata[/red]")
                sys.exit(1)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing text...", total=None)
            
            try:
                result = await client.paste_text(
                    text=text_content,
                    origin=origin,
                    sensitivity=sensitivity,
                    ticket_id=ticket_id,
                    metadata=metadata_dict
                )
                
                progress.update(task, description="✓ Text processed")
                
                console.print(Panel(
                    f"Job ID: {result['job_id']}\n"
                    f"Status: {result['status']}\n"
                    f"Message: {result['message']}",
                    title="Paste Result"
                ))
                
                if wait:
                    await _wait_for_jobs(client, [result['job_id']])
                    
            except Exception as e:
                console.print(f"[red]Paste failed: {e}[/red]")
                sys.exit(1)
    
    asyncio.run(_paste())


@cli.command()
@click.argument('job_id', required=False)
@click.option('--status', '-s', help='Filter by status')
@click.option('--origin', '-o', help='Filter by origin')
@click.option('--limit', '-l', default=10, help='Maximum number of jobs to show')
def status(job_id: Optional[str], status: Optional[str], origin: Optional[str], limit: int):
    """Check job status or list jobs."""
    
    async def _status():
        client = get_client()
        
        if job_id:
            # Get specific job status
            try:
                result = await client.get_job_status(job_id)
                
                console.print(Panel(
                    JSON.from_data(result),
                    title=f"Job Status: {job_id}"
                ))
                
            except Exception as e:
                console.print(f"[red]Failed to get job status: {e}[/red]")
                sys.exit(1)
        
        else:
            # List jobs
            try:
                result = await client.list_jobs(
                    limit=limit,
                    status=status,
                    origin=origin
                )
                
                if not result:
                    console.print("[yellow]No jobs found[/yellow]")
                    return
                
                table = Table(title="Jobs")
                table.add_column("Job ID", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("Origin")
                table.add_column("Source Type")
                table.add_column("Chunks", justify="right")
                table.add_column("Created")
                
                for job in result:
                    table.add_row(
                        str(job['id'])[:8] + "...",
                        job['status'],
                        job['origin'],
                        job['source_type'],
                        str(job['chunks_created']),
                        job['created_at'][:19]
                    )
                
                console.print(table)
                
            except Exception as e:
                console.print(f"[red]Failed to list jobs: {e}[/red]")
                sys.exit(1)
    
    asyncio.run(_status())


@cli.command()
@click.argument('query')
@click.option('--limit', '-l', default=5, help='Maximum number of results')
@click.option('--threshold', '-t', default=0.7, help='Similarity threshold')
@click.option('--filters', '-f', help='Search filters as JSON string')
def search(query: str, limit: int, threshold: float, filters: Optional[str]):
    """Search knowledge chunks."""
    
    async def _search():
        client = get_client()
        
        # Parse filters
        filters_dict = {}
        if filters:
            try:
                filters_dict = json.loads(filters)
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON in filters[/red]")
                sys.exit(1)
        
        try:
            result = await client.search(
                query=query,
                limit=limit,
                similarity_threshold=threshold,
                filters=filters_dict
            )
            
            if not result['results']:
                console.print("[yellow]No results found[/yellow]")
                return
            
            console.print(f"[green]Found {result['total_results']} results in {result['processing_time_ms']}ms[/green]\n")
            
            for i, item in enumerate(result['results'], 1):
                chunk = item['chunk']
                score = item['similarity_score']
                
                console.print(Panel(
                    f"[bold]Score:[/bold] {score:.3f}\n"
                    f"[bold]Source:[/bold] {chunk['source_type']} - {chunk['metadata'].get('origin', 'Unknown')}\n"
                    f"[bold]Content:[/bold]\n{chunk['chunk_text'][:500]}{'...' if len(chunk['chunk_text']) > 500 else ''}",
                    title=f"Result {i}"
                ))
                
        except Exception as e:
            console.print(f"[red]Search failed: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(_search())


@cli.command()
def health():
    """Check service health."""
    
    async def _health():
        client = get_client()
        
        try:
            result = await client.health_check()
            
            status_color = "green" if result['status'] == 'healthy' else "red"
            console.print(f"[{status_color}]Service Status: {result['status']}[/{status_color}]")
            console.print(f"Version: {result['version']}")
            console.print(f"Timestamp: {result['timestamp']}")
            
            # Service status table
            table = Table(title="Service Health")
            table.add_column("Service", style="cyan")
            table.add_column("Status", style="green")
            
            for service, status in result['services'].items():
                color = "green" if status == 'healthy' else "red"
                table.add_row(service, f"[{color}]{status}[/{color}]")
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]Health check failed: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(_health())


async def _wait_for_jobs(client: ACPClient, job_ids: list):
    """Wait for jobs to complete."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        pending_jobs = set(job_ids)
        task = progress.add_task(f"Waiting for {len(pending_jobs)} jobs...", total=None)
        
        while pending_jobs:
            completed_jobs = set()
            
            for job_id in pending_jobs:
                try:
                    result = await client.get_job_status(job_id)
                    status = result['status']
                    
                    if status in ['completed', 'failed']:
                        completed_jobs.add(job_id)
                        
                        if status == 'completed':
                            console.print(f"[green]✓ Job {job_id[:8]}... completed ({result['chunks_created']} chunks)[/green]")
                        else:
                            console.print(f"[red]✗ Job {job_id[:8]}... failed: {result.get('error_message', 'Unknown error')}[/red]")
                
                except Exception as e:
                    console.print(f"[red]Failed to check job {job_id[:8]}...: {e}[/red]")
                    completed_jobs.add(job_id)
            
            pending_jobs -= completed_jobs
            
            if pending_jobs:
                progress.update(task, description=f"Waiting for {len(pending_jobs)} jobs...")
                await asyncio.sleep(2)
        
        progress.update(task, description="✓ All jobs completed")


if __name__ == '__main__':
    cli()

