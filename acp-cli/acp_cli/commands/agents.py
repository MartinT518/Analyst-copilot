"""Commands for interacting with the agents service."""

import typer
from typing import Optional, List
import json

from ..client import AgentsClient
from ..utils import (
    print_success, print_error, print_info, print_table,
    format_output, show_progress, parse_key_value_pairs
)

app = typer.Typer(help="Interact with the agents service")


@app.command()
def start(
    workflow_type: str = typer.Argument(..., help="Type of workflow (clarifier, synthesizer, taskmaster, verifier)"),
    input_file: Optional[str] = typer.Option(None, "--input", "-i", help="JSON file with input data"),
    input_data: Optional[List[str]] = typer.Option(None, "--data", "-d", help="Input data as key=value pairs"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """Start an agent workflow."""
    
    # Validate workflow type
    valid_workflows = ["clarifier", "synthesizer", "taskmaster", "verifier"]
    if workflow_type not in valid_workflows:
        print_error(f"Invalid workflow type. Must be one of: {', '.join(valid_workflows)}")
        raise typer.Exit(1)
    
    # Parse input data
    input_dict = {}
    
    if input_file:
        try:
            with open(input_file, 'r') as f:
                input_dict = json.load(f)
        except Exception as e:
            print_error(f"Failed to read input file: {str(e)}")
            raise typer.Exit(1)
    
    if input_data:
        try:
            data_dict = parse_key_value_pairs(input_data)
            input_dict.update(data_dict)
        except ValueError as e:
            print_error(str(e))
            raise typer.Exit(1)
    
    if not input_dict:
        print_error("No input data provided. Use --input or --data options.")
        raise typer.Exit(1)
    
    print_info(f"Starting {workflow_type} workflow")
    print_info(f"Input data: {input_dict}")
    
    try:
        with AgentsClient() as client:
            with show_progress("Starting workflow...") as progress:
                task = progress.add_task("Starting...", total=None)
                response = client.start_workflow(workflow_type, input_dict)
                progress.remove_task(task)
            
            print_success("Workflow started successfully")
            print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Failed to start workflow: {str(e)}")
        raise typer.Exit(1)


@app.command()
def status(
    workflow_id: str = typer.Argument(..., help="Workflow ID to check"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """Get status of a workflow."""
    
    try:
        with AgentsClient() as client:
            response = client.get_workflow_status(workflow_id)
            
            status = response.get("status", "unknown")
            print_info(f"Workflow {workflow_id} status: {status}")
            
            print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Failed to get workflow status: {str(e)}")
        raise typer.Exit(1)


@app.command()
def workflows(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of workflows to return"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """List workflows."""
    
    try:
        with AgentsClient() as client:
            response = client.list_workflows(limit, offset)
            
            if output_format == "table" or output_format is None:
                workflows_data = response.get("items", [])
                if workflows_data:
                    print_table(workflows_data, "Agent Workflows")
                else:
                    print_info("No workflows found")
            else:
                print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Failed to list workflows: {str(e)}")
        raise typer.Exit(1)


@app.command()
def clarify(
    request: str = typer.Argument(..., help="Analysis request to clarify"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="Additional context"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """Generate clarifying questions for an analysis request."""
    
    input_data = {
        "request": request
    }
    
    if context:
        input_data["context"] = context
    
    print_info(f"Generating clarifying questions for: '{request}'")
    
    try:
        with AgentsClient() as client:
            with show_progress("Generating questions...") as progress:
                task = progress.add_task("Processing...", total=None)
                response = client.start_workflow("clarifier", input_data)
                progress.remove_task(task)
            
            print_success("Clarifying questions generated")
            
            # Extract questions for better display
            if "output" in response and "questions" in response["output"]:
                questions = response["output"]["questions"]
                print_info(f"Generated {len(questions)} questions:")
                for i, question in enumerate(questions, 1):
                    print(f"{i}. {question}")
            
            if output_format:
                print("\nFull response:")
                print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Failed to generate clarifying questions: {str(e)}")
        raise typer.Exit(1)


@app.command()
def synthesize(
    requirements: str = typer.Argument(..., help="Requirements to synthesize"),
    current_state: Optional[str] = typer.Option(None, "--current", "-c", help="Current state description"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """Generate AS-IS to TO-BE documentation."""
    
    input_data = {
        "requirements": requirements
    }
    
    if current_state:
        input_data["current_state"] = current_state
    
    print_info(f"Synthesizing documentation for: '{requirements}'")
    
    try:
        with AgentsClient() as client:
            with show_progress("Synthesizing documentation...") as progress:
                task = progress.add_task("Processing...", total=None)
                response = client.start_workflow("synthesizer", input_data)
                progress.remove_task(task)
            
            print_success("Documentation synthesized")
            print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Failed to synthesize documentation: {str(e)}")
        raise typer.Exit(1)


@app.command()
def tasks(
    requirements: str = typer.Argument(..., help="Requirements to break down into tasks"),
    priority: Optional[str] = typer.Option("medium", "--priority", "-p", help="Task priority (low, medium, high)"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """Generate developer tasks from requirements."""
    
    input_data = {
        "requirements": requirements,
        "priority": priority
    }
    
    print_info(f"Generating tasks for: '{requirements}' (priority: {priority})")
    
    try:
        with AgentsClient() as client:
            with show_progress("Generating tasks...") as progress:
                task = progress.add_task("Processing...", total=None)
                response = client.start_workflow("taskmaster", input_data)
                progress.remove_task(task)
            
            print_success("Tasks generated")
            
            # Extract tasks for better display
            if "output" in response and "tasks" in response["output"]:
                tasks = response["output"]["tasks"]
                print_info(f"Generated {len(tasks)} tasks:")
                for i, task in enumerate(tasks, 1):
                    print(f"{i}. {task.get('title', 'Untitled')}")
                    if task.get('description'):
                        print(f"   {task['description']}")
            
            if output_format:
                print("\nFull response:")
                print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Failed to generate tasks: {str(e)}")
        raise typer.Exit(1)


@app.command()
def verify(
    output_to_verify: str = typer.Argument(..., help="Output to verify against knowledge base"),
    verification_type: Optional[str] = typer.Option("general", "--type", "-t", help="Verification type"),
    output_format: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (table, json, yaml)")
):
    """Verify output against knowledge base and constraints."""
    
    input_data = {
        "output": output_to_verify,
        "verification_type": verification_type
    }
    
    print_info(f"Verifying output (type: {verification_type})")
    
    try:
        with AgentsClient() as client:
            with show_progress("Verifying output...") as progress:
                task = progress.add_task("Processing...", total=None)
                response = client.start_workflow("verifier", input_data)
                progress.remove_task(task)
            
            # Show verification results
            if "output" in response:
                verification_result = response["output"]
                is_valid = verification_result.get("is_valid", False)
                
                if is_valid:
                    print_success("Output verification passed")
                else:
                    print_error("Output verification failed")
                
                if "issues" in verification_result:
                    issues = verification_result["issues"]
                    if issues:
                        print_info(f"Found {len(issues)} issues:")
                        for i, issue in enumerate(issues, 1):
                            print(f"{i}. {issue}")
            
            if output_format:
                print("\nFull response:")
                print(format_output(response, output_format))
            
    except Exception as e:
        print_error(f"Failed to verify output: {str(e)}")
        raise typer.Exit(1)


@app.command()
def health():
    """Check agents service health."""
    
    try:
        with AgentsClient() as client:
            response = client.health_check()
            
            status = response.get("status", "unknown")
            if status == "healthy":
                print_success(f"Agents service is {status}")
            else:
                print_error(f"Agents service is {status}")
                if "error" in response:
                    print_error(f"Error: {response['error']}")
            
            print(format_output(response))
            
    except Exception as e:
        print_error(f"Health check failed: {str(e)}")
        raise typer.Exit(1)

