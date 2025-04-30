#!/usr/bin/env python
import sys
import os

# Adjust path to import from the root directory's utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from utils.helpers import parse_color
except ImportError:
    print("Error: Could not import parse_color from utils.helpers.")
    print("Ensure the script is run from the project root or the path is correct.")
    sys.exit(1)

def run_tests():
    test_colors = [
        ("rgba(255, 255, 255, 1)",   "#FFFFFF"),   # Opaque White
        ("rgba(139, 87, 42, 0.66)", "#8B572A A8"), # Brownish, semi-transparent (Note: Alpha ~168 -> A8)
        ("rgb(0, 0, 255)",         "#0000FF"),   # Blue
        ("#FF0000",                 "#FF0000"),   # Red (Hex)
        ("#0F0",                   "#00FF00"),   # Green (Short Hex expands)
        ("#000000FF",             "#000000"),   # Black Opaque (Hex with Alpha 255 simplifies)
        ("#00000080",             "#000000 80"), # Black 50% Transparent (Hex with Alpha)
        ("white",                  "#FFFFFF"),   # Named color
        ("black",                  "#000000"),   # Named color
        ("transparent",            "#000000 00"), # Named color (Alpha 0)
        ("invalid-color",        None),        # Invalid name
        ("rgba(50, 50, 50, 1.5)",  "#323232"),   # Invalid alpha clamps to 1.0 -> opaque
        ("rgb(300, 0, 0)" ,        None)         # Invalid RGB value fails parsing
    ]

    print("--- Running Color Parser Tests ---")
    passed = 0
    failed = 0
    for color_str, expected_hex in test_colors:
        result = parse_color(color_str)
        # Quick hack for comparing hex with alpha slightly differently if needed
        # For now, just direct comparison
        if result == expected_hex or (result and expected_hex and result.replace(" ", "") == expected_hex.replace(" ", "")):
            print(f"[PASS] Input: \"{color_str}\" -> Output: {result}")
            passed += 1
        else:
            print(f"[FAIL] Input: \"{color_str}\" -> Expected: {expected_hex}, Got: {result}")
            failed += 1
            
    print("--- Tests Complete ---")
    print(f"Result: {passed} passed, {failed} failed.")

if __name__ == "__main__":
    run_tests() 