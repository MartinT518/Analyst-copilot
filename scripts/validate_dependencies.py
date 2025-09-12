#!/usr/bin/env python3
"""
Dependency Validation Script for Analyst Copilot

This script validates that all dependencies in requirements.in and requirements-dev.in
exist on PyPI and are compatible with Python 3.10, 3.11, and 3.12.

Usage:
    python scripts/validate_dependencies.py
    python scripts/validate_dependencies.py --individual-check
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class DependencyValidator:
    """Validates dependencies against PyPI and Python version compatibility."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.requirements_files = [
            self.project_root / "requirements.in",
            self.project_root / "requirements-dev.in",
        ]
        self.python_versions = ["3.10", "3.11", "3.12"]
        self.invalid_packages: List[str] = []
        self.warnings: List[str] = []

    def extract_package_names(self, file_path: Path) -> Set[str]:
        """Extract package names from a requirements file."""
        packages = set()

        if not file_path.exists():
            print(f"Warning: {file_path} does not exist")
            return packages

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Skip -r includes (we'll handle those separately)
                if line.startswith("-r "):
                    continue

                # Extract package name (before any version specifiers)
                package_name = re.split(r"[>=<!=]", line)[0].strip()

                # Remove extras (e.g., package[extra] -> package)
                if "[" in package_name:
                    package_name = package_name.split("[")[0]

                if package_name:
                    packages.add(package_name)

        return packages

    def check_package_exists(self, package_name: str) -> Tuple[bool, str]:
        """Check if a package exists on PyPI."""
        try:
            result = subprocess.run(
                ["pip", "index", "versions", package_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()

        except subprocess.TimeoutExpired:
            return False, "Timeout while checking package"
        except Exception as e:
            return False, f"Error checking package: {str(e)}"

    def check_python_compatibility(self, package_name: str) -> Dict[str, bool]:
        """Check Python version compatibility for a package."""
        compatibility = {}

        for python_version in self.python_versions:
            try:
                # Use pip to check if package can be installed for specific Python version
                result = subprocess.run(
                    [
                        "pip",
                        "install",
                        "--dry-run",
                        "--python-version",
                        python_version,
                        "--only-binary=:all:",
                        package_name,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                compatibility[python_version] = result.returncode == 0

            except subprocess.TimeoutExpired:
                compatibility[python_version] = False
            except Exception:
                compatibility[python_version] = False

        return compatibility

    def validate_all_packages(self) -> bool:
        """Validate all packages in requirements files."""
        all_packages = set()

        # Collect all package names
        for req_file in self.requirements_files:
            packages = self.extract_package_names(req_file)
            all_packages.update(packages)
            print(f"Found {len(packages)} packages in {req_file.name}")

        print(f"\nTotal unique packages to validate: {len(all_packages)}")
        print("=" * 60)

        all_valid = True

        for i, package_name in enumerate(sorted(all_packages), 1):
            print(f"[{i}/{len(all_packages)}] Checking {package_name}...")

            # Check if package exists on PyPI
            exists, message = self.check_package_exists(package_name)

            if not exists:
                print(f"  FAIL: {package_name} - {message}")
                self.invalid_packages.append(package_name)
                all_valid = False
                continue

            # Check Python compatibility
            compatibility = self.check_python_compatibility(package_name)
            incompatible_versions = [v for v, compatible in compatibility.items() if not compatible]

            if incompatible_versions:
                print(
                    f"  WARNING: {package_name} - Incompatible with Python {', '.join(incompatible_versions)}"
                )
                self.warnings.append(
                    f"{package_name}: Incompatible with Python {', '.join(incompatible_versions)}"
                )
            else:
                print(f"  OK: {package_name}")

        return all_valid

    def generate_report(self) -> None:
        """Generate a validation report."""
        print("\n" + "=" * 60)
        print("DEPENDENCY VALIDATION REPORT")
        print("=" * 60)

        if self.invalid_packages:
            print(f"\nINVALID PACKAGES ({len(self.invalid_packages)}):")
            for package in self.invalid_packages:
                print(f"  - {package}")

        if self.warnings:
            print(f"\nWARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if not self.invalid_packages and not self.warnings:
            print("\nALL PACKAGES VALID!")
            print("All dependencies exist on PyPI and are compatible with Python 3.10-3.12")

        print(
            f"\nTotal packages checked: {len(self.invalid_packages) + len(self.warnings) + len([p for p in self.extract_package_names(self.requirements_files[0]) if p not in self.invalid_packages and p not in [w.split(':')[0] for w in self.warnings]])}"
        )

    def run_validation(self) -> int:
        """Run the complete validation process."""
        print("Starting dependency validation...")
        print(f"Python versions to check: {', '.join(self.python_versions)}")
        print(f"Requirements files: {[f.name for f in self.requirements_files]}")

        try:
            all_valid = self.validate_all_packages()
            self.generate_report()

            if all_valid:
                print("\nValidation completed successfully!")
                return 0
            else:
                print(f"\nValidation failed! Found {len(self.invalid_packages)} invalid packages.")
                return 1

        except KeyboardInterrupt:
            print("\n\nValidation interrupted by user")
            return 1
        except Exception as e:
            print(f"\nValidation failed with error: {str(e)}")
            return 1


def individual_check():
    """Run individual package validation using pip index versions."""
    validator = DependencyValidator()
    packages = set()
    for file_path in validator.requirements_files:
        packages.update(validator.extract_package_names(file_path))

    print("Starting individual package validation...")
    print(f"Found {len(packages)} packages to validate")

    failed_packages = []

    for i, package in enumerate(packages, 1):
        print(f"[{i}/{len(packages)}] Checking package: {package}")
        try:
            result = subprocess.run(
                ["pip", "index", "versions", package], capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                print(f"  FAIL: {package} - {result.stderr.strip()}")
                failed_packages.append(package)
            else:
                print(f"  OK: {package}")
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT: {package} - Request timed out")
            failed_packages.append(package)
        except Exception as e:
            print(f"  ERROR: {package} - {str(e)}")
            failed_packages.append(package)

    if failed_packages:
        print(f"\nFAILED PACKAGES: {len(failed_packages)}")
        for pkg in failed_packages:
            print(f"  - {pkg}")
        return 1
    else:
        print(f"\nALL PACKAGES VALID!")
        return 0


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--individual-check":
        exit_code = individual_check()
    else:
        validator = DependencyValidator()
        exit_code = validator.run_validation()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
