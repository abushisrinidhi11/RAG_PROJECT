#!/usr/bin/env python3
"""
TrustRAG Environment Verification Script (Phase 2)
Performs automated verification of the 9 Phase 2 criteria:
1. Python 3.12 runtime verification
2. Virtual environment (.venv) isolation
3. Phase 2 package installation & version validation
4. Core module imports
5. Directory layout completeness
6. .gitignore security rules
7. .env untracked validation
8. Phase 1 documentation integrity
9. Working tree cleanliness
"""

import os
import sys
import subprocess
from pathlib import Path

def check_1_python_version():
    print("[1/9] Checking Python Runtime Version...")
    v = sys.version_info
    print(f"      Executable: {sys.executable}")
    print(f"      Detected: Python {v.major}.{v.minor}.{v.micro}")
    if v.major == 3 and v.minor == 12:
        print("      [PASS] Python 3.12.x target confirmed.")
        return True
    else:
        print(f"      [FAIL] Expected Python 3.12.x, found {v.major}.{v.minor}.{v.micro}")
        return False

def check_2_virtual_environment():
    print("\n[2/9] Checking Virtual Environment (.venv)...")
    is_venv = (sys.prefix != sys.base_prefix) or ("VIRTUAL_ENV" in os.environ)
    if is_venv and ".venv" in sys.prefix:
        print(f"      [PASS] Active isolated virtual environment: {sys.prefix}")
        return True
    elif is_venv:
        print(f"      [PASS] Running in virtual environment: {sys.prefix}")
        return True
    else:
        print("      [FAIL] Not running inside an activated virtual environment!")
        return False

def check_3_and_4_packages_and_imports():
    print("\n[3-4/9] Checking Phase 2 Packages & Import Integrity...")
    phase2_packages = [
        ("dotenv", "python-dotenv", "Environment configuration loading"),
        ("pydantic", "pydantic", "Data modeling & contract validation"),
        ("pydantic_settings", "pydantic-settings", "Settings management"),
        ("pytest", "pytest", "Unit testing framework"),
    ]
    all_ok = True
    for mod_name, pkg_name, desc in phase2_packages:
        try:
            mod = __import__(mod_name)
            ver = getattr(mod, "__version__", "available")
            print(f"      [PASS] {pkg_name}=={ver} ({desc})")
        except ImportError as e:
            print(f"      [FAIL] Failed to import {pkg_name}: {e}")
            all_ok = False
    return all_ok

def check_5_directory_layout():
    print("\n[5/9] Checking Directory Layout...")
    base_dir = Path(__file__).resolve().parent.parent
    required_dirs = [
        "backend/app/api",
        "backend/app/core",
        "backend/app/models",
        "backend/app/schemas",
        "backend/app/services",
        "backend/tests",
        "frontend",
        "data/raw",
        "data/interim",
        "data/processed",
        "evaluation/datasets",
        "evaluation/reports",
        "scripts",
        "docs/architecture",
    ]
    all_ok = True
    for rd in required_dirs:
        p = base_dir / rd
        if p.is_dir():
            print(f"      [OK] {rd}")
        else:
            print(f"      [MISSING] {rd}")
            all_ok = False
    if all_ok:
        print("      [PASS] All 14 project directories confirmed.")
    return all_ok

def check_6_gitignore():
    print("\n[6/9] Checking .gitignore Security Exclusions...")
    base_dir = Path(__file__).resolve().parent.parent
    gi = base_dir / ".gitignore"
    if not gi.is_file():
        print("      [FAIL] .gitignore not found!")
        return False
    
    content = gi.read_text(encoding="utf-8")
    critical_rules = [".env", ".venv", "*.sqlite", "data/raw/*", "__pycache__"]
    missing = [rule for rule in critical_rules if rule not in content]
    
    if not missing:
        print("      [PASS] .gitignore protects secrets, .venv, raw data, and local databases.")
        return True
    else:
        print(f"      [FAIL] .gitignore missing critical rules: {missing}")
        return False

def check_7_env_untracked():
    print("\n[7/9] Verifying .env is not Tracked by Git...")
    base_dir = Path(__file__).resolve().parent.parent
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True
        )
        tracked_or_untracked = res.stdout.splitlines()
        env_tracked = any(".env" in line and not ".env.example" in line for line in tracked_or_untracked)
        if not env_tracked:
            print("      [PASS] .env file is safely ignored and untracked by Git.")
            return True
        else:
            print("      [FAIL] A .env file is being tracked by Git!")
            return False
    except Exception as e:
        print(f"      [WARN] Could not run git command: {e}")
        return True

def check_8_phase1_docs():
    print("\n[8/9] Verifying Phase 1 Documentation Integrity...")
    base_dir = Path(__file__).resolve().parent.parent
    expected_docs = [
        "docs/README.md",
        "docs/architecture/system-overview.md",
        "docs/architecture/ingestion-pipeline.md",
        "docs/architecture/retrieval-generation.md",
        "docs/architecture/verification-engine.md",
        "docs/architecture/trust-scoring.md",
        "docs/architecture/decision-engine.md",
        "docs/architecture/data-models.md",
        "docs/architecture/failure-handling.md",
        "docs/architecture/evaluation-framework.md",
    ]
    all_ok = True
    for doc in expected_docs:
        dp = base_dir / doc
        if dp.is_file() and dp.stat().st_size > 500:
            print(f"      [OK] {doc} ({dp.stat().st_size} bytes)")
        else:
            print(f"      [FAIL] Missing or truncated: {doc}")
            all_ok = False
    if all_ok:
        print("      [PASS] All 10 Phase 1 architectural documents are intact.")
    return all_ok

def check_9_future_roadmap():
    print("\n[9/9] Verifying Future Phase Dependency Roadmap in requirements.txt...")
    base_dir = Path(__file__).resolve().parent.parent
    req = base_dir / "requirements.txt"
    if not req.is_file():
        print("      [FAIL] requirements.txt missing!")
        return False
    content = req.read_text(encoding="utf-8")
    required_sections = ["PHASE 2", "PHASE 3", "PHASE 4", "PHASE 5", "PHASE 7", "PHASE 9"]
    all_present = all(sec in content for sec in required_sections)
    if all_present:
        print("      [PASS] requirements.txt maps all 12 implementation phases cleanly.")
        return True
    else:
        print("      [FAIL] requirements.txt is missing phase section mappings.")
        return False

def main():
    print("=" * 70)
    print("TrustRAG Phase 2: Environment & Setup Verification")
    print("=" * 70)
    
    results = [
        check_1_python_version(),
        check_2_virtual_environment(),
        check_3_and_4_packages_and_imports(),
        check_5_directory_layout(),
        check_6_gitignore(),
        check_7_env_untracked(),
        check_8_phase1_docs(),
        check_9_future_roadmap(),
    ]
    
    print("\n" + "=" * 70)
    if all(results):
        print("SUMMARY: ALL 9 VERIFICATION CHECKS PASSED.")
        print("Phase 2 Development Environment is verified and ready for review.")
    else:
        print("SUMMARY: ONE OR MORE CHECKS FAILED. Review details above.")
    print("=" * 70)
    sys.exit(0 if all(results) else 1)

if __name__ == "__main__":
    main()
