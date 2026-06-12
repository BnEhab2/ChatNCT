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
    """Load all lecture materials from the database."""
    global materials
    global _documents
    if materials:
        return materials  # Already loaded

    from mainAgent.db.database import get_connection, release_connection
    conn = get_connection()
    if not conn:
        print("[ERROR] Could not connect to DB for materials.")
        return {}
        
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT m.title, m.content, c.name 
            FROM materials m 
            LEFT JOIN courses c ON m.course_id = c.id
            WHERE m.content IS NOT NULL
        """)
        rows = cur.fetchall()
        
        _documents = []
        materials = {}
        for row in rows:
            title = row[0]
            content = row[1]
            course_name = row[2] or "Unknown"
            
            source_name = title if course_name.lower() in title.lower() else f"{course_name} - {title}"
            
            _documents.append({
                "source": source_name,
                "content": content
            })
            materials[source_name] = content
            
        print(f"[OK] {len(materials)} study materials loaded from database.")
    except Exception as e:
        print(f"[ERROR] Loading materials from DB: {e}")
    finally:
        release_connection(conn)

    return materials


def search_material(query: str, subject: str = None) -> dict:
    """Search lecture materials using the shared keyword search engine.
    If subject is provided, it only searches within that specific subject's materials."""
    if not _documents:
        load_materials()

    docs_to_search = _documents
    if subject:
        subject_lower = subject.lower()
        docs_to_search = [d for d in _documents if subject_lower in d["source"].lower()]

    if not docs_to_search:
        return {"error": f"No materials found for the specified subject: {subject}"}

    return search_documents(
        query=query,
        documents=docs_to_search,
        term_variations=TERM_VARIATIONS,
        min_keyword_length=3,
        snippet_chars=4000,
        include_full_content=True,
        top_k=5,
    )


def get_all_materials_info(subject: str = None) -> dict:
    """
    Get a summary of all loaded materials including a content preview.
    If subject is provided, it filters the results to only include materials for that subject.
    Use this to know what lectures exist and get a quick overview of their topics.
    To get full content for a specific topic, use search_material instead.
    """
    if not materials:
        load_materials()
        
    info = {}
    for name, content in materials.items():
        if subject and subject.lower() not in name.lower():
            continue
        # Extract first meaningful lines as a topic preview
        preview_lines = []
        for line in (content or "").split('\n'):
            line = line.strip()
            if line and len(line) > 5:
                preview_lines.append(line)
            if len(preview_lines) >= 8:
                break
        
        info[name] = {
            "lecture_name": name,
            "topic_preview": "\n".join(preview_lines),
            "total_words": len(content.split()) if content else 0,
        }
    return {"materials": info, "total_count": len(info)}


def get_available_subjects() -> list:
    """
    Get list of available subjects from loaded materials.
    """
    if not materials:
        load_materials()
        
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
