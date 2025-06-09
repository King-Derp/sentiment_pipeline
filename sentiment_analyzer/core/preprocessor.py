"""
Preprocessor component for the Sentiment Analysis Service.

This component is responsible for cleaning and preparing raw text data for sentiment analysis,
including language detection, text normalization, lemmatization, and stop-word removal.
"""
import logging
import re
from typing import Optional

import emoji
import spacy
from langdetect import LangDetectException, detect_langs
from langdetect.detector_factory import DetectorFactory # For seeding
from spacy.tokens import Doc

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
        try:
            self.nlp = spacy.load(spacy_model_name)
            logger.info(f"Successfully loaded spaCy model: {spacy_model_name}")
        except OSError as e:
            logger.error(
                f"Spacy model '{spacy_model_name}' not found. "
                f"Please download it: python -m spacy download {spacy_model_name}. Error: {e}"
            )
            # Depending on application requirements, either raise the error to halt startup
            # or set self.nlp to None and handle it gracefully in the preprocess method.
            raise

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

    def _lemmatize_and_filter_tokens(self, doc: Doc) -> str:
        """
        Lemmatizes tokens, converts to lowercase, and removes stopwords, punctuation, and non-alphabetic tokens.
        """
        tokens = [
            token.lemma_.lower()
            for token in doc
            if not token.is_stop      # Remove stopwords
            and not token.is_punct   # Remove punctuation
            and not token.is_space   # Remove space tokens
            and token.is_alpha       # Keep only alphabetic tokens
        ]
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
                original_text=str(text), # Ensure original_text is a string
                cleaned_text="",
                detected_language_code="unknown",
                detected_language_confidence=None,
                is_target_language=False,
            )

        # Perform basic cleaning first (URLs, emojis, etc.)
        partially_cleaned_text = self._clean_text_basic(text)

        # Detect language from the partially cleaned text
        lang_code, lang_confidence = self.detect_language(partially_cleaned_text)
        is_target = lang_code == self.target_language

        final_cleaned_text = partially_cleaned_text
        if is_target:
            # If it's the target language, perform full spaCy processing
            # (lemmatization, stop-word removal, etc.)
            # Reason: spaCy processing is more resource-intensive and language-specific.
            doc = self.nlp(partially_cleaned_text) # Process the already partially cleaned text
            final_cleaned_text = self._lemmatize_and_filter_tokens(doc)
        else:
            # If not the target language, we might return the partially_cleaned_text
            # or an empty string, depending on downstream requirements.
            # For now, return the partially_cleaned_text.
            logger.debug(f"Text language '{lang_code}' is not target '{self.target_language}'. Skipping full spaCy processing.")
            # final_cleaned_text remains partially_cleaned_text

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
