#!/usr/bin/env python3
"""
ADR numbering enforcement check.
Validates that ADR files follow the numbering convention (0001-XXXX.md).
"""
import os
import re
import sys
from pathlib import Path

ADR_DIR = Path(__file__).parent.parent.parent / "docs" / "adrs"

# Expected pattern: 0001-title.md, 0002-title.md, etc.
ADR_PATTERN = re.compile(r'^(\d{4})-(.+)\.md$')

def check_adr_numbering():
    """Check that ADR files follow sequential numbering."""
    if not ADR_DIR.exists():
        print(f"ADR directory not found: {ADR_DIR}")
        return 1
    
    adr_files = sorted(ADR_DIR.glob("*.md"))
    
    if not adr_files:
        print("No ADR files found")
        return 1
    
    errors = []
    expected_num = 1
    
    for adr_file in adr_files:
        # Allow index.md as a special case
        if adr_file.name == "index.md":
            continue
            
        match = ADR_PATTERN.match(adr_file.name)
        if not match:
            errors.append(f"{adr_file.name}: Invalid filename format (expected NNNN-title.md)")
            continue
        
        num = int(match.group(1))
        if num != expected_num:
            errors.append(f"{adr_file.name}: Expected {expected_num:04d}, got {num:04d}")
        expected_num += 1
    
    # Check for duplicates
    nums = []
    for f in adr_files:
        match = ADR_PATTERN.match(f.name)
        if match:
            nums.append(int(match.group(1)))
    duplicates = [n for n in set(nums) if nums.count(n) > 1]
    if duplicates:
        for d in duplicates:
            errors.append(f"Duplicate ADR number: {d:04d}")
    
    if errors:
        print("ADR numbering errors:")
        for error in errors:
            print(f"  ERROR: {error}")
        return 1
    
    print(f"ADR numbering check passed: {len(adr_files)} ADRs validated")
    return 0

def main():
    return check_adr_numbering()

if __name__ == "__main__":
    sys.exit(main())