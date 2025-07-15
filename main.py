#!/usr/bin/env python3
"""
Entry point for the transparent proxy tunnel application.
This file maintains backward compatibility while using the new structure.
"""

import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.main import main

if __name__ == "__main__":
    main()