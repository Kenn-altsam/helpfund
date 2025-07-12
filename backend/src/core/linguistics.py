from typing import Optional
from pymorphy2 import MorphAnalyzer

morph = MorphAnalyzer()

def normalize_russian_word(word: str) -> str:
    """
    Normalizes a Russian word or phrase to its canonical (nominative, singular) form.
    Handles multi-word names and capitalizes each part.
    e.g., "Алмате" -> "Алматы"
    e.g., "западном казахстане" -> "Западный Казахстан"
    """
    if not isinstance(word, str) or not word.strip():
        return word
    
    words = word.split()
    normalized_words = [morph.parse(w)[0].normal_form for w in words]
    capitalized_words = [w.capitalize() for w in normalized_words]
    
    return " ".join(capitalized_words)


def extract_location_from_text(text: str) -> Optional[str]:
    """
    A simple example: find the word after "в" or "из"
    """
    words = text.split()
    for i, word in enumerate(words):
        if word in ["в", "из"] and i + 1 < len(words):
            return words[i+1].strip(".,?!")
    return None 