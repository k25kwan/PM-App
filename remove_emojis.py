#!/usr/bin/env python3
"""Remove all emojis from Python files in the app directory."""
import re
from pathlib import Path

def remove_emojis(text):
    """Remove emoji characters from text."""
    # Extended emoji pattern
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        u"\U0001FA00-\U0001FA6F"  # Chess Symbols
        u"\U00002600-\U000026FF"  # Misc symbols
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

# Files to process
files = [
    Path(r"c:\Users\Kevin Kwan\PM-app\app\pages\1_IPS_Questionnaire.py"),
    Path(r"c:\Users\Kevin Kwan\PM-app\app\pages\3_Security_Screening.py"),
]

for file_path in files:
    if file_path.exists():
        print(f"Processing {file_path.name}...")
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove emojis
        new_content = remove_emojis(content)
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"  ✓ Cleaned {file_path.name}")
    else:
        print(f"  ✗ File not found: {file_path}")

print("\nDone! All emojis removed.")
