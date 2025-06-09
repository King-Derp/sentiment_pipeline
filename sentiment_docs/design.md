# Sentiment Analysis Service Design

**Version:** 1.2  
**Last Updated:** 2025-06-09  
**Status:** Draft

> **Note:** This service consumes raw events from the `raw_events` hypertable, each conforming to the `RawEventDTO` / `RawEventORM` contract (see `models/raw_event.py`). Any changes to that contract must be mirrored here.

---

## Table of Contents
- [Sentiment Analysis Service Design](#sentiment-analysis-service-design)
  - [Table of Contents](#table-of-contents)
  - [1. Overview](#1-overview)
  - [2. Architecture](#2-architecture)
    - [2.1 High-Level Design](#21-high-level-design)
    - [2.2 Component Diagram (Annotated)](#22-component-diagram-annotated)
    - [2.3 Data Flow](#23-data-flow)
  - [3. Data Model](#3-data-model)
    - [3.1 Input Data (`raw_events`)](#31-input-data-raw_events)
      - [Notes:](#notes)
    - [3.2 Output Data](#32-output-data)
      - [3.2.1 `sentiment_results` Table](#321-sentiment_results-table)
      - [3.2.2 `sentiment_metrics` Table](#322-sentiment_metrics-table)
  - [4. Components](#4-components)
    - [4.1 Data Fetcher](#41-data-fetcher)
    - [4.2 Preprocessor](#42-preprocessor)
    - [4.3 Sentiment Analyzer](#43-sentiment-analyzer)
    - [4.4 Result Processor](#44-result-processor)
    - [4.5 API Service](#45-api-service)
      - [4.5.1 Endpoints](#451-endpoints)
  - [5. APIs](#5-apis)
  - [6. Configuration](#6-configuration)
  - [7. Error Handling \& Logging](#7-error-handling--logging)
  - [8. Performance Considerations (MVP)](#8-performance-considerations-mvp)
  - [9. Testing Strategy](#9-testing-strategy)
    - [9.1 Unit Tests](#91-unit-tests)
    - [9.2 Integration Tests](#92-integration-tests)
    - [9.3 Performance Tests (Optional, Later)](#93-performance-tests-optional-later)
  - [10. Deployment](#10-deployment)
  - [11. Future Enhancements](#11-future-enhancements)

---

## 1. Overview

The **Sentiment Analysis Service** reads raw text events from the `raw_events` hypertable (each row must conform to the `RawEventDTO` / `RawEventORM` contract in `models/raw_event.py`), performs sentiment analysis, and stores both per-event results and time‐bucketed aggregates for dashboards or downstream consumers.  

- **Source of data**: `raw_events` (TimescaleDB hypertable)  
- **Outputs**:  
  1. `sentiment_results` (hypertable) ─ one row per event with sentiment score & label  
  2. `sentiment_metrics` (hypertable) ─ aggregated metrics (count, avg_score) by time bucket  
  3. `dead_letter_events` (table) ─ stores events that failed processing after attempts, for manual inspection and potential reprocessing.  

---

## 2. Architecture

### 2.1 High-Level Design

The system follows a modular, event-driven pipeline, orchestrated by the `SentimentPipeline` component. The key processing stages are:

1. **Data Fetcher**  
   - Claims unprocessed rows from `raw_events` based on their `processing_status` (e.g., 'unprocessed').
   - Atomically updates status to 'claimed' to prevent multiple workers processing the same event.  

2. **Preprocessor**  
   - Cleans text (removes URLs, special characters, emojis)  
   - (Optionally) filters by language, normalizes tokens  

3. **Sentiment Analyzer**  
   - Uses a model (VADER, FinBERT, or custom BERT) to compute  
     - `sentiment_score` (float)  
     - `sentiment_label` (str)  
     - `confidence` (float)  
     - `model_version` (str)  

4. **Result Processor**  
   - Inserts rows into `sentiment_results` (per event)  
   - Immediately updates `sentiment_metrics` (time‐bucketed aggregates) using `INSERT … ON CONFLICT DO UPDATE`  

5. **API Service**  
   - Exposes RESTful endpoints for on‐demand sentiment analysis, querying stored results, and retrieving aggregated metrics  

Multiple scraper instances (e.g., one for r/finance, one for r/economics) will write to the same `raw_events` hypertable. The Data Fetcher component must handle that concurrency gracefully by using a `processed` boolean (or `status` enum) and atomic “claim‐and‐return” queries.

---

### 2.2 Component Diagram (Annotated)

```mermaid
graph TD
  A[Data Fetcher]
  B[Preprocessor]
  C[Sentiment Analyzer]
  D[Result Processor]
  subgraph TimescaleDB
    direction TB
    R[(raw_events)]
    SR[(sentiment_results)]
    SM[(sentiment_metrics)]
  end
  A --> B
  B --> C
  C --> D
  D --> SR
  D --> SM
  F[API Service] --> SM
  F --> SR
  G[External Clients] --> F
```

- **TimescaleDB Node** shows three distinct hypertables:  
  - **raw_events** (read‐only for this service)  
  - **sentiment_results** (this service writes per‐event results)  
  - **sentiment_metrics** (time‐bucketed aggregates, updated in real time)  

---

### 2.3 Data Flow

1. **Claim New Events**  
   - Every X seconds (configurable, default `PIPELINE_RUN_INTERVAL_SECONDS`), the `SentimentPipeline` triggers the `DataFetcher` component, which runs:
     ```sql
     UPDATE raw_events
     SET processing_status = 'claimed', claimed_at = NOW()
     WHERE processing_status = 'unprocessed'
     ORDER BY occurred_at ASC
     LIMIT :batch_size
     RETURNING *;
     ```
   - This `UPDATE … RETURNING` is in a single transaction, guaranteeing no two fetchers pick the same rows. The `processing_status` field is an enum (e.g., `unprocessed`, `claimed`, `processed`, `failed`).  

2. **Preprocessing**  
   - For each fetched event:  
     - Extract `content` from the `RawEventDTO` as raw text.  
     - **Text Cleaning Pipeline (using spaCy `en_core_web_lg` and other libraries):**
       - Remove URLs, email addresses, mentions (e.g., @user), and hashtags.
       - Convert emojis to their textual descriptions (e.g., using the `emoji` library).
       - Normalize text: lowercasing, remove extra whitespace.
       - Perform lemmatization.
       - Remove stop-words.
     - **Language Detection:** Detect language using `langdetect`. If the detected language is not the `PREPROCESSOR_TARGET_LANGUAGE` (e.g., "en"), the event may be skipped or handled differently. The output includes `cleaned_text`, `detected_language_code`, and `is_target_language`.  

3. **Sentiment Analysis**  
   - Pass cleaned text to chosen model:  
     - **VADER** (rule‐based) or  
     - **FinBERT** (`yiyanghkust/finbert‐tone`) or  
     - **Custom BERT** (fine‐tuned on in‐house data)  
   - Produce a `SentimentAnalysisOutput` DTO containing:
       - `label` (str): The predicted sentiment label (e.g., "positive", "neutral", "negative").
       - `confidence` (float): The confidence score for the predicted `label`.
       - `scores` (dict): A dictionary of scores for all sentiment classes (e.g., `{"positive": 0.85, "neutral": 0.05, "negative": 0.10}`).
       - `model_version` (str): Identifier for the sentiment model used.
   - Example (FinBERT): `label` = "positive", `confidence` = 0.85, `scores` = `{"positive": 0.85, "neutral": 0.05, "negative": 0.10}`.  

4. **Result Storage**  
   The `ResultProcessor` component handles saving data to `sentiment_results` and updating `sentiment_metrics`.

   - **Insert into `sentiment_results`:**  
     For each successfully analyzed event, a new record is inserted. Details from `RawEventDTO`, `PreprocessedText`, and `SentimentAnalysisOutput` are mapped to `SentimentResultORM` fields.
     ```sql
     -- Conceptual SQL, actual implementation uses SQLAlchemy ORM
     INSERT INTO sentiment_results (
       id, raw_event_id, processed_at, model_version, 
       sentiment_label, sentiment_confidence, sentiment_scores_json, 
       cleaned_text, detected_language_code, is_target_language
     ) VALUES (
       gen_random_uuid(), :raw_event_id, NOW(), :model_version, 
       :label, :confidence, :scores_json, 
       :cleaned_text, :lang_code, :is_target_lang
     );
     ```

   - **Real‐Time Metrics Update in `sentiment_metrics`:**  
     Metrics are updated using an `INSERT ... ON CONFLICT DO UPDATE` strategy. For each processed event, relevant metrics (like event count and sum of scores for the determined label) are incremented.

     Example for incrementing `event_count` for a given label:
     ```sql
     -- Conceptual SQL, actual implementation uses SQLAlchemy ORM
     INSERT INTO sentiment_metrics (
       id, metric_timestamp, raw_event_source, sentiment_label, 
       model_version, metric_name, metric_value
     )
     VALUES (
       gen_random_uuid(), time_bucket_gapfill('1 hour', :processed_at), -- or similar time bucketing
       :raw_event_source, 
       :sentiment_label, 
       :model_version, 
       'event_count', 
       1 -- Increment by 1
     )
     ON CONFLICT (metric_timestamp, raw_event_source, sentiment_label, model_version, metric_name)
     DO UPDATE SET
       metric_value = sentiment_metrics.metric_value + EXCLUDED.metric_value;
     ```

     Example for incrementing sum of confidence scores for a given label (if tracking average confidence):
     ```sql
     -- Conceptual SQL, actual implementation uses SQLAlchemy ORM
     INSERT INTO sentiment_metrics (
       id, metric_timestamp, raw_event_source, sentiment_label, 
       model_version, metric_name, metric_value
     )
     VALUES (
       gen_random_uuid(), time_bucket_gapfill('1 hour', :processed_at), 
       :raw_event_source, 
       :sentiment_label, 
       :model_version, 
       'confidence_sum', 
       :sentiment_confidence -- Add current event's confidence
     )
     ON CONFLICT (metric_timestamp, raw_event_source, sentiment_label, model_version, metric_name)
     DO UPDATE SET
       metric_value = sentiment_metrics.metric_value + EXCLUDED.metric_value;
     ```
   - This approach allows for various metrics to be tracked. Average scores or confidences can be calculated at query time by dividing the sum-metric by the 'event_count' for the same aggregation group.

5. **API Exposure**  
   - Clients call `/api/v1/sentiment/analyze?text=…` for on‐the‐fly analysis.  
   - Clients query `/api/v1/sentiment/events?…` to retrieve stored results.  
   - Clients query `/api/v1/sentiment/metrics?…` to get aggregated metrics for dashboards.  

---

## 3. Data Model

### 3.1 Input Data (`raw_events`)

This service expects each row in `raw_events` to match `RawEventDTO` / `RawEventORM` (see `models/raw_event.py`). Relevant fields:

| Column         | Type           | Notes                                               |
|---------------|----------------|-----------------------------------------------------|
| `id`          | TEXT / UUID    | Unique identifier (NOT NULL)                         |
| `occurred_at` | TIMESTAMPTZ   | When the event happened (NOT NULL)                  |
| `source`      | TEXT           | e.g. `"reddit"` (NOT NULL)                           |
| `source_id`   | TEXT           | e.g. `"r/wallstreetbets"` (NOT NULL, or `'unknown'`) |
| `event_type`  | TEXT           | e.g. `"post_created"`, `"comment_created"`           |
| `payload`     | JSONB          | Contains fields like `title`, `selftext`, `author`   |
| `processed`   | BOOLEAN        | Default `FALSE`; toggled to `TRUE` when claimed      |
| `processed_at`| TIMESTAMPTZ    | When sentiment analysis was completed (NULL until processed) |

#### Notes:
- The service reads **only** from `raw_events`. It does **not** modify the original text or delete rows (beyond marking `processed = TRUE` and setting `processed_at` timestamp).
- A specialized index `ix_raw_events_processed_occurred_at` on `(processed, occurred_at)` with `WHERE processed = FALSE` optimizes fetching unprocessed events.
- Ensure that if `payload` changes (e.g. you add `payload.text_language`), you update `RawEventDTO` first, then this service’s code.  

---

### 3.2 Output Data

#### 3.2.1 `sentiment_results` Table

- **Purpose**: Stores individual sentiment analysis results for each processed event, linking back to the original raw event.
- **Hypertable**: Yes, partitioned by `processed_at`.
- **ORM Model**: `SentimentResultORM`
- **Key Columns**:
  - `id` (UUID, Primary Key)
- **Core Data Columns**:
  - `raw_event_id` (UUID, Foreign Key to `raw_events.id`, Indexed) - Links to the original event.
  - `processed_at` (TIMESTAMPTZ, default NOW(), Indexed) - Timestamp of when the sentiment analysis was completed.
  - `model_version` (TEXT) - Version of the sentiment model used.
  - `sentiment_label` (TEXT) - The final determined sentiment (e.g., 'positive', 'negative', 'neutral').
  - `sentiment_confidence` (FLOAT) - Confidence score for the `sentiment_label`.
  - `sentiment_scores_json` (JSONB) - JSON object storing all class scores from the model (e.g., `{"positive": 0.8, "neutral": 0.15, "negative": 0.05}`).
  - `cleaned_text` (TEXT) - The preprocessed text that was analyzed.
  - `detected_language_code` (TEXT, nullable) - Detected language code (e.g., 'en', 'es').
  - `is_target_language` (BOOLEAN) - Flag indicating if the detected language was the target language for analysis.

#### 3.2.2 `sentiment_metrics` Table

- **Purpose**: Stores aggregated sentiment metrics (like counts, sums of scores) over time buckets, per source, label, and model.
- **Hypertable**: Yes, partitioned by `metric_timestamp`.
- **ORM Model**: `SentimentMetricORM`
- **Key Columns** (Part of composite unique constraint; `id` is the Primary Key):
  - `id` (UUID, Primary Key)
  - `metric_timestamp` (TIMESTAMPTZ) - The start of the time bucket (e.g., top of the hour).
  - `raw_event_source` (TEXT) - Source of the original raw events (e.g., 'reddit', 'twitter').
  - `sentiment_label` (TEXT) - The sentiment label being aggregated.
  - `model_version` (TEXT) - Version of the sentiment model used for the results being aggregated.
  - `metric_name` (TEXT) - Name of the specific metric being stored (e.g., 'event_count', 'confidence_sum').
- **Metric Value Column**:
  - `metric_value` (FLOAT) - The value of the specified `metric_name` for this aggregation group.
- **Notes**:
  - The combination of `(metric_timestamp, raw_event_source, sentiment_label, model_version, metric_name)` should be unique to ensure each specific metric for an aggregation group is stored once per time bucket.
  - This structure allows for flexible aggregation. For example, to get the total count of positive sentiments for 'reddit' in an hour, you'd query for `metric_name = 'event_count'` and `sentiment_label = 'positive'`. Average scores or confidences would be calculated at query time by dividing a sum-metric (e.g., 'confidence_sum') by an 'event_count' metric for the same aggregation group (timestamp, source, label, model_version).
- **Granularity of Buckets:**  
  - By default, at write‐time we use `time_bucket('1h', occurred_at)`.  
  - If you later want daily aggregates, you can run a backfill query like:

    ```sql
    INSERT INTO sentiment_metrics (time_bucket, source, source_id, label, count, avg_score)
    SELECT
      time_bucket('1d', occurred_at)   AS bucket,
      source,
      source_id,
      sentiment_label,
      COUNT(*) AS count,
      AVG(sentiment_score) AS avg_score
    FROM sentiment_results
    WHERE occurred_at BETWEEN :start_date AND :end_date
    GROUP BY bucket, source, source_id, sentiment_label
    ON CONFLICT (time_bucket, source, source_id, label)
    DO UPDATE SET
      count = sentiment_metrics.count + EXCLUDED.count,
      avg_score = (
        (sentiment_metrics.avg_score * sentiment_metrics.count)
        + (EXCLUDED.avg_score * EXCLUDED.count)
      ) / (sentiment_metrics.count + EXCLUDED.count);
    ```

- **Handling New Labels:**  
  - If a sentiment model introduces a brand‐new label (e.g. `"very_positive"`), the first `INSERT … ON CONFLICT …` simply creates a new row for `(time_bucket, source, source_id, 'very_positive')`. Future events with `"very_positive"` will update that same row automatically—no schema change needed.

#### 3.2.3 `dead_letter_events` Table

- **Purpose**: Stores raw events that failed processing in the sentiment analysis pipeline after all attempts or due to critical errors, allowing for later inspection and potential reprocessing.
- **Hypertable**: Yes, partitioned by `failed_at`.
- **ORM Model**: `DeadLetterEventORM`
- **Key Columns**:
  - `id` (UUID, Primary Key)
- **Core Data Columns**:
  - `raw_event_id` (UUID, nullable) - Foreign key to `raw_events.id` if the failure occurred after the raw event was identified. This can be NULL if the event data itself was malformed before an ID could be parsed.
  - `raw_event_content` (JSONB, nullable) - The content of the raw event, if available, stored as JSON. This could be the original `RawEventDTO` or parts of it.
  - `failed_at` (TIMESTAMPTZ, default NOW(), Indexed) - Timestamp of when the event processing failed and was moved to this table. This is the hypertable partitioning key.
  - `error_message` (TEXT, nullable) - Description of the error that caused the failure.
  - `failed_stage` (TEXT, nullable) - The stage in the pipeline where the failure occurred (e.g., 'preprocessing', 'sentiment_analysis', 'result_saving', 'data_fetching').
  - `traceback` (TEXT, nullable) - Full Python traceback of the exception, if available and captured.
  - `retry_count` (INTEGER, default 0) - Number of times processing has been attempted for this event (can be incremented by a future retry mechanism).
- **Notes**:
  - This table provides a comprehensive log for events that could not be processed, aiding in debugging pipeline issues and understanding data quality problems.
  - The `raw_event_content` allows for full inspection of the problematic data.


### 3.3 TimescaleDB Specific Considerations

#### Hypertable Foreign Key Constraints: Hypertable-to-Hypertable Limitation

TimescaleDB, as of the current understanding and documentation, **does not support foreign key constraints where both the referencing table and the referenced table are hypertables.**

For example, a direct foreign key from `sentiment_results` (hypertable) to `raw_events` (hypertable) cannot be established at the database level.

**Implications for this Service:**
- The relationship between `sentiment_results.event_id, sentiment_results.occurred_at` and `raw_events.id, raw_events.occurred_at` is a **logical relationship**.
- Referential integrity (ensuring that `event_id` in `sentiment_results` corresponds to a valid `id` in `raw_events`) must be managed at the **application level**.
- This can involve:
    - Ensuring data consistency during the write process within the sentiment analysis service.
    - Periodic checks or cleanup jobs if strict integrity is required over time, though this is not planned for the initial implementation given the single-writer nature for `sentiment_results`.

This limitation means that while the ORM models and migration scripts will define columns like `event_id` with the correct data type (`BIGINT`) to match the intended referenced column in `raw_events`, the database itself will not enforce this link with a foreign key constraint.

---

## 4. Components

### 4.1 `SentimentPipeline` (Orchestrator)

- **Purpose**: Coordinates the end-to-end sentiment analysis workflow for batches of events.
- **Key Responsibilities**:
  - Manages the main processing loop, running at a configurable interval (`PIPELINE_RUN_INTERVAL_SECONDS`).
  - Invokes the `DataFetcher` to retrieve a batch of raw events.
  - For each event, orchestrates the sequence: `Preprocessor` -> `SentimentAnalyzerComponent` -> `ResultProcessor`.
  - Uses `asyncio.gather` for concurrent processing of events within a batch.
  - Implements top-level error handling for individual event processing, including routing failed events to the `dead_letter_events` table via the `ResultProcessor`.
  - Logs overall batch processing statistics (e.g., number of events fetched, processed successfully, failed).
- **Implementation**: `sentiment_analyzer.core.pipeline.SentimentPipeline`

### 4.2 Data Fetcher

**Responsibility:** Claim unprocessed rows from `raw_events`, mark them as claimed (`processed = TRUE`), and hand them to the preprocessing pipeline.

- **Key Steps (in Python/Pseudocode):**

  ```python
  async def fetch_unprocessed_batch(db, batch_size: int):
      # 1. Try to claim up to batch_size rows
      rows = await db.fetch_all(
          """
          UPDATE raw_events
          SET processed = TRUE
          WHERE processed = FALSE
          ORDER BY occurred_at ASC
          LIMIT $1
          RETURNING id, occurred_at, source, source_id, payload;
          """,
          batch_size
      )
      return rows  # List[RawEventDTO]
  ```

- **Features:**  
  1. **Polling Interval:** Configurable—default every 30 seconds (`config.processing.poll_interval_seconds`).  
  2. **Atomic “Claim + Return”:** The single `UPDATE … RETURNING` inside a transaction prevents overlap across multiple fetcher instances.  
  3. **Batch Size:** Configurable (`config.processing.batch_size`, default 100).  
  4. **Dead‐Letter Handling:** If a row fails downstream (e.g. unparseable text), either:  
     - Set `processed = FALSE` again so it can be retried, or  
     - Insert into a `dead_letter_events` table for manual inspection.  
  5. **Retry / Backoff:** On database errors or timeouts, apply exponential backoff up to `max_retries` before alerting.  

- **Do we need it?**  
  - **Yes.** A dedicated Fetcher decouples the DB‐polling logic from the NLP/Modeling logic, making the service easier to scale and maintain. If you later switch to `LISTEN`/`NOTIFY`, only this module changes.

---

### 4.3 Preprocessor

**Responsibility:** Clean and normalize raw text, remove noise, optionally detect/filter by language.

- **Input:** Raw JSON `payload` from `raw_events` (fields vary by source, but assume `payload.text` or combination of `payload.title + payload.selftext`).  
- **Output:**  
  - `clean_text: str` (lowercased, URLs removed, emojis stripped, optionally lemmatized).  

- **Library Choices & Trade‐Offs:**

  1.  **`spaCy` (Recommended for High Accuracy & Advanced Processing):**
      - **Usage:**
        ```python
        import spacy
        # Load a suitable model (e.g., en_core_web_lg for better accuracy)
        # Consider GPU acceleration if using transformer components within spaCy
        nlp = spacy.load("en_core_web_lg") 

        def spacy_clean(text: str) -> str:
            doc = nlp(text)
            tokens = []
            for token in doc:
                if (token.is_stop or 
                    token.is_punct or 
                    token.is_space or 
                    token.like_url or 
                    token.like_email):
                    continue
                tokens.append(token.lemma_.lower())
            return " ".join(tokens)
        ```
      - **Pros:**
        - Superior tokenization, lemmatization, and stop-word removal.
        - Can perform part-of-speech tagging, named entity recognition (NER) for more advanced feature engineering if needed.
        - Highly configurable pipeline.
        - Excellent for achieving higher accuracy in downstream sentiment analysis.
        - Your 5950X CPU can handle `spaCy`'s processing efficiently, especially when batching documents.
      - **Cons:**
        - Slightly higher processing time per document compared to simpler regex methods, but manageable with your hardware.
        - Larger memory footprint for models like `en_core_web_lg`.

  2.  **Regex + `emoji` Package (Basic Cleaning):**
      - **Usage:**
        ```python
        import re
        import emoji

        def simple_clean(text: str) -> str:
            text = re.sub(r'https?://\S+', '', text)  # remove URLs
            text = re.sub(r'\s+', ' ', text)          # normalize whitespace
            text = emoji.demojize(text)             # convert emojis to text (e.g. :smile:)
            # Optional: remove emojis: text = emoji.replace_emoji(text, replace='')
            text = text.lower()
            return text.strip()
        ```
      - **Pros:**
        - Very fast for basic cleaning tasks.
        - Minimal dependencies.
      - **Cons:**
        - Less linguistically sophisticated; may not handle complex cases as well as `spaCy`.
        - Lemmatization or advanced tokenization requires additional libraries.

- **Language Detection:**
  - Use a library like `langdetect` or `fastText` (if `spaCy` model doesn't inherently provide reliable language identification for your needs).
  - **Recommendation:** For the MVP, detect language and store it. Filter to process only English text initially, but retain other languages for future enhancements.

- **Do we need it?**
  - **Yes.** Effective preprocessing is crucial for accurate sentiment analysis. Given your hardware, opting for a more thorough approach with `spaCy` is recommended for better results.

---

### 4.4 Sentiment Analyzer

**Responsibility:** Take preprocessed text and return sentiment score, label, confidence, and model version.

- **Input:** `clean_text: str` from Preprocessor.
- **Output:** `(sentiment_score: float, sentiment_label: str, confidence: float, model_version: str)`.
- **Model Choices & Trade‐Offs (Prioritizing Accuracy with High-End Hardware):**

| Model       | Key Output(s)                               | Pros                                                                                                                               | Cons                                                                                                                            | Best For                                   |
|-------------|---------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|
| **FinBERT (Primary Recommendation)** | Probabilities for `[negative, neutral, positive]` | • **Excellent accuracy on financial texts** due to domain-specific fine-tuning. <br> • Returns explicit confidences via softmax. <br> • Your 4090 GPU will provide fast inference. | • Large model (~120M-400M+ params depending on version). <br> • Primarily English.                                            | **All finance-related subreddits (e.g., r/wallstreetbets, r/stocks).** This should be the default choice. |
| **Custom BERT/Transformer (Ultimate Goal)** | Depends on your fine‐tuning                 | • **Potentially highest accuracy** by fine-tuning on your specific Reddit dataset. <br> • Can be tailored to project-specific nuances and vocabulary. <br> • Your hardware (4090 for training/inference, 5950X for data prep) makes this highly feasible. | • Requires significant effort: data collection, labeling, training pipeline setup, and maintenance. <br> • Inference cost similar to FinBERT. | Achieving state-of-the-art performance tailored to your exact dataset and requirements. |
| **VADER**   | `compound` (float), `pos/neu/neg` proportions | • Very fast (rule‐based). <br> • Good for general social‐media text. <br> • Lightweight.                                                     | • Doesn’t learn domain‐specific slang. <br> • Only English. <br> • No built-in “confidence” (besides compound magnitude).        | Prototyping, or non-critical/non-financial general text if speed is paramount over accuracy. Less relevant given your hardware. |
| **TextBlob** | `polarity` (float), `subjectivity` (float)   | • Easy to use. <br> • Pure‐Python.                                                                                                   | • Slower than VADER. <br> • No direct confidence. <br> • Only English.                                                          | Prototyping only. Not recommended for production accuracy in this project. |

- **Multi‐Model Strategy (Optional - Less Critical with High-End Hardware):**
  - The original idea of using VADER as a fast-lane filter before routing to a heavier model like FinBERT is less critical given your 4090 GPU. You can likely process most, if not all, relevant texts directly with FinBERT (or a custom model) with acceptable performance.
  - However, if extreme throughput is required for a subset of very generic, non-financial texts, this strategy could still be considered, but it adds complexity.

- **Model Versioning:**
  - Always store a `model_version` (e.g., `"finbert-v1.2-financial-phrasebank"`, `"custom-reddit-bert-v1.1-2025-07"`) with each row in `sentiment_results`.
  - This allows A/B tests and tracking of model performance over time. Configuration should specify the active model and version:
    ```yaml
    sentiment:
      model:
        name: "finbert"  # or "custom_bert"
        version: "finbert-v1.2-financial-phrasebank"
        # path: "/path/to/your/model_files_if_local/"
      # For spaCy in preprocessor
      preprocessor:
        spacy_model: "en_core_web_lg"
    ```

- **Do we need it?**
  - **Yes.** This is the core of the service.

---

### 4.5 Result Processor

**Responsibility:**  
- Insert each sentiment result into `sentiment_results`.  
- Immediately update corresponding row in `sentiment_metrics` in real time.  
- Handle batch inserts and transactional consistency.

- **Pseudo‐Code (Python Async):**

  ```python
  async def process_batch(db, processed_events: List[ProcessedEvent]):
      # 1. Batch insert into sentiment_results
      await db.execute_many(
          """
          INSERT INTO sentiment_results (
            event_id, occurred_at, source, source_id,
            sentiment_score, sentiment_label, confidence,
            model_version, raw_text
          ) VALUES (
            :event_id, :occurred_at, :source, :source_id,
            :sentiment_score, :sentiment_label, :confidence,
            :model_version, :raw_text
          );
          """,
          [e.dict() for e in processed_events]
      )

      # 2. Real‐time metrics updates (could be done per‐event or in a mini‐batch)
      for e in processed_events:
          await db.execute(
              """
              INSERT INTO sentiment_metrics (
                time_bucket, source, source_id, label, count, avg_score
              )
              VALUES (
                time_bucket('1h', :occurred_at),
                :source, :source_id, :sentiment_label,
                1, :sentiment_score
              )
              ON CONFLICT (time_bucket, source, source_id, label)
              DO UPDATE SET
                count = sentiment_metrics.count + 1,
                avg_score = (
                  (sentiment_metrics.avg_score * sentiment_metrics.count)
                  + EXCLUDED.avg_score
                ) / (sentiment_metrics.count + 1);
              """,
              {
                "occurred_at": e.occurred_at,
                "source": e.source,
                "source_id": e.source_id,
                "sentiment_label": e.sentiment_label,
                "sentiment_score": e.sentiment_score
              }
          )
  ```

- **Transactional Guarantees:**  
  - If using a single DB transaction for both steps (inserting into `sentiment_results` and updating `sentiment_metrics`), you guarantee consistency. If any part fails, the entire transaction rolls back, and you can retry.  
  - If the batch is large and you worry about transaction size/timeouts, you can group into smaller sub‐batches.  

- **Error Handling / Dead‐Letter:**  
  - If an update to `sentiment_metrics` fails (e.g. transient DB error), log the error and either retry or mark the event as “needs‐metrics‐rebuild” so a background job can catch up later.  

---

### 4.6 API Service

**Responsibility:** Expose RESTful HTTP endpoints for clients to:

1. Analyze ad‐hoc text  
2. Query stored sentiment results  
3. Query aggregated metrics  

- **Framework Suggestion:** FastAPI (async, built‐in OpenAPI docs, minimal boilerplate).

#### 4.5.1 Endpoints

1. **Analyze Text On‐Demand**  
   - **Route:** `GET /api/v1/sentiment/analyze?text={URL‐encoded text}`  
   - **Behavior:**  
     - Validate `text` parameter (required; max length = `config.processing.max_text_length`).  
     - Run preprocessing → sentiment model → return JSON.  
   - **Response (200):**  
     ```json
     {
       "text": "your text here",
       "sentiment_score": 0.85,
       "sentiment_label": "positive",
       "confidence": 0.95,
       "model_version": "finbert-v1.2"
     }
     ```  
   - **Error (400):**  
     ```json
     {
       "error": {
         "code": "MISSING_PARAMETER",
         "message": "Query parameter 'text' is required."
       }
     }
     ```

2. **Get Sentiment Events**  
   - **Route:** `GET /api/v1/sentiment/events`  
   - **Query Parameters:**  
     - `source` (required) – e.g. `reddit`  
     - `start` (optional) – ISO-8601 datetime (defaults to now() − 24 h)  
     - `end` (optional) – ISO-8601 datetime (defaults to now())  
     - `label` (optional) – filter by `sentiment_label`  
     - `source_id` (optional) – filter by subreddit or other identifier  
     - `limit` (optional, int ≤ 1000; default 100)  
     - `cursor` (optional) – for pagination (opaque string)  
   - **Behavior:**  
     1. Validate `source`. If missing → `400`.  
     2. Parse `start`/`end`; if invalid format → `400`.  
     3. Enforce `limit ≤ 1000`; if violated → `400`.  
     4. Build SQL with `WHERE source = :source 
        AND occurred_at BETWEEN :start AND :end 
        [AND sentiment_label = :label] 
        [AND source_id = :source_id]`.  
     5. Apply `ORDER BY occurred_at DESC LIMIT :limit + 1`.  
     6. If `rows > limit`, set `next_cursor = encode_cursor(last_row.occurred_at, last_row.event_id)`; return only `limit` rows.  
   - **Response (200):**  
     ```json
     {
       "results": [
         {
           "event_id": "abc123",
           "occurred_at": "2025-06-01T12:34:56Z",
           "source": "reddit",
           "source_id": "r/wallstreetbets",
           "sentiment_score": 0.75,
           "sentiment_label": "positive",
           "confidence": 0.92,
           "model_version": "finbert-v1.2"
         }
         // … up to 'limit' items …
       ],
       "count": 350,           // total matching rows (optional, adds query cost)
       "limit": 100,
       "next_cursor": "eyJ0IjoiMjAyNS0wNi0wMVQxMjowMzo1Nl...",  // for the next page
       "start": "2025-06-01T00:00:00Z",
       "end": "2025-06-02T00:00:00Z"
     }
     ```  
   - **Error (400 Example):**  
     ```json
     {
       "error": {
         "code": "INVALID_DATE_FORMAT",
         "message": "Query parameter 'start' is not in ISO-8601 format."
       }
     }
     ```

3. **Get Aggregated Metrics**  
   - **Route:** `GET /api/v1/sentiment/metrics`  
   - **Query Parameters:**  
     - `source` (required)  
     - `start` (optional) – ISO-8601 datetime (defaults to now() − 24 h)  
     - `end` (optional) – ISO-8601 datetime (defaults to now())  
     - `bucket` (optional, one of `1h`, `1d`, `1w`; default `1h`)  
     - `source_id` (optional)  
     - `label` (optional)  
   - **Behavior:**  
     1. Validate `source`. If missing → `400`.  
     2. Parse `start` / `end`; if invalid → `400`.  
     3. Validate `bucket` ∈ {`1h`,`1d`,`1w`}; if invalid → `400`.  
     4. Query `sentiment_metrics` for rows where `time_bucket BETWEEN time_bucket(:bucket, :start) AND time_bucket(:bucket, :end)`, `source = :source`, optional filters `source_id` & `label`.  
   - **Response (200):**  
     ```json
     {
       "metrics": [
         {
           "time_bucket": "2025-06-01T00:00:00Z",
           "source": "reddit",
           "source_id": "r/wallstreetbets",
           "label": "positive",
           "count": 123,
           "avg_score": 0.65
         },
         {
           "time_bucket": "2025-06-01T01:00:00Z",
           "source": "reddit",
           "source_id": "r/wallstreetbets",
           "label": "positive",
           "count": 98,
           "avg_score": 0.70
         },
         // etc.
       ],
       "start": "2025-06-01T00:00:00Z",
       "end": "2025-06-02T00:00:00Z",
       "bucket": "1h"
     }
     ```  
   - **Error (400 Example):**  
     ```json
     {
       "error": {
         "code": "INVALID_BUCKET",
         "message": "Query parameter 'bucket' must be one of: 1h, 1d, 1w."
       }
     }
     ```

4. **Health Check**  
   - **Route:** `GET /health`  
   - **Behavior:**  
     - Verify DB connection (e.g. run `SELECT 1;`).  
     - Verify sentiment model can load (e.g. instantiate VADER client or load FinBERT tokenizer/model).  
     - Return `200 OK` with `{ "status": "healthy" }` if checks pass, else `503 Service Unavailable`.

---

## 5. APIs

All endpoints are under `/api/v1/sentiment`. Use standard HTTP status codes:

- **200 OK** – successful response  
- **400 Bad Request** – invalid/missing parameters  
- **404 Not Found** – requested resource not found (e.g., `event_id` not in DB)  
- **500 Internal Server Error** – unhandled exceptions (log and return generic message)  

Because this is a **private API**, authentication (e.g., API key) can be enforced at the ingress layer (e.g. via an API gateway). This service can assume that clients are trusted internal systems, but still should validate inputs thoroughly.

---

## 6. Configuration

Use environment variables and a YAML file (`config/config.yaml`). Example:

```yaml
# config/config.yaml

sentiment:
  model:
    name: "vader"             # or "finbert", "custombert"
    version: "v3.3"           # model version identifier
    threshold: 0.05           # for neutral/positive/negative boundary

  processing:
    batch_size: 100
    poll_interval_seconds: 30
    max_text_length: 5000
    language: "en"            # skip non-EN if set
    enable_language_filter: false

  database:
    host: ${PG_HOST}
    port: ${PG_PORT}
    name: ${PG_DB}
    user: ${PG_USER}
    password: ${PG_PASSWORD}

  api:
    host: "0.0.0.0"
    port: 8000
    debug: false
    workers: 4
```

- **Secret Management:**  
  - Do not commit DB credentials to Git. Use environment variables (`PG_USER`, `PG_PASSWORD`) instead.  
- **Validation:**  
  - Use Pydantic (or similar) inside your code to load & validate config; fail fast on missing/invalid values.  
## 7. Error Handling & Logging

- **Structured Logging:** Implement JSON-formatted logging for easier parsing by log management systems. Include correlation IDs for tracing requests across components.
- **Error Classification:** Distinguish between transient errors (e.g., temporary DB unavailability, retryable) and permanent errors (e.g., malformed data, non-retryable).
- **Dead-Letter Events:** Events that consistently fail processing (e.g., due to malformed data or unrecoverable errors) should be moved to a `dead_letter_events` table. This table will store the original event data, error details, and timestamps for later investigation and potential manual intervention or reprocessing (a full automated retry mechanism for these is a future enhancement).
- **API Error Responses:** Use standard HTTP status codes and provide clear error messages in API responses.
- **Component-Level Error Handling:** Each component (Fetcher, Preprocessor, Analyzer, Processor) should have robust error handling.
- **Configuration:** Log level and format (JSON/console) should be configurable.

- **Log Levels:**
  - `DEBUG`: raw payload dumps, preprocessor input/output (only if `config.api.debug = true`).
  - `INFO`: “Fetched 100 events,” “Processed batch of 100, inserted into DB.”
  - `WARNING`: “Model inference took >1s for text of length 10k,” “Retrying DB write.”
  - `ERROR`: “Sentiment model load failure,” “Database connection timeout.”
  - `CRITICAL`: “Unable to start service; migration failed.”

- **Error Tracking:**
  - Integrate Sentry (or similar). On any unhandled exception, capture full stack trace.
  - Configure alerts for error rates > 5/minute.
- **Error Tracking:**  
  - Integrate Sentry (or similar). On any unhandled exception, capture full stack trace.  
  - Configure alerts for error rates > 5/minute.  

- **Dead-Letter Queue:**  
  - If an event fails sentiment analysis or DB insert after X retries, insert into `dead_letter_events` table:  
    ```sql
    CREATE TABLE dead_letter_events (
      id          SERIAL PRIMARY KEY,
      event_id    TEXT        NOT NULL,
      occurred_at TIMESTAMPTZ NOT NULL,
      source      TEXT        NOT NULL,
      source_id   TEXT        NOT NULL,
      error_msg   TEXT,
      created_at  TIMESTAMPTZ DEFAULT NOW()
    );
    ```  
  - Have a small background job or manual process to inspect/fix these errors.

---

## 8. Performance Considerations (MVP)

Because the primary goal is to get a working prototype up quickly:

1. **Use VADER on CPU**  
   - Expect ~500–1,000 short tweets/comments per second on a 4-core machine.  
   - For early testing, this throughput is sufficient.  

2. **Async I/O & DB Batching**  
   - Use an async framework (FastAPI + `asyncpg` or SQLAlchemy async) so the service does not block on I/O.  
   - Buffer processed events into mini-batches (e.g. 50–100 rows) and do a single multi-row `INSERT` per batch to reduce roundtrips.  

3. **Connection Pooling**  
   - Set DB pool size = 10 (for 4 workers, 4 threads each, an 8–10 connection pool is safe).  

4. **Monitor & Iterate**  
   - Expose Prometheus metrics:  
     - `events_processed_total{model="vader"}`  
     - `sentiment_latency_seconds`  
     - `db_insert_duration_seconds{table="sentiment_results"}`  
   - Once the MVP runs for a few days, review metrics to see if you need to switch to FinBERT or add GPUs.

---

## 9. Testing Strategy

### 9.1 Unit Tests

- **Focus Areas:**  
  1. **Data Fetcher**:  
     - Mock DB.  
     - Test `UPDATE … RETURNING` logic (simulate claiming rows, no duplicates).  
  2. **Preprocessor**:  
     - Input: empty string (`""`) → output `""`.  
     - Input: `"Visit https://example.com 😊!"` → output `"visit"`.  
     - Very long text (> 5,000 chars) → test truncation.  
  3. **Sentiment Analyzer**:  
     - VADER: `"I love this!"` → positive label.  
     - FinBERT: with a known finance-text snippet, assert it yields a specific label.  
     - Edge case: very neutral text, e.g., `"The market is open."` → likely neutral.  
  4. **Result Processor**:  
     - Mock DB calls to test that the `INSERT … ON CONFLICT` logic is correct.  
  5. **API Endpoints**:  
     - Using TestClient (FastAPI), call `/sentiment/analyze`, confirm 200 & correct JSON schema.  
     - Call `/sentiment/events` missing `source` → 400.  
- **Coverage Target:** Aim for ≥ 80% for critical modules (fetcher, preprocessor, analyzer).

### 9.2 Integration Tests

- **Dockerized Test Environment:**  
  - Create `docker-compose.test.yml` with:  
    - `timescaledb:latest` (with a mounted test database)  
    - `sentiment-service:latest` (built from `Dockerfile`)  
  - On startup, run Alembic migrations automatically, then run pytest:  
    ```yaml
    services:
      timescaledb:
        image: timescale/timescaledb:latest-pg14
        environment:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: testdb
        healthcheck:
          test: ["CMD", "pg_isready", "-U", "test"]
          interval: 10s
          retries: 5

      sentiment:
        build:
          context: .
          dockerfile: Dockerfile
        environment:
          - PG_HOST=timescaledb
          - PG_PORT=5432
          - PG_DB=testdb
          - PG_USER=test
          - PG_PASSWORD=test
          - CONFIG_FILE=/app/config/config_test.yaml
        depends_on:
          timescaledb:
            condition: service_healthy
        command: ["pytest", "--disable-warnings", "--maxfail=1", "-q"]
    ```

- **Data Seeding & Cleanup:**  
  - Provide a SQL fixture to seed 50 `raw_events` (mix of positive/negative)  
  - After tests, drop tables or run `TRUNCATE` on `raw_events`, `sentiment_results`, `sentiment_metrics`.

### 9.3 Performance Tests (Optional, Later)

- **Load Testing (Post-MVP):**  
  - Use Locust or Apache JMeter to simulate 1,000 clients calling `/sentiment/analyze` concurrently.  
  - Benchmark `50,000 sentiment events/second` via the fetcher pipeline (if you switch to FinBERT + GPU).  

---

## 10. Deployment

Because you only want to ensure migrations run before the service, here’s a minimal `docker-compose.yaml` snippet:

```yaml
version: "3.8"
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg14
    environment:
      POSTGRES_USER: production
      POSTGRES_PASSWORD: s3cr3t
      POSTGRES_DB: productiondb
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "production"]
      interval: 10s
      retries: 5

  sentiment-service:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - PG_HOST=timescaledb
      - PG_PORT=5432
      - PG_DB=productiondb
      - PG_USER=production
      - PG_PASSWORD=s3cr3t
      - CONFIG_FILE=/app/config/config.yaml
    depends_on:
      timescaledb:
        condition: service_healthy
    entrypoint:
      - sh
      - -c
      - |
        alembic upgrade head
        exec uvicorn app.main:app --host 0.0.0.0 --port 8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

- **Alembic Migrations:**  
  - Ensure your `alembic.ini` is configured to point at `postgresql://production:s3cr3t@timescaledb:5432/productiondb`.  
  - On service start, `alembic upgrade head` runs all pending migrations, creating `sentiment_results` and `sentiment_metrics` if missing.  
- **Health Check:**  
  - The container’s NSG (Kubernetes probe or Docker healthcheck) hits `/health`. If it fails (DB down or model can’t load), container is marked unhealthy and can be restarted.  

---

## 11. Future Enhancements

1. **Model Training Pipeline**  
   - Build a system (e.g. an Airflow DAG) that:  
     1. Labels a small random sample of Reddit posts each week.  
     2. Retrains a custom BERT/FinBERT model monthly.  
     3. Pushes new model artifacts to an S3 bucket.  
     4. Updates `config.yaml` → `model.version = "custombert-2025-07"`.  

2. **Advanced Analytics**  
   - **Topic Modeling (LDA, BERTopic):** Add a pipeline step to cluster posts by topics.  
   - **Named Entity Recognition:** Use spaCy or HuggingFace NER models to tag tickers, company names.  
   - **Emotion Detection:** Extend beyond polarity to detect anger, joy, fear.  

3. **Real-Time Processing via Kafka**  
   - Instead of polling `raw_events`, have the Reddit scraper produce to a Kafka topic `reddit.raw_events`.  
   - Sentiment service becomes a Kafka consumer group, writes results to DB.  
   - Benefits: true streaming, better horizontal scaling.

4. **Multi-Language Support**  
   - Integrate a translation step (e.g. AWS Translate) for non-English texts before feeding into an English-only sentiment model.  
   - Or train language-specific sentiment models (BERT-multilingual).  

5. **Advanced Monitoring & Dashboards**  
   - Expose Prometheus metrics for events/sec, latency, DB errors.  
   - Create Grafana dashboards showing:  
     - Real-time sentiment distribution per subreddit  
     - P95/P99 latency of `/analyze` endpoint  
     - Health of DB connection pools  

6. **Data Retention & Compression**  
   - After 90 days, compress old chunks of `sentiment_results` and `sentiment_metrics` using TimescaleDB’s native compression:  
     ```sql
     ALTER TABLE sentiment_results SET (
       timescaledb.compress = TRUE
     );
     SELECT add_compression_policy('sentiment_results', INTERVAL '90 days');
     ```  
   - Archival strategies: move raw JSON payloads older than 1 year to cold storage.

---

**End of Service Design Document**
