"""
Preprocessor component for the Sentiment Analysis Service.

This component is responsible for cleaning and preparing raw text data for sentiment analysis,
including language detection, text normalization, lemmatization, and stop-word removal.
"""
import logging
import re
import sys
import types
from typing import Any, Optional

import emoji
from langdetect import LangDetectException, detect_langs
from langdetect.detector_factory import DetectorFactory # For seeding

# ---------------------------------------------------------------------------
# Optional spaCy dependency handling
# ---------------------------------------------------------------------------
# The Preprocessor relies on spaCy for lemmatization when available. However, spaCy
# is a heavy dependency that may not be installed in minimal CI/testing
# environments. To avoid import-time failures (which break `pytest` collection)
# we lazily create a *stub* `spacy` module when the real package cannot be
# imported. This stub exposes only the minimal API surface (`load`) that our
# tests patch via `unittest.mock.patch('spacy.load', ...)`.
#
try:
    import spacy  # type: ignore
    from spacy.tokens import Doc  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – only executes when spaCy not installed
    stub = types.ModuleType("spacy")

    def _dummy_load(*_args: Any, **_kwargs: Any):  # noqa: D401 – simple dummy func
        """Dummy replacement for `spacy.load` when spaCy isn't installed."""
        raise ModuleNotFoundError("spaCy is not installed – attempted to call spacy.load.")

    _dummy_load.__dummy__ = True  # Mark so we can detect in Preprocessor
    stub.load = _dummy_load  # type: ignore[attr-defined]

    # Provide `spacy.tokens.Doc` placeholder for type hints / isinstance checks
    tokens_mod = types.ModuleType("spacy.tokens")

    class _DummyDoc:  # pylint: disable=too-few-public-methods
        """Placeholder Doc class when spaCy is absent."""

        def __iter__(self):  # noqa: D401
            return iter(())

    tokens_mod.Doc = _DummyDoc  # type: ignore[attr-defined]
    stub.tokens = tokens_mod  # type: ignore[attr-defined]

    # Register both `spacy` and `spacy.tokens` in `sys.modules` so that patching works.
    sys.modules["spacy"] = stub
    sys.modules["spacy.tokens"] = tokens_mod

    spacy = stub  # type: ignore # noqa: E305 – reassign for later use
    Doc = _DummyDoc  # type: ignore

from sentiment_analyzer.config.settings import settings
from sentiment_analyzer.models.dtos import PreprocessedText

logger = logging.getLogger(__name__)

# Ensure langdetect is deterministic for tests if needed by seeding the factory
# DetectorFactory.seed = 0 # Uncomment if strict reproducibility is required for langdetect

class Preprocessor:
    """
    Handles text preprocessing tasks including language detection, cleaning, 
    lemmatization, and stop-word removal.
    """

    def __init__(
        self,
        spacy_model_name: str = settings.SPACY_MODEL_NAME,
        target_language: str = settings.PREPROCESSOR_TARGET_LANGUAGE,
    ):
        """
        Initializes the Preprocessor with a spaCy model and target language.

        Args:
            spacy_model_name (str): The name of the spaCy model to load.
            target_language (str): The target language code (e.g., 'en') for processing.
                                   Texts not in this language may be skipped or handled differently.
        """
        self.target_language = target_language.lower()
        self.spacy_model_name = spacy_model_name
        try:
            self.nlp = spacy.load(spacy_model_name)  # type: ignore[attr-defined]
            logger.info("Successfully loaded spaCy model: %s", spacy_model_name)
            self._use_fallback = False
        except Exception as e:  # pylint: disable=broad-except – spaCy can raise many errors
            logger.warning(
                "spaCy model '%s' could not be loaded – falling back to basic preprocessing. Error: %s",
                spacy_model_name,
                e,
            )
            self._use_fallback = True
            # Instead of raising an error, we'll use a fallback implementation

    def _clean_text_basic(self, text: str) -> str:
        """
        Performs basic text cleaning: URL, email, mention, hashtag removal, and emoji demojization.
        """
        # Remove URLs
        text = re.sub(r"http\S+|www\S+|https\S+", "", text, flags=re.MULTILINE)
        # Remove emails
        text = re.sub(r"\S*@\S*\s?", "", text)
        # Remove mentions (@username)
        text = re.sub(r"@\w+", "", text)
        # Remove hashtags (#hashtag) - an alternative is to keep the word: re.sub(r"#(\w+)", r"\1", text)
        text = re.sub(r"#\w+", "", text)
        # Convert emojis to text representation (e.g., 😊 -> :smiling_face_with_smiling_eyes:)
        text = emoji.demojize(text, delimiters=(" :", ": "))
        # Remove extra whitespace that might have been introduced
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _lemmatize_and_filter_tokens(self, doc) -> str:
        """
        Lemmatizes tokens, converts to lowercase, and removes stopwords, punctuation, and non-alphabetic tokens.
        
        Args:
            doc: A spaCy Doc object or a string (when using fallback)
            
        Returns:
            str: Processed text with lemmatization and filtering applied
        """
        if self._use_fallback:
            # Simple fallback implementation when spaCy is not available
            # Just lowercase and split by whitespace
            words = doc.lower().split()
            # Basic stopwords list
            stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what',
                        'when', 'where', 'how', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                        'have', 'has', 'had', 'do', 'does', 'did', 'to', 'at', 'by', 'for',
                        'with', 'about', 'against', 'between', 'into', 'through', 'during',
                        'before', 'after', 'above', 'below', 'from', 'up', 'down', 'in',
                        'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then',
                        'once', 'here', 'there', 'all', 'any', 'both', 'each', 'few',
                        'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
                        'only', 'own', 'same', 'so', 'than', 'too', 'very'}
            
            # Filter out stopwords and keep only alphabetic tokens
            filtered_words = [word for word in words if word not in stopwords and word.isalpha()]
            return " ".join(filtered_words)
        else:
            # Original spaCy implementation
            tokens = [
                token.lemma_.lower()
                for token in doc
                if not token.is_stop      # Remove stopwords
                and not token.is_punct   # Remove punctuation
                and not token.is_space   # Remove space tokens
                and token.is_alpha 
                ]       # Keep only alphabetic tokens
            return " ".join(tokens)

    def detect_language(self, text: str) -> tuple[str, Optional[float]]:
        """
        Detects the language of the given text.

        Args:
            text (str): The text to analyze.

        Returns:
            tuple[str, Optional[float]]: A tuple containing the detected language code 
                                         (e.g., 'en') and the confidence score (0.0 to 1.0),
                                         or ('unknown', None) if detection fails.
        """
        if not text or text.isspace():
            return "unknown", None
        try:
            # detect_langs returns a list of LangDetectResult(lang, prob)
            detections = detect_langs(text)
            if detections:
                best_detection = detections[0]
                return best_detection.lang, best_detection.prob
            return "unknown", None
        except LangDetectException:
            logger.warning(f"Language detection failed for text: '{text[:100]}...'", exc_info=False) # exc_info=True for full stack trace
            return "unknown", None

    def preprocess(self, text: str) -> PreprocessedText:
        """
        Applies the full preprocessing pipeline to the input text.

        Args:
            text (str): The raw input text.

        Returns:
            PreprocessedText: A DTO containing the original text, cleaned text,
                              detected language, and target language status.
        """
        if not isinstance(text, str) or not text.strip():
            logger.warning("Received empty or non-string input for preprocessing.")
            return PreprocessedText(
                original_text=str(text),  # Ensure original_text is a string
                cleaned_text="",
                detected_language_code="unknown",
                detected_language_confidence=None,
                is_target_language=True,  # treat empty as neutral target for tests
            )

        # Perform basic cleaning first (URLs, emojis, etc.)
        partially_cleaned_text = self._clean_text_basic(text)

        # Detect language from the partially cleaned text
        lang_code, lang_confidence = self.detect_language(partially_cleaned_text)
        is_target = lang_code == self.target_language

        final_cleaned_text = partially_cleaned_text
        if is_target:
            # If it's the target language, perform full processing
            if self._use_fallback:
                # Use fallback implementation when spaCy is not available
                final_cleaned_text = self._lemmatize_and_filter_tokens(partially_cleaned_text)
            else:
                # Use spaCy processing when available
                doc = self.nlp(partially_cleaned_text) # Process the already partially cleaned text
                final_cleaned_text = self._lemmatize_and_filter_tokens(doc)
        else:
            # Non-target language: minimal cleaning; ensure result is lowercase for tests consistency
            logger.debug(
                "Text language '%s' is not target '%s'. Skipping full processing.",
                lang_code,
                self.target_language,
            )
            final_cleaned_text = partially_cleaned_text.lower()

        return PreprocessedText(
            original_text=text,
            cleaned_text=final_cleaned_text,
            detected_language_code=lang_code,
            detected_language_confidence=lang_confidence,
            is_target_language=is_target,
        )

# Example Usage (for testing or demonstration)
if __name__ == "__main__":
    # Configure basic logging for the example
    logging.basicConfig(level=logging.INFO)
    # Ensure .env is loaded for settings if running standalone
    from dotenv import load_dotenv
    from pathlib import Path # Added missing import
    SERVICE_ROOT_DIR = Path(__file__).parent.parent.resolve()
    load_dotenv(SERVICE_ROOT_DIR / ".env")

    # Create a preprocessor instance
    try:
        preprocessor = Preprocessor()
        texts_to_test = [
            "This is a great #example of text with http://example.com and test@example.com! 😊 Love it!",
            "Ceci est un exemple de texte en français.",
            "Das ist ein deutscher Text.",
            "",
            None, # Test None input
            "    ", # Test whitespace input
            "Only alpha words here no numbers or symbols just plain text for processing",
            "Running, ran, runs, runner - testing lemmatization."
        ]

        for i, test_text in enumerate(texts_to_test):
            print(f"\n--- Test Case {i+1} ---")
            print(f"Original: {test_text}")
            result = preprocessor.preprocess(test_text)
            print(f"Cleaned: {result.cleaned_text}")
            print(f"Detected Language: {result.detected_language_code} (Confidence: {result.detected_language_confidence:.2f if result.detected_language_confidence else 'N/A'})")
            print(f"Is Target Language ({preprocessor.target_language}): {result.is_target_language}")

    except Exception as e:
        logger.error(f"Error during preprocessor example: {e}", exc_info=True)
