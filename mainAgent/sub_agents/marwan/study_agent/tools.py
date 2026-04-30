import os
from typing import Dict, List

from mainAgent.sub_agents.rag_search import load_text_documents, search_documents


# Loaded lazily on first search.
materials: Dict[str, str] = {}
_documents: List[Dict[str, str]] = []

# Study-agent term variations and synonyms.
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
    'gui': ['gui', 'graphical user interface'],
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
    """Load all lecture materials from the materials directory."""
    global materials
    global _documents
    if materials:
        return materials  # Already loaded

    base_dir = os.path.dirname(os.path.abspath(__file__))
    materials_path = os.path.join(base_dir, materials_dir)

    _documents = load_text_documents(materials_path)
    materials = {doc["source"]: doc["content"] for doc in _documents}

    print(f"[OK] {len(materials)} study materials loaded.")
    return materials


def search_material(query: str) -> dict:
    """Search lecture materials using the shared keyword search engine."""
    if not _documents:
        load_materials()

    return search_documents(
        query=query,
        documents=_documents,
        term_variations=TERM_VARIATIONS,
        min_keyword_length=3,
        snippet_chars=4000,
        include_full_content=True,
        top_k=5,
    )


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


# Materials are loaded lazily on first use to keep startup fast.
