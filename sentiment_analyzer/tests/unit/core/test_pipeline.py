import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from sentiment_analyzer.core.pipeline import SentimentPipeline
from sentiment_analyzer.models.dtos import RawEventDTO, PreprocessedText, SentimentAnalysisOutput


@pytest.fixture
def mock_pipeline_components():
    """Fixture to mock all external components of the SentimentPipeline."""
    with (patch('sentiment_analyzer.core.pipeline.Preprocessor') as MockPreprocessor,
          patch('sentiment_analyzer.core.pipeline.SentimentAnalyzerComponent') as MockAnalyzer,
          patch('sentiment_analyzer.core.pipeline.ResultProcessor') as MockResultProcessor,
          patch('sentiment_analyzer.core.pipeline.fetch_and_claim_raw_events') as mock_fetch):


        # Setup mock instances
        preprocessor_instance = MockPreprocessor.return_value
        analyzer_instance = MockAnalyzer.return_value
        result_processor_instance = MockResultProcessor.return_value

        # Make processor methods async mocks
        result_processor_instance.save_sentiment_result = AsyncMock()
        result_processor_instance.update_sentiment_metrics = AsyncMock()
        result_processor_instance.move_to_dead_letter_queue = AsyncMock()

        yield {
            "preprocessor": preprocessor_instance,
            "analyzer": analyzer_instance,
            "result_processor": result_processor_instance,
            "fetch": mock_fetch
        }


@pytest.mark.asyncio
async def test_process_single_event_success(mock_pipeline_components, mocker):
    """Test the successful processing of a single event."""
    mocker.patch('sentiment_analyzer.config.settings.settings.EVENT_FETCH_BATCH_SIZE', 10)
    pipeline = SentimentPipeline()
    raw_event = RawEventDTO(id=1, content='{"text":"A good test"}', source='test', occurred_at='2023-01-01T00:00:00')

    # Mock component outputs for a successful run
    mock_pipeline_components['preprocessor'].preprocess.return_value = PreprocessedText(is_target_language=True, cleaned_text='good test')
    mock_pipeline_components['analyzer'].analyze.return_value = SentimentAnalysisOutput(label='positive', confidence=0.9)
    mock_pipeline_components['result_processor'].save_sentiment_result.return_value = MagicMock() # Represents a saved ORM object
    mock_pipeline_components['result_processor'].update_sentiment_metrics.return_value = True

    result = await pipeline.process_single_event(raw_event)

    assert result is True
    mock_pipeline_components['preprocessor'].preprocess.assert_called_once()
    mock_pipeline_components['analyzer'].analyze.assert_called_once()
    mock_pipeline_components['result_processor'].save_sentiment_result.assert_called_once()
    mock_pipeline_components['result_processor'].update_sentiment_metrics.assert_called_once()
    mock_pipeline_components['result_processor'].move_to_dead_letter_queue.assert_not_called()

@pytest.mark.asyncio
async def test_process_event_non_target_language(mock_pipeline_components, mocker):
    """Test that an event with a non-target language is skipped correctly."""
    mocker.patch('sentiment_analyzer.config.settings.settings.EVENT_FETCH_BATCH_SIZE', 10)
    pipeline = SentimentPipeline()
    raw_event = RawEventDTO(id=2, content='{"text":"un bon test"}', source='test', occurred_at='2023-01-01T00:00:00')

    # Mock preprocessor to return non-target language
    mock_pipeline_components['preprocessor'].preprocess.return_value = PreprocessedText(is_target_language=False, detected_language_code='fr')

    result = await pipeline.process_single_event(raw_event)

    assert result is True # Skipping is considered a successful outcome
    mock_pipeline_components['analyzer'].analyze.assert_not_called()
    mock_pipeline_components['result_processor'].save_sentiment_result.assert_not_called()

@pytest.mark.asyncio
async def test_process_event_empty_content(mock_pipeline_components, mocker):
    """Test that an event with empty content is moved to the DLQ."""
    mocker.patch('sentiment_analyzer.config.settings.settings.EVENT_FETCH_BATCH_SIZE', 10)
    pipeline = SentimentPipeline()
    raw_event = RawEventDTO(id=3, content='', source='test', occurred_at='2023-01-01T00:00:00')

    result = await pipeline.process_single_event(raw_event)

    assert result is False
    mock_pipeline_components['result_processor'].move_to_dead_letter_queue.assert_called_once()
    mock_pipeline_components['preprocessor'].preprocess.assert_not_called()

@pytest.mark.asyncio
async def test_process_event_save_result_fails(mock_pipeline_components, mocker):
    """Test that a failure to save the result moves the event to the DLQ."""
    mocker.patch('sentiment_analyzer.config.settings.settings.EVENT_FETCH_BATCH_SIZE', 10)
    pipeline = SentimentPipeline()
    raw_event = RawEventDTO(id=4, content='{"text":"A good test"}', source='test', occurred_at='2023-01-01T00:00:00')

    # Mock a failure in the result processor
    mock_pipeline_components['preprocessor'].preprocess.return_value = PreprocessedText(is_target_language=True, cleaned_text='good test')
    mock_pipeline_components['analyzer'].analyze.return_value = SentimentAnalysisOutput(label='positive', confidence=0.9)
    mock_pipeline_components['result_processor'].save_sentiment_result.return_value = None # Simulate save failure

    result = await pipeline.process_single_event(raw_event)

    assert result is False
    mock_pipeline_components['result_processor'].move_to_dead_letter_queue.assert_called_once()
    # Ensure metrics update is not attempted if saving fails
    mock_pipeline_components['result_processor'].update_sentiment_metrics.assert_not_called()

@pytest.mark.asyncio
async def test_run_pipeline_once(mock_pipeline_components, mocker):
    """Test the main pipeline runner for a batch of events."""
    mocker.patch('sentiment_analyzer.config.settings.settings.EVENT_FETCH_BATCH_SIZE', 10)
    pipeline = SentimentPipeline()
    # Mock fetch to return two events
    events = [
        RawEventDTO(id=1, content='{"text":"Event 1"}', source='test', occurred_at='2023-01-01T00:00:00'),
        RawEventDTO(id=2, content='{"text":"Event 2"}', source='test', occurred_at='2023-01-01T00:00:00')
    ]
    mock_pipeline_components['fetch'].return_value = events

    # Mock process_single_event to simplify the test
    with patch.object(pipeline, 'process_single_event', new_callable=AsyncMock) as mock_process_single:
        mock_process_single.return_value = True # Assume all processing succeeds
        
        fetched_count = await pipeline.run_pipeline_once()

        assert fetched_count == 2
        assert mock_process_single.call_count == 2

@pytest.mark.asyncio
async def test_run_pipeline_once_no_events(mock_pipeline_components, mocker):
    """Test the pipeline runner when no events are fetched."""
    mocker.patch('sentiment_analyzer.config.settings.settings.EVENT_FETCH_BATCH_SIZE', 10)
    pipeline = SentimentPipeline()
    mock_pipeline_components['fetch'].return_value = []

    with patch.object(pipeline, 'process_single_event', new_callable=AsyncMock) as mock_process_single:
        fetched_count = await pipeline.run_pipeline_once()

        assert fetched_count == 0
        mock_process_single.assert_not_called()
