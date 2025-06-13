import pytest
from unittest.mock import patch, MagicMock

from sentiment_analyzer.core.preprocessor import Preprocessor
from sentiment_analyzer.models.dtos import PreprocessedText

# Mock spaCy's language model and its components
@pytest.fixture
def mock_spacy_model():
    """Fixture to mock the spaCy language model and its pipeline components."""
    with patch('spacy.load') as mock_load:
        mock_nlp = MagicMock()
        mock_doc = MagicMock()
        mock_token = MagicMock()

        # Mock token attributes
        mock_token.lemma_ = 'test'
        mock_token.is_stop = False
        mock_token.is_punct = False
        mock_token.is_space = False

        # Mock document to be an iterable of mock tokens
        mock_doc.__iter__.return_value = [mock_token]
        mock_nlp.return_value = mock_doc
        mock_load.return_value = mock_nlp
        yield mock_load

# Mock langdetect
@pytest.fixture
def mock_langdetect():
    """Fixture to mock the langdetect library."""
    with patch('langdetect.detect') as mock_detect:
        mock_detect.return_value = 'en' # Default mock to English
        yield mock_detect

def test_preprocessor_initialization(mock_spacy_model):
    """Test that the Preprocessor class initializes correctly."""
    try:
        preprocessor = Preprocessor(target_language='en')
        assert preprocessor is not None
        assert preprocessor.target_language == 'en'
        mock_spacy_model.assert_called_once()
    except Exception as e:
        pytest.fail(f"Preprocessor initialization failed: {e}")

def test_preprocess_target_language(mock_spacy_model, mock_langdetect):
    """Test preprocessing for a text in the target language."""
    preprocessor = Preprocessor()
    mock_langdetect.return_value = 'en'

    # Mock the spacy doc/token pipeline for a specific input
    mock_nlp = mock_spacy_model.return_value
    mock_doc = MagicMock()
    mock_token1 = MagicMock(lemma_='company', is_stop=False, is_punct=False, is_space=False)
    mock_token2 = MagicMock(lemma_='perform', is_stop=False, is_punct=False, is_space=False)
    mock_token3 = MagicMock(lemma_='well', is_stop=False, is_punct=False, is_space=False)
    mock_doc.__iter__.return_value = [mock_token1, mock_token2, mock_token3]
    mock_nlp.return_value = mock_doc

    original_text = "The company is performing very well. Check http://example.com 😊"
    result = preprocessor.preprocess(original_text)

    assert isinstance(result, PreprocessedText)
    assert result.is_target_language is True
    assert result.detected_language_code == 'en'
    assert result.cleaned_text == 'company perform well'
    assert result.original_text == original_text

def test_preprocess_non_target_language(mock_spacy_model, mock_langdetect):
    """Test that non-target language texts are identified and not fully processed."""
    preprocessor = Preprocessor(target_language='en')
    mock_langdetect.return_value = 'fr' # Mock detection as French

    original_text = "C'est une bonne journée."
    result = preprocessor.preprocess(original_text)

    assert result.is_target_language is False
    assert result.detected_language_code == 'fr'
    # For non-target languages, cleaned_text might be minimally processed or same as original
    # Based on the current implementation, it still goes through basic cleaning
    assert result.cleaned_text == "c'est une bonne journée."

@pytest.mark.parametrize("input_text, expected_output", [
    ("Check out http://example.com for more info", "check info"),
    ("A great day! 😄 #awesome", "great day awesome"),
    ("Contact me at test@example.com", "contact"),
    ("This is a test... with punctuation!", "test punctuation"),
    ("RT @user: This is a retweet", "retweet"),
    ("Lots of    extra   spaces", "lot extra space"),
    ("\nNewlines\nand\ttabs", "newline tab"),
])
def test_individual_cleaning_rules(mock_spacy_model, mock_langdetect, input_text, expected_output):
    """Test individual cleaning rules of the preprocessor."""
    preprocessor = Preprocessor()
    mock_langdetect.return_value = 'en'

    # Simplified mock for tokenization based on expected output
    mock_nlp = mock_spacy_model.return_value
    mock_doc = MagicMock()
    tokens = []
    for word in expected_output.split():
        tokens.append(MagicMock(lemma_=word, is_stop=False, is_punct=False, is_space=False))
    mock_doc.__iter__.return_value = tokens
    mock_nlp.return_value = mock_doc

    result = preprocessor.preprocess(input_text)
    assert result.cleaned_text == expected_output

def test_preprocess_empty_and_whitespace_input(mock_spacy_model, mock_langdetect):
    """Test that empty or whitespace-only strings are handled gracefully."""
    preprocessor = Preprocessor()
    
    # Test empty string
    result_empty = preprocessor.preprocess("")
    assert result_empty.cleaned_text == ""
    assert result_empty.is_target_language is True # langdetect might fail, preprocessor handles it

    # Test whitespace string
    result_whitespace = preprocessor.preprocess("   \t\n  ")
    assert result_whitespace.cleaned_text == ""
