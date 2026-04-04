import os
import re

def clean_comments_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # remove lines that are just "# ----..."
        if re.match(r'^\s*#\s*-{5,}\s*$', line):
            i += 1
            continue
            
        # if it's a normal comment like # init global state
        # let's turn it into a bit more sloppy: # init state or just lowercase
        stripped = line.lstrip()
        if stripped.startswith('#') and not stripped.startswith('#!') and not stripped.startswith('# noqa'):
            # lowercase it
            indent = line[:len(line) - len(stripped)]
            comment_text = stripped[1:].strip()
            # remove numbers like "1. "
            comment_text = re.sub(r'^\d+\.\s*', '', comment_text)
            
            # just make it lower case
            new_lines.append(indent + '# ' + comment_text.lower() + '\n')
            i += 1
            continue
            
        new_lines.append(line)
        i += 1
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

for root, dirs, files in os.walk('.'):
    if 'venv' in root or 'node_modules' in root or '.git' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            clean_comments_in_file(os.path.join(root, file))
