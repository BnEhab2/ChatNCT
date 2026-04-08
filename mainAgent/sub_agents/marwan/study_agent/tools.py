"""
tools.py - Enhanced search utility for the Study Agent
"""

import os
import re
from typing import Dict, List


# Global dictionary to store loaded materials
materials: Dict[str, str] = {}

# Common academic terms and their variations
TERM_VARIATIONS = {
    # Computer Science terms
    'ram': ['ram', 'random access memory', 'primary memory', 'volatile memory', 'main memory'],
    'rom': ['rom', 'read only memory', 'non-volatile memory', 'firmware memory'],
    'cpu': ['cpu', 'central processing unit', 'processor', 'core'],
    'os': ['os', 'operating system', 'system software'],
    'db': ['db', 'database', 'dbms', 'database management system'],
    'sql': ['sql', 'structured query language', 'query language'],
    'io': ['io', 'i/o', 'input output', 'input/output', 'peripheral'],
    'api': ['api', 'application programming interface'],
    'ui': ['ui', 'user interface', 'interface'],
    'gui': ['gui', 'graphical user interface', 'gui'],
    'cli': ['cli', 'command line interface', 'terminal', 'shell'],
    'http': ['http', 'hypertext transfer protocol'],
    'url': ['url', 'uniform resource locator', 'web address'],
    'html': ['html', 'hypertext markup language'],
    'css': ['css', 'cascading style sheets'],
    'js': ['js', 'javascript', 'ecmascript'],
    'oop': ['oop', 'object oriented programming', 'object-oriented'],
    'ide': ['ide', 'integrated development environment'],
    
    # General academic terms
    'intro': ['intro', 'introduction', 'overview', 'basics', 'fundamentals'],
    'def': ['def', 'definition', 'meaning', 'what is', 'concept'],
    'types': ['types', 'kinds', 'categories', 'classifications', 'varieties'],
    'features': ['features', 'characteristics', 'properties', 'attributes'],
    'advantages': ['advantages', 'benefits', 'pros', 'strengths'],
    'disadvantages': ['disadvantages', 'drawbacks', 'cons', 'limitations'],
}


def load_materials(materials_dir: str = "materials") -> Dict[str, str]:
    """
    Load all lecture materials from the materials directory.
    """
    global materials
    materials = {}
    
    # Get the directory where this file is located
    base_dir = os.path.dirname(os.path.abspath(__file__))
    materials_path = os.path.join(base_dir, materials_dir)
    
    # Check if materials directory exists
    if not os.path.exists(materials_path):
        print(f"Warning: Materials directory '{materials_path}' not found!")
        return materials
    
    # Load all .txt files (sorted for consistent order)
    for file in sorted(os.listdir(materials_path)):
        if file.endswith(".txt"):
            file_path = os.path.join(materials_path, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    materials[file] = f.read()
                    print(f"✓ Loaded: {file}")
            except Exception as e:
                print(f"✗ Error loading {file}: {e}")
    
    print(f"\n Total materials loaded: {len(materials)}")
    return materials


def extract_keywords(query: str) -> List[str]:
    """
    Extract important keywords from user query.
    
    Removes common words and keeps meaningful terms.
    """
    # Words to ignore
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
        'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here',
        'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
        'because', 'until', 'while', 'this', 'that', 'these', 'those', 'it',
        'its', 'what', 'which', 'who', 'whom', 'whose', 'about', 'against',
        'summary', 'summarize', 'quiz', 'explain', 'tell', 'me', 'make', 'give',
        'lecture', 'lectures', 'create', 'show', 'difference', 'between'
    }
    
    # Extract words
    words = re.findall(r'\b\w+\b', query.lower())
    
    # Filter out stop words and short words
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    return keywords


def expand_query(keywords: List[str]) -> List[str]:
    """
    Expand query with term variations and synonyms.
    """
    expanded = set(keywords)
    
    for keyword in keywords:
        keyword_lower = keyword.lower()
        
        # Add variations for known terms
        if keyword_lower in TERM_VARIATIONS:
            expanded.update(TERM_VARIATIONS[keyword_lower])
        
        # Check if keyword is a variation of something
        for term, variations in TERM_VARIATIONS.items():
            if keyword_lower in variations:
                expanded.add(term)
                expanded.update(variations)
    
    return list(expanded)


def search_material(query: str) -> dict:
    """
    Intelligent search through loaded materials.
    
    Features:
    1. Keyword extraction (removes common words)
    2. Query expansion (adds synonyms and variations)
    3. Multi-level matching (filename, exact, partial, semantic)
    4. Relevance scoring
    5. Returns full content for better responses
    
    Args:
        query (str): The search query from the user.
    
    Returns:
        dict: Dictionary containing search results with file, content, and relevance score.
    """
    results = []
    
    # Extract important keywords
    keywords = extract_keywords(query)
    
    # If no keywords found, use original query terms
    if not keywords:
        keywords = query.lower().split()
    
    # Expand query with variations
    expanded_terms = expand_query(keywords)
    
    query_lower = query.lower()
    
    for name, content in materials.items():
        content_lower = content.lower()
        file_name_lower = name.lower()
        
        relevance_score = 0
        matched_terms = []
        
        # 1. Filename matching (highest priority)
        for term in keywords:
            if term in file_name_lower:
                relevance_score += 10
                matched_terms.append(f"filename:{term}")
            
            # Lecture number matching
            if term.isdigit():
                lecture_pattern = f"lecture {term}"
                if lecture_pattern in file_name_lower or f"lecture{term}" in file_name_lower:
                    relevance_score += 15
                    matched_terms.append(f"lecture_number:{term}")
        
        # 2. Exact content matching
        for term in keywords:
            if len(term) > 2:
                count = content_lower.count(term)
                if count > 0:
                    relevance_score += count * 2
                    matched_terms.append(f"exact:{term}({count})")
        
        # 3. Expanded term matching (synonyms, variations)
        for term in expanded_terms:
            if len(term) > 2 and term not in keywords:
                count = content_lower.count(term)
                if count > 0:
                    relevance_score += count * 1.5
                    matched_terms.append(f"synonym:{term}({count})")
        
        # 4. Phrase matching (multiple words together)
        keyword_phrases = ' '.join(keywords[:3])  # First 3 keywords as phrase
        if keyword_phrases in content_lower:
            relevance_score += 20
            matched_terms.append(f"phrase:{keyword_phrases}")
        
        # 5. Case-sensitive uppercase matching (for acronyms)
        for term in keywords:
            if term.isupper() or len(term) <= 3:
                if term in content:  # Check original case
                    relevance_score += 3
                    matched_terms.append(f"uppercase:{term}")
        
        # 6. Contextual matching - check for related terms near each other
        if len(keywords) >= 2:
            for i in range(len(keywords) - 1):
                term1 = keywords[i]
                term2 = keywords[i + 1]
                # Check if both terms appear within 100 characters of each other
                pattern = f"{term1}(.{{0,100}}){term2}"
                if re.search(pattern, content_lower, re.IGNORECASE):
                    relevance_score += 5
                    matched_terms.append(f"context:{term1}-{term2}")
        
        # Only include files with matches
        if relevance_score > 0:
            # Find the best match position
            first_match_pos = len(content_lower)
            
            # Check for keyword matches
            for term in keywords:
                if len(term) > 2:
                    pos = content_lower.find(term)
                    if pos != -1 and pos < first_match_pos:
                        first_match_pos = pos
            
            # Check for expanded term matches
            for term in expanded_terms:
                if len(term) > 2:
                    pos = content_lower.find(term)
                    if pos != -1 and pos < first_match_pos:
                        first_match_pos = pos
            
            # Extract relevant snippet (2000 chars for better context)
            start = max(0, first_match_pos - 2000)
            end = min(len(content), first_match_pos + 2000)
            snippet = content[start:end]
            
            # Add ellipsis if needed
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."
            
            results.append({
                "file": name,
                "content": snippet,
                "full_content": content,
                "relevance_score": relevance_score,
                "matched_terms": matched_terms[:10]  # Top 10 matched terms
            })
    
    # Sort by relevance score (highest first)
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    # Return top 5 results
    return {"results": results[:5], "total_matches": len(results)}


def get_all_materials_info() -> dict:
    """
    Get information about all loaded materials.
    """
    info = {}
    for name, content in materials.items():
        info[name] = {
            "size": len(content),
            "lines": content.count('\n') + 1,
            "words": len(content.split())
        }
    return info


def get_available_subjects() -> list:
    """
    Get list of available subjects from loaded materials.
    """
    subjects = set()
    for name in materials.keys():
        if 'C++' in name or 'c++' in name.lower():
            subjects.add('C++')
        elif 'DataBase' in name or 'Database' in name or 'database' in name.lower():
            subjects.add('Database')
        elif 'IT Essential' in name or 'IT Essential' in name:
            subjects.add('IT Essentials')
        elif 'Linux' in name:
            subjects.add('Linux')
        elif 'Operating System' in name:
            subjects.add('Operating System')
    return sorted(list(subjects))


# Auto-load materials when module is imported
print("\n" + "="*60)
print(" Loading materials...")
print("="*60)
load_materials()
subjects = get_available_subjects()
print(f"\n Available subjects ({len(subjects)}):")
for subject in subjects:
    print(f"   • {subject}")
print("="*60)