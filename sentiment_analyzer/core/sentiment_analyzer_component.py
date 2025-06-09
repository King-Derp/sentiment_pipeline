"""
Sentiment Analyzer component for the Sentiment Analysis Service.

This component uses a pre-trained Hugging Face Transformers model (e.g., FinBERT)
to perform sentiment analysis on preprocessed text.
"""
import logging
from typing import Dict

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, PreTrainedModel, PreTrainedTokenizerBase

from sentiment_analyzer.config.settings import settings
from sentiment_analyzer.models.dtos import SentimentAnalysisOutput

logger = logging.getLogger(__name__)

class SentimentAnalyzerComponent:
    """
    Handles sentiment analysis using a Hugging Face Transformers model.
    """

    def __init__(
        self,
        model_name: str = settings.FINBERT_MODEL_NAME,
        use_gpu_if_available: bool = settings.USE_GPU_IF_AVAILABLE,
    ):
        """
        Initializes the SentimentAnalyzerComponent, loading the model and tokenizer.

        Args:
            model_name (str): The name or path of the Hugging Face model to load.
            use_gpu_if_available (bool): Whether to use GPU if available.
        """
        self.model_name = model_name
        self.device = self._get_device(use_gpu_if_available)
        
        logger.info(f"Initializing SentimentAnalyzerComponent with model: {self.model_name} on device: {self.device}")

        try:
            self.tokenizer: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(self.model_name)
            self.model: PreTrainedModel = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()  # Set model to evaluation mode
            logger.info(f"Successfully loaded model '{self.model_name}' and tokenizer.")
        except Exception as e:
            logger.error(f"Error loading model or tokenizer '{self.model_name}': {e}", exc_info=True)
            # Depending on application requirements, either raise to halt or handle gracefully.
            raise

    def _get_device(self, use_gpu_if_available: bool) -> torch.device:
        """
        Determines the device (CPU or GPU) to use for PyTorch operations.
        """
        if use_gpu_if_available and torch.cuda.is_available():
            logger.info("CUDA is available. Using GPU for sentiment analysis.")
            return torch.device("cuda")
        elif use_gpu_if_available:
            logger.warning("CUDA is not available, but USE_GPU_IF_AVAILABLE is True. Falling back to CPU.")
        else:
            logger.info("Using CPU for sentiment analysis.")
        return torch.device("cpu")

    def analyze(self, text: str) -> SentimentAnalysisOutput:
        """
        Performs sentiment analysis on the given text.

        Args:
            text (str): The preprocessed text to analyze.

        Returns:
            SentimentAnalysisOutput: A DTO containing the sentiment label, confidence,
                                     all class scores, and model version.
        """
        if not isinstance(text, str) or not text.strip():
            logger.warning("Received empty or non-string input for sentiment analysis. Returning neutral default.")
            # Return a default neutral sentiment or handle as an error based on requirements
            return SentimentAnalysisOutput(
                label="neutral", 
                confidence=1.0, 
                scores={"positive": 0.0, "negative": 0.0, "neutral": 1.0},
                model_version=self.model_name
            )

        try:
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad(): # Disable gradient calculations for inference
                outputs = self.model(**inputs)
            
            logits = outputs.logits
            probabilities = torch.nn.functional.softmax(logits, dim=-1)
            
            # Get the ID to label mapping from the model's config
            # FinBERT (ProsusAI/finbert) labels: 0: positive, 1: negative, 2: neutral
            id2label = self.model.config.id2label
            
            predicted_class_id = torch.argmax(probabilities, dim=-1).item()
            predicted_label = id2label[predicted_class_id]
            confidence = probabilities[0, predicted_class_id].item()
            
            all_scores: Dict[str, float] = {id2label[i]: probabilities[0, i].item() for i in range(probabilities.shape[1])}

            return SentimentAnalysisOutput(
                label=predicted_label,
                confidence=confidence,
                scores=all_scores,
                model_version=self.model_name
            )

        except Exception as e:
            logger.error(f"Error during sentiment analysis for text '{text[:100]}...': {e}", exc_info=True)
            # Fallback or re-raise based on error handling strategy
            # For now, return a default neutral sentiment on error
            return SentimentAnalysisOutput(
                label="neutral", 
                confidence=0.0, # Indicate low confidence due to error
                scores={"positive": 0.0, "negative": 0.0, "neutral": 0.0},
                model_version=self.model_name
            )

# Example Usage (for testing or demonstration)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Ensure .env is loaded for settings if running standalone
    from dotenv import load_dotenv
    from pathlib import Path
    SERVICE_ROOT_DIR = Path(__file__).parent.parent.resolve()
    load_dotenv(SERVICE_ROOT_DIR / ".env")

    try:
        analyzer = SentimentAnalyzerComponent()
        
        texts_to_analyze = [
            "This company is performing exceptionally well, with strong profits and growth.",
            "The market is crashing, and stock prices are plummeting.",
            "The report was largely uneventful and provided no new insights.",
            "I am feeling very optimistic about the future prospects.",
            "There are significant risks associated with this investment.",
            "", # Empty string test
            "         ", # Whitespace test
        ]

        for i, test_text in enumerate(texts_to_analyze):
            print(f"\n--- Test Case {i+1} ---")
            print(f"Original Text: {test_text}")
            result = analyzer.analyze(test_text)
            print(f"  Label: {result.label}")
            print(f"  Confidence: {result.confidence:.4f}")
            print(f"  Scores: {result.scores}")
            print(f"  Model: {result.model_version}")

    except Exception as e:
        logger.error(f"Error during SentimentAnalyzerComponent example: {e}", exc_info=True)
