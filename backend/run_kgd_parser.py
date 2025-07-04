#!/usr/bin/env python3
"""
KGD Tax Parser Launcher

This script launches the KGD parser from the project root directory.
It automatically changes to the parser directory and runs the quick start script.

Usage from project root:
    python run_kgd_parser.py
"""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Launch the KGD parser"""
    print("🚀 Launching KGD Tax Parser...")
    
    # Get the project root directory
    project_root = Path(__file__).parent
    parser_dir = project_root / "parser"
    
    # Check if parser directory exists
    if not parser_dir.exists():
        print("❌ Error: parser/ directory not found")
        sys.exit(1)
    
    # Check if quick_start.py exists
    quick_start_script = parser_dir / "quick_start.py"
    if not quick_start_script.exists():
        print("❌ Error: quick_start.py not found in parser/ directory")
        sys.exit(1)
    
    # Change to parser directory and run the script
    try:
        print(f"📁 Changing to directory: {parser_dir}")
        os.chdir(parser_dir)
        
        print("🎯 Running KGD parser quick start...")
        
        # Run the quick start script
        result = subprocess.run([sys.executable, "quick_start.py"])
        
        if result.returncode != 0:
            print("❌ KGD parser exited with error")
            sys.exit(result.returncode)
        else:
            print("✅ KGD parser completed successfully")
        
    except Exception as e:
        print(f"❌ Error running KGD parser: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 