import re

def extract_entities(text: str) -> dict:
    # English patterns
    dates = re.findall(r"\b(?:\d{1,2}[-/])?\d{1,2}[-/]\d{2,4}\b", text)
    articles = re.findall(r"Article\s+\d+", text)
    verdicts = re.findall(r"(Judgment|Dismissed|Convicted|Acquitted)", text, re.IGNORECASE)

    # Arabic patterns
    arabic_articles = re.findall(r"(?:المادة|مادة)\s+\d+", text)
    arabic_verdicts = re.findall(r"(حكمت المحكمة.*?[\.\n])", text)

    return {
        "dates": dates,
        "articles": articles + arabic_articles,
        "verdicts": verdicts + arabic_verdicts
    }
