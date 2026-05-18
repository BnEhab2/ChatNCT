"""
Keyword-based search for student affairs data.
Uses the same shared local search engine as Marwan's study_agent.
"""

import os
from typing import Dict, List

from mainAgent.sub_agents.rag_search import load_text_documents, search_documents


# Global list to store loaded paragraphs (lazy loaded)
_documents: List[Dict[str, str]] = []

# Arabic stop words
STOP_WORDS_AR = {
    'في', 'من', 'على', 'إلى', 'الى', 'عن', 'مع', 'هل', 'ما', 'هو', 'هي',
    'هذا', 'هذه', 'ذلك', 'تلك', 'التي', 'الذي', 'الذين', 'اللتي', 'اللذين',
    'كان', 'كانت', 'يكون', 'تكون', 'أن', 'ان', 'إن', 'لا', 'لم', 'لن',
    'قد', 'بين', 'حتى', 'أو', 'او', 'ثم', 'اي', 'أي', 'كل', 'بعض',
    'كيف', 'أين', 'اين', 'متى', 'كم', 'لماذا', 'ليه', 'ازاي', 'فين',
    'يا', 'و', 'ف', 'ب', 'ل', 'ده', 'دي', 'دا', 'مش', 'مين',
    'عاوز', 'عايز', 'عايزه', 'عاوزه', 'ممكن', 'لو', 'سمحت',
    'انا', 'أنا', 'انت', 'احنا', 'احنة', 'اللي', 'بتاع', 'بتاعت',
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'when',
    'where', 'who', 'which', 'can', 'do', 'does', 'i', 'me', 'my',
    'want', 'need', 'please', 'tell', 'about',
}

# Term variations / synonyms (Arabic + transliterated)
TERM_VARIATIONS = {
    'مصروفات': ['مصروفات', 'مصاريف', 'رسوم', 'تكلفة', 'فلوس', 'مصاريف الدراسة', 'fees'],
    'تقديم': ['تقديم', 'تسجيل', 'التحاق', 'قبول', 'admission', 'apply'],
    'تحويل': ['تحويل', 'نقل', 'transfer'],
    'أوراق': ['أوراق', 'اوراق', 'مستندات', 'وثائق', 'ورق', 'documents', 'papers'],
    'تخصصات': ['تخصصات', 'أقسام', 'اقسام', 'برامج', 'كليات', 'departments', 'majors'],
    'جدول': ['جدول', 'جداول', 'جدوال', 'مواعيد', 'schedule', 'timetable'],
    'تدريب': ['تدريب', 'تدريبات', 'training', 'internship'],
    'منح': ['منح', 'إعفاء', 'اعفاء', 'تخفيض', 'تقسيط', 'scholarship'],
    'مكان': ['مكان', 'موقع', 'عنوان', 'فين', 'أين', 'اين', 'location', 'address'],
    'شؤون': ['شؤون', 'شئون', 'شوون', 'student affairs'],
    'دراسة': ['دراسة', 'دراسية', 'محاضرات', 'study', 'lectures'],
    'دبلوم': ['دبلوم', 'دبلومة', 'diploma'],
    'ماجستير': ['ماجستير', 'دراسات عليا', 'master', 'postgrad'],
    'امتحان': ['امتحان', 'امتحانات', 'اختبار', 'اختبارات', 'قدرات', 'exam', 'test'],
    'ثانوية': ['ثانوية', 'ثانوي', 'secondary', 'high school'],
    'فني': ['فني', 'فنية', 'دبلومات', 'صنايع', 'technical'],
    'تخرج': ['تخرج', 'شهادة', 'graduation', 'certificate', 'degree'],
}


def _load_paragraphs() -> List[str]:
    """Lazy load paragraphs from data files on first search."""
    global _documents
    if _documents:
        return [doc["content"] for doc in _documents]

    folder = os.path.join(os.path.dirname(__file__), "data")
    _documents = load_text_documents(folder, split_paragraphs=True)
    print(f"[OK] {len(_documents)} student affairs paragraphs loaded.")
    return [doc["content"] for doc in _documents]


def search_data(query: str) -> dict:
    """
    Search student affairs paragraphs with the shared keyword search engine.
    """
    _load_paragraphs()
    if not _documents:
        return {"results": [], "message": "لا توجد بيانات محملة."}

    return search_documents(
        query=query,
        documents=_documents,
        term_variations=TERM_VARIATIONS,
        stop_words=STOP_WORDS_AR,
        min_keyword_length=2,
        top_k=5,
    )


# Paragraphs are loaded lazily on first use to keep startup fast.
