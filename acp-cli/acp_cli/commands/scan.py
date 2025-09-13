"""Security scanning commands for ACP CLI."""

import os
import json
import subprocess
import typer
from pathlib import Path
from typing import Optional, List, Dict, Any

from ..utils import print_success, print_error, print_info, print_warning

app = typer.Typer(help="Security scanning for ACP services")


@app.command()
def dependencies(
    service: Optional[str] = typer.Option(
        None, "--service", "-s", help="Scan specific service (ingest, agents, cli)"
    ),
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix vulnerabilities automatically"),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, sarif)"
    ),
    severity: str = typer.Option(
        "medium", "--severity", help="Minimum severity level (low, medium, high, critical)"
    ),
):
    """Scan dependencies for known vulnerabilities."""

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
        scan_results = {}

        for svc in services_to_scan:
            print_info(f"Scanning dependencies for {svc} service...")

            if svc == "ingest":
                scan_dir = project_root / "acp-ingest"
            elif svc == "agents":
                scan_dir = project_root / "acp-agents"
            elif svc == "cli":
                scan_dir = project_root / "acp-cli"

            if not scan_dir.exists():
                print_warning(f"Service directory not found: {scan_dir}")
                continue

            requirements_file = scan_dir / "requirements.txt"
            if not requirements_file.exists():
                print_warning(f"Requirements file not found: {requirements_file}")
                continue

            # Run pip-audit
            print_info("Running pip-audit...")
            cmd = ["pip-audit", "-r", "requirements.txt"]

            if output_format == "json":
                cmd.extend(["--format", "json"])
            elif output_format == "sarif":
                cmd.extend(["--format", "sarif"])

            if fix:
                cmd.append("--fix")

            # Add severity filter
            severity_levels = {
                "low": ["low", "medium", "high", "critical"],
                "medium": ["medium", "high", "critical"],
                "high": ["high", "critical"],
                "critical": ["critical"],
            }

            result = subprocess.run(cmd, cwd=scan_dir, capture_output=True, text=True)

            scan_results[svc] = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            if result.returncode != 0:
                if output_format == "json":
                    try:
                        vulnerabilities = json.loads(result.stdout)
                        # Filter by severity
                        filtered_vulns = []
                        for vuln in vulnerabilities:
                            if vuln.get("severity", "").lower() in severity_levels.get(
                                severity, []
                            ):
                                filtered_vulns.append(vuln)

                        if filtered_vulns:
                            print_error(f"Found {len(filtered_vulns)} vulnerabilities in {svc}")
                            print(json.dumps(filtered_vulns, indent=2))
                            overall_success = False
                        else:
                            print_success(f"No {severity}+ severity vulnerabilities found in {svc}")
                    except json.JSONDecodeError:
                        print_error(f"Failed to parse pip-audit output for {svc}")
                        print(result.stdout)
                        overall_success = False
                else:
                    print_error(f"Vulnerabilities found in {svc}:")
                    print(result.stdout)
                    overall_success = False
            else:
                print_success(f"No vulnerabilities found in {svc}")

        # Run npm audit for any Node.js dependencies
        package_json = project_root / "package.json"
        if package_json.exists():
            print_info("Running npm audit...")

            npm_cmd = ["npm", "audit"]
            if output_format == "json":
                npm_cmd.append("--json")

            if fix:
                npm_cmd.append("--fix")

            result = subprocess.run(npm_cmd, cwd=project_root, capture_output=True, text=True)

            if result.returncode != 0:
                print_error("npm audit found vulnerabilities:")
                print(result.stdout)
                overall_success = False
            else:
                print_success("npm audit passed")

        if overall_success:
            print_success("All dependency scans passed! ✅")
        else:
            print_error("Some dependency scans found vulnerabilities ❌")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to scan dependencies: {e}")
        raise typer.Exit(1)


@app.command()
def code(
    service: Optional[str] = typer.Option(
        None, "--service", "-s", help="Scan specific service (ingest, agents, cli)"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, sarif)"
    ),
    confidence: str = typer.Option(
        "medium", "--confidence", help="Minimum confidence level (low, medium, high)"
    ),
):
    """Scan code for security vulnerabilities using Bandit."""

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
            print_info(f"Scanning code for {svc} service...")

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
            cmd = ["bandit", "-r", ".", "--confidence", confidence, "--severity", "medium"]

            if output_format == "json":
                cmd.extend(["-f", "json"])
            elif output_format == "sarif":
                cmd.extend(["-f", "sarif"])

            # Exclude test files and migrations
            cmd.extend(["--exclude", "tests,migrations,venv,.venv"])

            result = subprocess.run(cmd, cwd=scan_dir, capture_output=True, text=True)

            if result.returncode != 0:
                if output_format == "json":
                    try:
                        scan_data = json.loads(result.stdout)
                        issues = scan_data.get("results", [])
                        if issues:
                            print_error(f"Found {len(issues)} security issues in {svc}")
                            print(json.dumps(issues, indent=2))
                            overall_success = False
                        else:
                            print_success(f"No security issues found in {svc}")
                    except json.JSONDecodeError:
                        print_error(f"Failed to parse bandit output for {svc}")
                        print(result.stdout)
                        overall_success = False
                else:
                    print_error(f"Security issues found in {svc}:")
                    print(result.stdout)
                    overall_success = False
            else:
                print_success(f"No security issues found in {svc}")

        if overall_success:
            print_success("All code scans passed! ✅")
        else:
            print_error("Some code scans found security issues ❌")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to scan code: {e}")
        raise typer.Exit(1)


@app.command()
def secrets(
    path: Optional[str] = typer.Option(".", "--path", "-p", help="Path to scan for secrets"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", help="Patterns to exclude"),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
):
    """Scan for exposed secrets and credentials."""

    try:
        scan_path = Path(path)

        if not scan_path.exists():
            print_error(f"Path does not exist: {scan_path}")
            raise typer.Exit(1)

        print_info(f"Scanning for secrets in {scan_path}...")

        # Check if truffleHog is available
        result = subprocess.run(["trufflehog", "--version"], capture_output=True)
        if result.returncode != 0:
            print_warning("truffleHog not found, using basic pattern matching")
            _basic_secret_scan(scan_path, exclude or [])
        else:
            _trufflehog_scan(scan_path, exclude or [], output_format)

    except Exception as e:
        print_error(f"Failed to scan for secrets: {e}")
        raise typer.Exit(1)


def _basic_secret_scan(scan_path: Path, exclude_patterns: List[str]):
    """Basic secret scanning using pattern matching."""

    # Common secret patterns
    secret_patterns = [
        (r'password\s*=\s*["\'][^"\']+["\']', "Password"),
        (r'api[_-]?key\s*=\s*["\'][^"\']+["\']', "API Key"),
        (r'secret[_-]?key\s*=\s*["\'][^"\']+["\']', "Secret Key"),
        (r'access[_-]?token\s*=\s*["\'][^"\']+["\']', "Access Token"),
        (r'private[_-]?key\s*=\s*["\'][^"\']+["\']', "Private Key"),
        (r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----", "Private Key"),
        (r"sk-[a-zA-Z0-9]{48}", "OpenAI API Key"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
        (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    ]

    import re

    findings = []

    for file_path in scan_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in [
            ".py",
            ".js",
            ".ts",
            ".json",
            ".yaml",
            ".yml",
            ".env",
        ]:
            # Skip excluded patterns
            skip = False
            for pattern in exclude_patterns:
                if pattern in str(file_path):
                    skip = True
                    break

            if skip:
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                    for pattern, secret_type in secret_patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for match in matches:
                            line_num = content[: match.start()].count("\n") + 1
                            findings.append(
                                {
                                    "file": str(file_path),
                                    "line": line_num,
                                    "type": secret_type,
                                    "match": (
                                        match.group()[:50] + "..."
                                        if len(match.group()) > 50
                                        else match.group()
                                    ),
                                }
                            )
            except Exception:
                continue

    if findings:
        print_error(f"Found {len(findings)} potential secrets:")
        for finding in findings:
            print_warning(
                f"  {finding['file']}:{finding['line']} - {finding['type']}: {finding['match']}"
            )
        raise typer.Exit(1)
    else:
        print_success("No secrets found")


def _trufflehog_scan(scan_path: Path, exclude_patterns: List[str], output_format: str):
    """Advanced secret scanning using truffleHog."""

    cmd = ["trufflehog", "filesystem", str(scan_path)]

    if output_format == "json":
        cmd.append("--json")

    # Add exclude patterns
    for pattern in exclude_patterns:
        cmd.extend(["--exclude", pattern])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        if output_format == "json":
            try:
                findings = [json.loads(line) for line in result.stdout.strip().split("\n") if line]
                if findings:
                    print_error(f"Found {len(findings)} secrets:")
                    print(json.dumps(findings, indent=2))
                    raise typer.Exit(1)
                else:
                    print_success("No secrets found")
            except json.JSONDecodeError:
                print_error("Failed to parse truffleHog output")
                print(result.stdout)
                raise typer.Exit(1)
        else:
            if result.stdout.strip():
                print_error("Secrets found:")
                print(result.stdout)
                raise typer.Exit(1)
            else:
                print_success("No secrets found")
    else:
        print_success("No secrets found")


@app.command()
def containers(
    image: Optional[str] = typer.Option(
        None, "--image", "-i", help="Scan specific container image"
    ),
    severity: str = typer.Option(
        "medium", "--severity", help="Minimum severity level (low, medium, high, critical)"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
):
    """Scan container images for vulnerabilities using Trivy."""

    try:
        # Check if Trivy is available
        result = subprocess.run(["trivy", "--version"], capture_output=True)
        if result.returncode != 0:
            print_error("Trivy not found. Please install Trivy for container scanning.")
            raise typer.Exit(1)

        if image:
            images_to_scan = [image]
        else:
            # Get images from docker-compose
            print_info("Getting images from docker-compose...")
            result = subprocess.run(
                ["docker-compose", "config", "--images"],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )

            if result.returncode == 0:
                images_to_scan = [
                    img.strip() for img in result.stdout.strip().split("\n") if img.strip()
                ]
            else:
                print_error("Failed to get images from docker-compose")
                raise typer.Exit(1)

        overall_success = True

        for img in images_to_scan:
            print_info(f"Scanning container image: {img}")

            cmd = ["trivy", "image", "--severity", severity.upper()]

            if output_format == "json":
                cmd.extend(["--format", "json"])

            cmd.append(img)

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print_error(f"Vulnerabilities found in {img}:")
                print(result.stdout)
                overall_success = False
            else:
                if output_format == "json":
                    try:
                        scan_data = json.loads(result.stdout)
                        vulnerabilities = []
                        for target in scan_data.get("Results", []):
                            vulnerabilities.extend(target.get("Vulnerabilities", []))

                        if vulnerabilities:
                            print_error(f"Found {len(vulnerabilities)} vulnerabilities in {img}")
                            print(json.dumps(vulnerabilities, indent=2))
                            overall_success = False
                        else:
                            print_success(f"No vulnerabilities found in {img}")
                    except json.JSONDecodeError:
                        print_success(f"No vulnerabilities found in {img}")
                else:
                    print_success(f"No vulnerabilities found in {img}")

        if overall_success:
            print_success("All container scans passed! ✅")
        else:
            print_error("Some container scans found vulnerabilities ❌")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to scan containers: {e}")
        raise typer.Exit(1)


@app.command()
def all(
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json)"
    ),
    severity: str = typer.Option("medium", "--severity", help="Minimum severity level"),
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix issues automatically"),
):
    """Run all security scans."""

    try:
        print_info("Running comprehensive security scan...")

        scan_results = {"dependencies": True, "code": True, "secrets": True, "containers": True}

        # Run dependency scan
        try:
            print_info("\n=== Dependency Scan ===")
            result = subprocess.run(
                ["acp", "scan", "dependencies", "--format", output_format, "--severity", severity]
                + (["--fix"] if fix else [])
            )
            scan_results["dependencies"] = result.returncode == 0
        except Exception as e:
            print_error(f"Dependency scan failed: {e}")
            scan_results["dependencies"] = False

        # Run code scan
        try:
            print_info("\n=== Code Security Scan ===")
            result = subprocess.run(
                ["acp", "scan", "code", "--format", output_format, "--confidence", severity]
            )
            scan_results["code"] = result.returncode == 0
        except Exception as e:
            print_error(f"Code scan failed: {e}")
            scan_results["code"] = False

        # Run secrets scan
        try:
            print_info("\n=== Secrets Scan ===")
            result = subprocess.run(["acp", "scan", "secrets", "--format", output_format])
            scan_results["secrets"] = result.returncode == 0
        except Exception as e:
            print_error(f"Secrets scan failed: {e}")
            scan_results["secrets"] = False

        # Run container scan
        try:
            print_info("\n=== Container Scan ===")
            result = subprocess.run(
                ["acp", "scan", "containers", "--format", output_format, "--severity", severity]
            )
            scan_results["containers"] = result.returncode == 0
        except Exception as e:
            print_error(f"Container scan failed: {e}")
            scan_results["containers"] = False

        # Summary
        print_info("\n=== Security Scan Summary ===")
        all_passed = True
        for scan_type, passed in scan_results.items():
            if passed:
                print_success(f"{scan_type.title()}: PASS")
            else:
                print_error(f"{scan_type.title()}: FAIL")
                all_passed = False

        if all_passed:
            print_success("\nAll security scans passed! ✅")
        else:
            print_error("\nSome security scans failed ❌")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to run security scans: {e}")
        raise typer.Exit(1)
