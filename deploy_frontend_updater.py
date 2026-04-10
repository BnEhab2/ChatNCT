import os, glob, re

config_code = "const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? '' : 'https://chatnct.onrender.com';\n\n"

for p in glob.glob('frontend/js/*.js'):
    # skip config.js
    if 'config.js' in p:
        continue
    
    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()
        
    original = content
    
    # Prepend config code if not already there
    if "const API_BASE =" not in content:
        content = config_code + content
        
    # Replace fetch('/api/...) with fetch(`${API_BASE}/api/...)
    # Handles: fetch('/api/xxx' and fetch(`/api/xxx`
    content = re.sub(r"fetch\('(/api/[^']+)'\)", r"fetch(`${API_BASE}\1`)", content)
    content = re.sub(r'fetch\("(/api/[^"]+)"\)', r'fetch(`${API_BASE}\1`)', content)
    content = re.sub(r'fetch\(`(/api/[^`]+)`\)', r'fetch(`${API_BASE}\1`)', content)
    
    # Also handle fetch('/api/xxx', {
    content = re.sub(r"fetch\('(/api/[^']+)',", r"fetch(`${API_BASE}\1`,", content)
    content = re.sub(r'fetch\("(/api/[^"]+)",', r'fetch(`${API_BASE}\1`,', content)
    content = re.sub(r'fetch\(`(/api/[^`]+)`,', r'fetch(`${API_BASE}\1`,', content)
    
    if original != content:
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {p}")
