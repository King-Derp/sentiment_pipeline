import json
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from reddit_scraper.reddit_scraper.cli_db import app

runner = CliRunner()


@patch('reddit_scraper.reddit_scraper.cli_db.get_connection')
@patch('reddit_scraper.reddit_scraper.cli_db.query_for_gaps')
@patch('reddit_scraper.reddit_scraper.cli_db.Config.from_files')
def test_find_gaps_command_success_stdout(mock_config_from_files, mock_query_for_gaps, mock_get_connection):
    """Tests the find-gaps command successfully prints JSON to stdout."""
    # Arrange
    mock_config = MagicMock()
    mock_config.postgres.enabled = True
    mock_config_from_files.return_value = mock_config
    mock_get_connection.return_value = MagicMock()

    fake_gaps = [
        {
            "subreddit": "testsubreddit",
            "gap_start": "2023-01-01T12:00:00",
            "gap_end": "2023-01-01T12:30:00",
            "gap_duration_seconds": 1800.0
        }
    ]
    mock_query_for_gaps.return_value = fake_gaps

    # Act
    result = runner.invoke(app, ["find-gaps"])

    # Assert
    assert result.exit_code == 0
    output_json = json.loads(result.stdout)
    assert len(output_json) == 1
    assert output_json[0]['subreddit'] == 'testsubreddit'
    assert output_json[0]['gap_duration_seconds'] == 1800.0
    assert output_json[0]['gap_start'] == '2023-01-01T12:00:00'


@patch('reddit_scraper.reddit_scraper.cli_db.get_connection')
@patch('reddit_scraper.reddit_scraper.cli_db.query_for_gaps')
@patch('reddit_scraper.reddit_scraper.cli_db.Config.from_files')
def test_find_gaps_command_success_file_output(mock_config_from_files, mock_query_for_gaps, mock_get_connection, tmp_path):
    """Tests the find-gaps command successfully writes JSON to a file."""
    # Arrange
    output_file = tmp_path / "gaps.json"
    mock_config = MagicMock()
    mock_config.postgres.enabled = True
    mock_config_from_files.return_value = mock_config
    mock_get_connection.return_value = MagicMock()

    fake_gaps = [
        {
            "subreddit": "testsubreddit2",
            "gap_start": "2023-01-02T10:00:00",
            "gap_end": "2023-01-02T10:15:00",
            "gap_duration_seconds": 900.0
        }
    ]
    mock_query_for_gaps.return_value = fake_gaps

    # Act
    result = runner.invoke(app, ["find-gaps", "--output-file", str(output_file)])

    # Assert
    assert result.exit_code == 0
    assert output_file.exists()

    with open(output_file, 'r') as f:
        data = json.load(f)
    
    assert len(data) == 1
    assert data[0]['subreddit'] == 'testsubreddit2'
    assert data[0]['gap_duration_seconds'] == 900.0

