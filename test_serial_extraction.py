#!/usr/bin/env python3
"""
Test script for serial number extraction from show version output.
This helps validate the regex patterns without needing a live device.
"""

import re
from typing import Optional


def parse_show_version(output: str) -> Optional[str]:
    """
    Parse 'show version' output to extract serial number.

    Args:
        output: Output from 'show version' command

    Returns:
        Serial number if found, None otherwise
    """
    # Clean up pagination artifacts
    cleaned_output = output.replace('--More--', '').replace('-- More --', '')
    # Remove backspace characters and ANSI escape codes
    cleaned_output = re.sub(r'\x08+', '', cleaned_output)
    cleaned_output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', cleaned_output)

    # Common patterns for serial number in show version output
    patterns = [
        # Cisco IOS XE / Catalyst switches
        r'Model [Nn]umber\s*:?\s*\S+\s+[Ss]ystem [Ss]erial [Nn]umber\s*:?\s*(\S+)',
        r'[Ss]ystem [Ss]erial [Nn]umber\s*:?\s*(\S+)',
        # Standard patterns
        r'[Ss]erial\s+[Nn]umber\s*:?\s+(\S+)',
        r'[Pp]rocessor [Bb]oard ID\s+(\S+)',
        r'Chassis Serial Number\s*:?\s+(\S+)',
        # Alternative patterns
        r'Serial [Nn]um\s*:?\s*(\S+)',
        r'SN\s*:?\s*(\S+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned_output, re.IGNORECASE)
        if match:
            serial = match.group(1).strip()
            # Filter out placeholder values
            if serial and serial.lower() not in ['none', 'n/a', 'unknown', '']:
                print(f"✓ Matched pattern: {pattern}")
                return serial

    return None


# Test cases
test_outputs = [
    # Test 1: Cisco Catalyst with System Serial Number
    {
        "name": "Cisco Catalyst 9K (System Serial Number)",
        "output": """
Model Number                    : C9300-48U
Model Revision Number           : A0
System Serial Number            : FOC2345ABCD
""",
        "expected": "FOC2345ABCD"
    },

    # Test 2: Old Cisco with Processor Board ID
    {
        "name": "Cisco IOS (Processor Board ID)",
        "output": """
cisco WS-C3850-24P (MIPS) processor (revision A0) with 4194304K bytes of memory.
Processor board ID FCW1234A5BC
""",
        "expected": "FCW1234A5BC"
    },

    # Test 3: Generic Serial Number format
    {
        "name": "Generic Serial Number",
        "output": """
Product Name: Switch
Serial Number: SN123456789
""",
        "expected": "SN123456789"
    },

    # Test 4: With pagination
    {
        "name": "Output with --More--",
        "output": """
Cisco IOS Software
 --More--
Model Number: C9300-48U
System Serial Number: FOC9876XYZA
""",
        "expected": "FOC9876XYZA"
    },
]


def main():
    """Run all test cases."""
    print("=" * 80)
    print("Serial Number Extraction Test Suite")
    print("=" * 80)

    passed = 0
    failed = 0

    for i, test in enumerate(test_outputs, 1):
        print(f"\nTest {i}: {test['name']}")
        print("-" * 80)

        result = parse_show_version(test['output'])
        expected = test['expected']

        if result == expected:
            print(f"✓ PASS - Extracted: {result}")
            passed += 1
        else:
            print(f"✗ FAIL - Expected: {expected}, Got: {result}")
            failed += 1

    print("\n" + "=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
