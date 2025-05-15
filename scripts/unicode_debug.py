#!/usr/bin/env python3
"""
Unicode Debugging Tool for Hindi Text

This script helps diagnose issues with Hindi text rendering by analyzing the exact
Unicode sequences of input text, showing character codes, normalization differences,
and rendering differences.
"""

import unicodedata
import sys
import argparse

def analyze_unicode(text, label="Text"):
    """Analyze the Unicode sequence of a text string."""
    print(f"\n=== Unicode Analysis for {label} ===")
    print(f"Text: {text}")
    print(f"Length: {len(text)} characters")
    print("Character breakdown:")
    
    for i, char in enumerate(text):
        code_point = ord(char)
        try:
            char_name = unicodedata.name(char)
        except ValueError:
            char_name = "UNKNOWN"
            
        category = unicodedata.category(char)
        combining = "COMBINING" if unicodedata.combining(char) > 0 else "NON-COMBINING"
        
        print(f"  [{i}] U+{code_point:04X} {char} - {char_name} ({category}, {combining})")
    
    # Show different normalizations
    print("\nNormalization forms:")
    for form in ['NFC', 'NFD', 'NFKC', 'NFKD']:
        normalized = unicodedata.normalize(form, text)
        if normalized == text:
            status = "SAME AS INPUT"
        else:
            status = "DIFFERENT FROM INPUT"
        print(f"  {form}: {normalized} ({len(normalized)} chars) - {status}")
        if normalized != text:
            analyze_unicode(normalized, f"{form} Normalized")
    
    return text

def compare_texts(text1, text2):
    """Compare two texts and highlight differences."""
    print("\n=== Text Comparison ===")
    
    # Basic comparison
    if text1 == text2:
        print("✅ Texts are IDENTICAL.")
    else:
        print("❌ Texts are DIFFERENT.")
        
        if len(text1) != len(text2):
            print(f"Length difference: text1 has {len(text1)} chars, text2 has {len(text2)} chars")
        
        # Check if normalizing makes them equal
        forms = ['NFC', 'NFD', 'NFKC', 'NFKD']
        for form in forms:
            norm1 = unicodedata.normalize(form, text1)
            norm2 = unicodedata.normalize(form, text2)
            if norm1 == norm2:
                print(f"✅ Texts are IDENTICAL after {form} normalization.")
            
        # Character by character comparison
        min_len = min(len(text1), len(text2))
        for i in range(min_len):
            if text1[i] != text2[i]:
                print(f"First difference at position {i}:")
                print(f"  text1[{i}]: U+{ord(text1[i]):04X} {text1[i]} - {unicodedata.name(text1[i], 'UNKNOWN')}")
                print(f"  text2[{i}]: U+{ord(text2[i]):04X} {text2[i]} - {unicodedata.name(text2[i], 'UNKNOWN')}")
                break

def extract_sequence(text, start_char):
    """Extract a specific character sequence from text for analysis."""
    start_index = text.find(start_char)
    if start_index == -1:
        print(f"Character '{start_char}' not found in text.")
        return None
    
    # Try to extract a reasonable sequence (5 chars if possible)
    end_index = min(start_index + 5, len(text))
    sequence = text[start_index:end_index]
    
    analyze_unicode(sequence, f"Sequence starting with '{start_char}'")
    return sequence

def main():
    parser = argparse.ArgumentParser(description='Analyze Unicode sequences in Hindi text')
    parser.add_argument('text', nargs='?', help='Text to analyze')
    parser.add_argument('--file', '-f', help='Read text from file')
    parser.add_argument('--compare', '-c', help='Second text to compare with first text')
    parser.add_argument('--extract', '-e', help='Extract and analyze sequence starting with this character')
    parser.add_argument('--normalize', '-n', choices=['NFC', 'NFD', 'NFKC', 'NFKD'], 
                        help='Normalize text to this form')
    
    args = parser.parse_args()
    
    # Get the text from arguments or file
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read().strip()
        except Exception as e:
            print(f"Error reading file: {e}")
            return
    elif args.text:
        text = args.text
    else:
        text = "अल्ट्रासॉफ्ट मेमोरी फोम तकिया"  # Default example
    
    # Normalize if requested
    if args.normalize:
        text = unicodedata.normalize(args.normalize, text)
        print(f"Text normalized to {args.normalize} form")
    
    # Basic analysis
    analyze_unicode(text)
    
    # Extract sequence if requested
    if args.extract:
        extract_sequence(text, args.extract)
    
    # Compare if requested
    if args.compare:
        compare_texts(text, args.compare)

if __name__ == "__main__":
    main() 