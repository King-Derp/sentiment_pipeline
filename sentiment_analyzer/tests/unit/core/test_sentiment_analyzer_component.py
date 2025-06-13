import pytest
import torch
from unittest.mock import patch, MagicMock

from sentiment_analyzer.core.sentiment_analyzer_component import SentimentAnalyzerComponent
from sentiment_analyzer.models.dtos import SentimentAnalysisOutput

# Mock the entire transformers library to avoid real model loading
@pytest.fixture
def mock_transformers():
    """Fixture to mock Hugging Face transformers Auto* classes."""
    with (patch('sentiment_analyzer.core.sentiment_analyzer_component.AutoTokenizer') as mock_tokenizer,
          patch('sentiment_analyzer.core.sentiment_analyzer_component.AutoModelForSequenceClassification') as mock_model):
        
        # Mock tokenizer instance
        tokenizer_instance = MagicMock()
        tokenizer_instance.return_value = {"input_ids": torch.tensor([[1, 2, 3]]), "attention_mask": torch.tensor([[1, 1, 1]])}
        mock_tokenizer.from_pretrained.return_value = tokenizer_instance

        # Mock model instance
        model_instance = MagicMock()
        model_instance.config.id2label = {0: 'positive', 1: 'negative', 2: 'neutral'}
        # Simulate model output (logits)
        model_output = MagicMock()
        model_output.logits = torch.tensor([[0.1, 0.2, 0.7]]) # Corresponds to 'neutral' being highest
        model_instance.return_value = model_output
        mock_model.from_pretrained.return_value = model_instance
        
        yield mock_tokenizer, mock_model


def test_analyzer_initialization(mock_transformers):
    """Test that the SentimentAnalyzerComponent initializes correctly."""
    mock_tokenizer, mock_model = mock_transformers
    try:
        analyzer = SentimentAnalyzerComponent(model_name='finbert-test')
        assert analyzer is not None
        assert analyzer.model_name == 'finbert-test'
        mock_tokenizer.from_pretrained.assert_called_once_with('finbert-test')
        mock_model.from_pretrained.assert_called_once_with('finbert-test')
        analyzer.model.to.assert_called_once() # Check if model was moved to a device
    except Exception as e:
        pytest.fail(f"SentimentAnalyzerComponent initialization failed: {e}")

@patch('torch.cuda.is_available')
def test_get_device_selection(mock_cuda_available, mock_transformers):
    """Test the device selection logic for CPU and GPU."""
    # Test GPU selection
    mock_cuda_available.return_value = True
    analyzer_gpu = SentimentAnalyzerComponent(use_gpu_if_available=True)
    assert str(analyzer_gpu.device) == 'cuda'

    # Test CPU fallback
    mock_cuda_available.return_value = False
    analyzer_cpu_fallback = SentimentAnalyzerComponent(use_gpu_if_available=True)
    assert str(analyzer_cpu_fallback.device) == 'cpu'

    # Test CPU explicit selection
    analyzer_cpu = SentimentAnalyzerComponent(use_gpu_if_available=False)
    assert str(analyzer_cpu.device) == 'cpu'

def test_analyze_normal_text(mock_transformers):
    """Test sentiment analysis on a normal string of text."""
    analyzer = SentimentAnalyzerComponent()
    result = analyzer.analyze("This is a test sentence.")

    assert isinstance(result, SentimentAnalysisOutput)
    assert result.label == 'neutral' # Based on mock logits
    # Check that confidence is a float between 0 and 1
    assert isinstance(result.confidence, float)
    assert 0 <= result.confidence <= 1
    assert result.model_version == 'ProsusAI/finbert' # Default model name
    assert 'positive' in result.scores
    assert 'negative' in result.scores
    assert 'neutral' in result.scores

def test_analyze_empty_input(mock_transformers):
    """Test that empty or whitespace-only input returns a default neutral sentiment."""
    analyzer = SentimentAnalyzerComponent()

    # Test empty string
    result_empty = analyzer.analyze("")
    assert result_empty.label == 'neutral'
    assert result_empty.confidence == 1.0

    # Test whitespace string
    result_whitespace = analyzer.analyze("   \t\n  ")
    assert result_whitespace.label == 'neutral'
    assert result_whitespace.confidence == 1.0


def test_analyze_inference_error(mock_transformers):
    """Test fallback behavior when an exception occurs during model inference."""
    mock_tokenizer, mock_model = mock_transformers
    
    # Configure the mocked model to raise an error during inference
    mock_model.from_pretrained.return_value.side_effect = Exception("Inference failed")

    analyzer = SentimentAnalyzerComponent()
    result = analyzer.analyze("This will cause an error.")

    assert isinstance(result, SentimentAnalysisOutput)
    assert result.label == 'neutral'
    assert result.confidence == 0.0 # Confidence is 0 to indicate an error
    assert result.scores == {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
