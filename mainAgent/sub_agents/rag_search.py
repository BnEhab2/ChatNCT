"""
Shared keyword-based search helpers for local RAG-style agents.

The agents keep their own data folders and domain-specific synonyms, while this
module owns the common loading, keyword extraction, expansion, and scoring flow.
"""

import os
import re
from typing import Dict, Iterable, List, Optional


DEFAULT_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "as", "into",
    "through", "during", "before", "after", "between", "under", "again",
    "then", "once", "here", "there", "when", "where", "why", "how", "all",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "and", "but", "if", "or", "because", "until", "while", "this", "that",
    "these", "those", "it", "its", "what", "which", "who", "whom", "whose",
    "about", "summary", "summarize", "quiz", "explain", "tell", "me",
    "make", "give", "lecture", "lectures", "create", "show", "difference",
}


def load_text_documents(folder: str, split_paragraphs: bool = False) -> List[Dict[str, str]]:
    """Load .txt files as searchable documents."""
    documents: List[Dict[str, str]] = []

    if not os.path.exists(folder):
        return documents

    for file_name in sorted(os.listdir(folder)):
        if not file_name.endswith(".txt"):
            continue

        file_path = os.path.join(folder, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:
            print(f"[ERROR] Error loading {file_name}: {exc}")
            continue

        if split_paragraphs:
            for index, paragraph in enumerate(content.split("\n\n"), start=1):
                paragraph = paragraph.strip()
                if paragraph:
                    documents.append({
                        "source": file_name,
                        "section": str(index),
                        "content": paragraph,
                    })
        else:
            documents.append({
                "source": file_name,
                "section": "",
                "content": content,
            })

    return documents


def extract_keywords(
    query: str,
    stop_words: Optional[Iterable[str]] = None,
    min_length: int = 2,
) -> List[str]:
    """Extract meaningful query terms in Arabic and English."""
    ignored = set(DEFAULT_STOP_WORDS)
    if stop_words:
        ignored.update(stop_words)

    words = re.findall(r"[\w\u0600-\u06FF]+", query.lower())
    return [word for word in words if word not in ignored and len(word) >= min_length]


def expand_query(keywords: List[str], term_variations: Dict[str, List[str]]) -> List[str]:
    """Expand keywords using domain-specific synonyms and variations."""
    expanded = set(keywords)

    for keyword in keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in term_variations:
            expanded.update(term_variations[keyword_lower])

        for term, variations in term_variations.items():
            lowered_variations = [variation.lower() for variation in variations]
            if keyword_lower in lowered_variations:
                expanded.add(term)
                expanded.update(variations)

    return list(expanded)


def search_documents(
    query: str,
    documents: List[Dict[str, str]],
    term_variations: Optional[Dict[str, List[str]]] = None,
    stop_words: Optional[Iterable[str]] = None,
    min_keyword_length: int = 2,
    snippet_chars: Optional[int] = None,
    include_full_content: bool = False,
    top_k: int = 5,
) -> Dict[str, object]:
    """Score documents by filename, exact matches, synonyms, phrases, and proximity."""
    if not documents:
        return {"results": [], "total_matches": 0}

    term_variations = term_variations or {}
    keywords = extract_keywords(query, stop_words, min_keyword_length)
    if not keywords:
        keywords = [word for word in query.lower().split() if len(word) >= min_keyword_length]

    expanded_terms = expand_query(keywords, term_variations)
    results = []

    for document in documents:
        content = document["content"]
        content_lower = content.lower()
        source = document.get("source", "")
        source_lower = source.lower()
        relevance_score = 0.0
        matched_terms = []

        for term in keywords:
            if term in source_lower:
                relevance_score += 10
                matched_terms.append(f"filename:{term}")

            if term.isdigit() and (
                f"lecture {term}" in source_lower or f"lecture{term}" in source_lower
            ):
                relevance_score += 15
                matched_terms.append(f"lecture_number:{term}")

            count = content_lower.count(term)
            if count > 0:
                relevance_score += count * 3
                matched_terms.append(f"exact:{term}({count})")

        for term in expanded_terms:
            if term in keywords:
                continue
            count = content_lower.count(term.lower())
            if count > 0:
                relevance_score += count * 2
                matched_terms.append(f"synonym:{term}({count})")

        if len(keywords) >= 2:
            phrase = " ".join(keywords[:3])
            if phrase in content_lower:
                relevance_score += 15
                matched_terms.append(f"phrase:{phrase}")

            for index in range(len(keywords) - 1):
                first = re.escape(keywords[index])
                second = re.escape(keywords[index + 1])
                if re.search(f"{first}.{{0,100}}{second}", content_lower):
                    relevance_score += 5
                    matched_terms.append(f"context:{keywords[index]}-{keywords[index + 1]}")

        first_line = content_lower.split("\n", 1)[0][:120]
        for term in keywords:
            if term in first_line:
                relevance_score += 4
                matched_terms.append(f"header:{term}")

        if relevance_score <= 0:
            continue

        result = {
            "file": source,
            "source": source,
            "section": document.get("section", ""),
            "content": _make_snippet(content, keywords, expanded_terms, snippet_chars),
            "relevance_score": relevance_score,
            "matched_terms": matched_terms[:10],
        }
        if include_full_content:
            result["full_content"] = content

        results.append(result)

    results.sort(key=lambda item: item["relevance_score"], reverse=True)
    return {"results": results[:top_k], "total_matches": len(results)}


def _make_snippet(
    content: str,
    keywords: List[str],
    expanded_terms: List[str],
    snippet_chars: Optional[int],
) -> str:
    if not snippet_chars:
        return content

    content_lower = content.lower()
    first_match_pos = len(content_lower)

    for term in keywords + expanded_terms:
        if len(term) < 2:
            continue
        pos = content_lower.find(term.lower())
        if pos != -1 and pos < first_match_pos:
            first_match_pos = pos

    if first_match_pos == len(content_lower):
        first_match_pos = 0

    radius = max(1, snippet_chars // 2)
    start = max(0, first_match_pos - radius)
    end = min(len(content), first_match_pos + radius)
    snippet = content[start:end]

    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return snippet
