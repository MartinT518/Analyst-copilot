"""Test commands for ACP CLI."""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer

from ..utils import print_error, print_info, print_success, print_warning

app = typer.Typer(help="Run tests for ACP services")


@app.command()
def run(
    service: Optional[str] = typer.Option(
        None, "--service", "-s", help="Run tests for specific service (ingest, agents, cli)"
    ),
    with_coverage: bool = typer.Option(
        False, "--coverage", "-c", help="Run tests with coverage reporting"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    fail_fast: bool = typer.Option(False, "--fail-fast", "-x", help="Stop on first failure"),
    pattern: Optional[str] = typer.Option(
        None, "--pattern", "-k", help="Run tests matching pattern"
    ),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Run tests in parallel"),
    html_report: bool = typer.Option(False, "--html", help="Generate HTML coverage report"),
):
    """Run tests for ACP services."""

    try:
        project_root = Path.cwd()

        # Determine which services to test
        services_to_test = []
        if service:
            if service in ["ingest", "agents", "cli"]:
                services_to_test = [service]
            else:
                print_error(f"Unknown service: {service}")
                raise typer.Exit(1)
        else:
            # Test all services
            services_to_test = ["ingest", "agents", "cli"]

        overall_success = True
        test_results = {}

        for svc in services_to_test:
            print_info(f"Running tests for {svc} service...")

            if svc == "ingest":
                test_dir = project_root / "acp-ingest"
            elif svc == "agents":
                test_dir = project_root / "acp-agents"
            elif svc == "cli":
                test_dir = project_root / "acp-cli"

            if not test_dir.exists():
                print_warning(f"Service directory not found: {test_dir}")
                continue

            # Check if tests directory exists
            tests_dir = test_dir / "tests"
            if not tests_dir.exists():
                print_warning(f"Tests directory not found: {tests_dir}")
                continue

            # Build test command
            cmd = ["python", "-m", "pytest"]

            if verbose:
                cmd.append("-v")

            if fail_fast:
                cmd.append("-x")

            if pattern:
                cmd.extend(["-k", pattern])

            if parallel:
                cmd.extend(["-n", "auto"])

            if with_coverage:
                cmd.extend(
                    [
                        "--cov=.",
                        "--cov-report=term-missing",
                        "--cov-report=xml",
                        "--cov-fail-under=80",
                    ]
                )

                if html_report:
                    cmd.append("--cov-report=html")

            # Add test directory
            cmd.append("tests/")

            print_info(f"Running: {' '.join(cmd)}")

            # Run tests
            result = subprocess.run(cmd, cwd=test_dir, capture_output=False, text=True)

            test_results[svc] = result.returncode == 0

            if result.returncode != 0:
                print_error(f"Tests failed for {svc} service")
                overall_success = False
            else:
                print_success(f"Tests passed for {svc} service")

        # Print summary
        print_info("\n" + "=" * 50)
        print_info("TEST SUMMARY")
        print_info("=" * 50)

        for svc, success in test_results.items():
            status = "PASS" if success else "FAIL"
            color_func = print_success if success else print_error
            color_func(f"{svc.upper()}: {status}")

        if overall_success:
            print_success("\nAll tests passed! ✅")
        else:
            print_error("\nSome tests failed ❌")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to run tests: {e}")
        raise typer.Exit(1)


@app.command()
def lint(
    service: Optional[str] = typer.Option(
        None, "--service", "-s", help="Lint specific service (ingest, agents, cli)"
    ),
    fix: bool = typer.Option(False, "--fix", help="Automatically fix issues where possible"),
):
    """Run linting checks for ACP services."""

    try:
        project_root = Path.cwd()

        # Determine which services to lint
        services_to_lint = []
        if service:
            if service in ["ingest", "agents", "cli"]:
                services_to_lint = [service]
            else:
                print_error(f"Unknown service: {service}")
                raise typer.Exit(1)
        else:
            # Lint all services
            services_to_lint = ["ingest", "agents", "cli"]

        overall_success = True

        for svc in services_to_lint:
            print_info(f"Linting {svc} service...")

            if svc == "ingest":
                lint_dir = project_root / "acp-ingest"
            elif svc == "agents":
                lint_dir = project_root / "acp-agents"
            elif svc == "cli":
                lint_dir = project_root / "acp-cli"

            if not lint_dir.exists():
                print_warning(f"Service directory not found: {lint_dir}")
                continue

            # Run black
            print_info("Running black...")
            black_cmd = ["black"]
            if not fix:
                black_cmd.append("--check")
            black_cmd.append(".")

            result = subprocess.run(black_cmd, cwd=lint_dir)
            if result.returncode != 0:
                overall_success = False

            # Run isort
            print_info("Running isort...")
            isort_cmd = ["isort"]
            if not fix:
                isort_cmd.append("--check-only")
            isort_cmd.append(".")

            result = subprocess.run(isort_cmd, cwd=lint_dir)
            if result.returncode != 0:
                overall_success = False

            # Run flake8
            print_info("Running flake8...")
            flake8_cmd = ["flake8", "."]

            result = subprocess.run(flake8_cmd, cwd=lint_dir)
            if result.returncode != 0:
                overall_success = False

        if overall_success:
            print_success("All linting checks passed! ✅")
        else:
            print_error("Some linting checks failed ❌")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to run linting: {e}")
        raise typer.Exit(1)


@app.command()
def security(
    service: Optional[str] = typer.Option(
        None, "--service", "-s", help="Scan specific service (ingest, agents, cli)"
    )
):
    """Run security scans for ACP services."""

    try:
        project_root = Path.cwd()

        # Determine which services to scan
        services_to_scan = []
        if service:
            if service in ["ingest", "agents", "cli"]:
                services_to_scan = [service]
            else:
                print_error(f"Unknown service: {service}")
                raise typer.Exit(1)
        else:
            # Scan all services
            services_to_scan = ["ingest", "agents", "cli"]

        overall_success = True

        for svc in services_to_scan:
            print_info(f"Security scanning {svc} service...")

            if svc == "ingest":
                scan_dir = project_root / "acp-ingest"
            elif svc == "agents":
                scan_dir = project_root / "acp-agents"
            elif svc == "cli":
                scan_dir = project_root / "acp-cli"

            if not scan_dir.exists():
                print_warning(f"Service directory not found: {scan_dir}")
                continue

            # Run bandit
            print_info("Running bandit security scan...")
            bandit_cmd = [
                "bandit",
                "-r",
                ".",
                "-f",
                "json",
                "-o",
                "bandit-report.json",
                "--severity-level",
                "medium",
            ]

            result = subprocess.run(bandit_cmd, cwd=scan_dir, capture_output=True)
            if result.returncode != 0:
                print_error("Bandit found security issues")
                overall_success = False
            else:
                print_success("Bandit scan passed")

            # Run pip-audit if requirements.txt exists
            requirements_file = scan_dir / "requirements.txt"
            if requirements_file.exists():
                print_info("Running pip-audit for dependency vulnerabilities...")
                pip_audit_cmd = ["pip-audit", "-r", "requirements.txt"]

                result = subprocess.run(pip_audit_cmd, cwd=scan_dir)
                if result.returncode != 0:
                    print_error("pip-audit found vulnerabilities")
                    overall_success = False
                else:
                    print_success("pip-audit scan passed")

        if overall_success:
            print_success("All security scans passed! ✅")
        else:
            print_error("Some security scans failed ❌")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to run security scans: {e}")
        raise typer.Exit(1)


@app.command()
def integration():
    """Run integration tests for the entire ACP stack."""

    try:
        project_root = Path.cwd()

        print_info("Running integration tests...")

        # Check if docker-compose is available
        result = subprocess.run(["docker-compose", "--version"], capture_output=True)
        if result.returncode != 0:
            print_error("docker-compose not found. Integration tests require Docker.")
            raise typer.Exit(1)

        # Start test stack
        print_info("Starting test stack...")
        start_cmd = ["docker-compose", "-f", "docker-compose.test.yml", "up", "-d"]
        result = subprocess.run(start_cmd, cwd=project_root)

        if result.returncode != 0:
            print_error("Failed to start test stack")
            raise typer.Exit(1)

        try:
            # Wait for services to be ready
            import time

            print_info("Waiting for services to start...")
            time.sleep(30)

            # Run integration tests
            test_cmd = ["python", "-m", "pytest", "tests/integration/", "-v"]
            result = subprocess.run(test_cmd, cwd=project_root)

            if result.returncode == 0:
                print_success("Integration tests passed! ✅")
            else:
                print_error("Integration tests failed ❌")
                raise typer.Exit(1)

        finally:
            # Clean up test stack
            print_info("Cleaning up test stack...")
            cleanup_cmd = ["docker-compose", "-f", "docker-compose.test.yml", "down", "-v"]
            subprocess.run(cleanup_cmd, cwd=project_root)

    except Exception as e:
        print_error(f"Failed to run integration tests: {e}")
        raise typer.Exit(1)


@app.command()
def performance(
    duration: int = typer.Option(60, "--duration", "-d", help="Test duration in seconds"),
    users: int = typer.Option(10, "--users", "-u", help="Number of concurrent users"),
    target_url: Optional[str] = typer.Option(
        None, "--url", help="Target URL for performance testing"
    ),
):
    """Run performance tests against ACP services."""

    try:
        if not target_url:
            target_url = "http://localhost:8000"

        print_info(f"Running performance tests against {target_url}")
        print_info(f"Duration: {duration}s, Users: {users}")

        # Check if k6 is available
        result = subprocess.run(["k6", "version"], capture_output=True)
        if result.returncode != 0:
            print_error("k6 not found. Please install k6 for performance testing.")
            raise typer.Exit(1)

        # Create k6 test script
        k6_script = f"""
import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export let options = {{
  vus: {users},
  duration: '{duration}s',
}};

export default function () {{
  let response = http.get('{target_url}/health');
  check(response, {{ 'status was 200': (r) => r.status == 200 }});
  sleep(1);
}}
"""

        # Write script to temporary file
        script_path = Path.cwd() / "k6-test.js"
        with open(script_path, "w") as f:
            f.write(k6_script)

        try:
            # Run k6 test
            k6_cmd = ["k6", "run", str(script_path)]
            result = subprocess.run(k6_cmd)

            if result.returncode == 0:
                print_success("Performance tests completed! ✅")
            else:
                print_error("Performance tests failed ❌")
                raise typer.Exit(1)

        finally:
            # Clean up script file
            if script_path.exists():
                script_path.unlink()

    except Exception as e:
        print_error(f"Failed to run performance tests: {e}")
        raise typer.Exit(1)
