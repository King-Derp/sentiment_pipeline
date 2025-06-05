# Product Requirements Document: Sentiment Analysis Service

**Version:** 1.0
**Date:** 2025-06-04

## 1. Introduction & Overview

The Sentiment Analysis Service is a core component of the broader Sentiment Pipeline project. Its primary purpose is to ingest text data from various sources (initially Reddit events from the `raw_events` table), perform sentiment analysis to determine if the expressed sentiment is positive, negative, or neutral, and quantify this sentiment with scores and confidence levels. The service provides these insights for financial data analysis, making results available via a database and an API.

This service is designed to be modular, configurable, and performant, leveraging available hardware resources (GPU/CPU) for accurate and timely sentiment extraction.

## 2. Goals

- **G1: Accurate Sentiment Determination:** Accurately classify the sentiment of financial text data, particularly from Reddit discussions.
- **G2: Granular Sentiment Output:** Provide detailed sentiment scores, labels (e.g., positive, negative, neutral), and confidence levels for each analyzed text.
- **G3: Efficient Data Storage:** Store both individual sentiment results and aggregated time-series metrics efficiently in TimescaleDB hypertables.
- **G4: Accessible Insights:** Offer a RESTful API for on-demand sentiment analysis of arbitrary text and for retrieving processed sentiment data and metrics.
- **G5: Seamless Integration:** Integrate smoothly into the existing data pipeline by consuming events from the `raw_events` table and marking them as processed.
- **G6: Configurability & Flexibility:** Allow configuration of preprocessing steps, sentiment analysis models (e.g., FinBERT, custom models), and operational parameters.
- **G7: High Performance:** Achieve high throughput for batch processing and low latency for API requests, utilizing available GPU (NVIDIA 4090) and CPU (AMD 5950X) resources effectively.
- **G8: Robustness & Reliability:** Ensure stable operation with comprehensive error handling and logging.

## 3. Target Users & Stakeholders

- **Data Analysts/Scientists:** Utilize the processed sentiment data for financial modeling, market trend analysis, and generating investment insights.
- **Downstream Applications/Services:** Consume sentiment scores and metrics programmatically via the API for automated decision-making or further analysis.
- **Project Developers:** Maintain, extend, and improve the sentiment analysis capabilities within the Sentiment Pipeline project.

## 4. Scope

### 4.1 In Scope (MVP & Initial Iterations)

- **IS1: Data Consumption:** Consume raw text events from the `raw_events` TimescaleDB table.
- **IS2: Event Claiming:** Implement a mechanism to mark events in `raw_events` as processed by the sentiment service (e.g., using the `processed_sentiment` flag).
- **IS3: Advanced Text Preprocessing:** Employ `spaCy` for high-quality text cleaning, including lowercasing, removal of URLs/emojis/special characters, lemmatization, and stop-word removal.
- **IS4: Language Detection:** Identify the language of the input text (initially focusing on processing English content).
- **IS5: High-Accuracy Sentiment Analysis:** Utilize FinBERT as the primary model for sentiment analysis, leveraging GPU acceleration.
- **IS6: Detailed Results Storage:** Persist individual sentiment analysis results (including event ID, original timestamp, source, source ID, raw text, sentiment score, label, confidence, and model version) in the `sentiment_results` TimescaleDB hypertable.
- **IS7: Aggregated Metrics Storage:** Calculate and store aggregated sentiment metrics (e.g., count, total score, average score, last event timestamp per time bucket, source, source ID, and label) in the `sentiment_metrics` TimescaleDB hypertable.
- **IS8: API Endpoints:**
    - `POST /api/v1/sentiment/analyze`: For on-demand sentiment analysis of a given text string.
    - `GET /api/v1/sentiment/events`: To retrieve stored sentiment results with filtering capabilities.
    - `GET /api/v1/sentiment/metrics`: To retrieve aggregated sentiment metrics with filtering capabilities.
- **IS9: Model Versioning:** Store and associate a model version with every sentiment result.
- **IS10: Configuration Management:** Utilize environment variables and YAML files for service configuration (database, models, logging, etc.).
- **IS11: Error Handling & Logging:** Implement robust error handling and structured logging for diagnostics and monitoring.
- **IS12: Dockerization:** Package the service as a Docker container for deployment and orchestration via Docker Compose.

### 4.2 Out of Scope (Future Considerations)

- **OS1:** Real-time, low-latency processing for extremely high-volume, streaming data sources (initial focus is on efficient batch processing).
- **OS2:** Full sentiment analysis support for multiple languages beyond English in the initial versions.
- **OS3:** A dedicated user interface (UI) for interacting with the service (API-first approach).
- **OS4:** Complex alerting mechanisms based on sentiment shifts or anomalies (can be built as a separate layer on top of the data).
- **OS5:** In-service model training or fine-tuning pipelines (assumes pre-trained models or models developed in a separate MLOps pipeline).
- **OS6:** Advanced NLP tasks beyond sentiment analysis, such as aspect-based sentiment, topic modeling, or entity-specific sentiment, unless incorporated into a custom model.

## 5. Key Features & Requirements

### 5.1 Functional Requirements

- **FR1: Data Ingestion:** The service MUST periodically fetch new, unprocessed events from the `raw_events` table in TimescaleDB based on a configurable batch size.
- **FR2: Event Claiming:** The service MUST update a flag (e.g., `processed_sentiment`) in the `raw_events` table for fetched events to prevent reprocessing.
- **FR3: Text Preprocessing:** The service MUST preprocess input text using `spaCy` with `en_core_web_lg` (or a similarly capable model) to perform: lowercasing, URL removal, emoji removal/conversion, lemmatization, and stop-word removal.
- **FR4: Language Detection:** The service MUST detect the language of the input text. Initially, it will prioritize processing English text.
- **FR5: Sentiment Analysis:** The service MUST generate a sentiment score (float), a sentiment label (e.g., "positive", "negative", "neutral"), and a confidence score (float) using a configurable model, defaulting to FinBERT.
- **FR6: Results Storage:** The service MUST store detailed sentiment results in the `sentiment_results` hypertable, including `event_id`, `occurred_at`, `source`, `source_id`, `sentiment_score`, `sentiment_label`, `confidence`, `model_version`, and `raw_text`.
- **FR7: Metrics Aggregation & Storage:** The service MUST update the `sentiment_metrics` hypertable in near real-time, aggregating counts, total scores, and average scores per time bucket (e.g., hourly), source, source_id, and sentiment label.
- **FR8: API - Analyze Text:** The service MUST provide a `POST /api/v1/sentiment/analyze` endpoint that accepts a JSON payload with text and returns its sentiment analysis.
- **FR9: API - Get Events:** The service MUST provide a `GET /api/v1/sentiment/events` endpoint to query stored `sentiment_results` with filters for time range, source, source_id, label, etc.
- **FR10: API - Get Metrics:** The service MUST provide a `GET /api/v1/sentiment/metrics` endpoint to query stored `sentiment_metrics` with filters for time range, bucket size, source, source_id, label, etc.
- **FR11: Configuration:** The service MUST be configurable via environment variables and a YAML file for database connections, model selection (name, version, path), batch sizes, and logging levels.
- **FR12: Model Versioning:** The service MUST record the specific version of the sentiment model used for each analysis in the `sentiment_results` table.

### 5.2 Non-Functional Requirements

- **NFR1: Performance:** 
    - Batch processing target: Process at least [Specify target, e.g., 1000] Reddit-like events per minute on specified hardware.
    - API Latency: `POST /analyze` endpoint P95 latency < 500ms for typical texts using FinBERT on GPU.
    - Resource Utilization: Efficiently utilize NVIDIA 4090 for model inference and AMD 5950X for preprocessing tasks.
- **NFR2: Accuracy:** Prioritize high sentiment analysis accuracy, especially for financial texts. The choice of FinBERT and `spaCy` reflects this. Aim for F1-scores > [Specify target, e.g., 0.80] on a representative labeled dataset for key sentiment classes.
- **NFR3: Scalability:** While the initial deployment may be a single instance, the service architecture should not preclude horizontal scaling if future loads demand it. The database (TimescaleDB) is inherently scalable.
- **NFR4: Reliability:** The service MUST handle transient errors (e.g., temporary database unavailability) gracefully with retry mechanisms. Data integrity MUST be maintained.
- **NFR5: Maintainability:** Code MUST be modular, well-documented, adhere to PEP8 standards, and include type hints. Project structure should be clean and intuitive.
- **NFR6: Configurability:** Key parameters (models, database, batch sizes) MUST be easily configurable without code changes.
- **NFR7: Testability:** The service MUST have comprehensive unit tests (Pytest) covering individual components and integration tests verifying component interactions and database operations.
- **NFR8: Deployment:** The service MUST be deployable as a Docker container and managed via Docker Compose as part of the larger Sentiment Pipeline project.
- **NFR9: Security:** Database credentials and any sensitive configuration MUST be managed securely (e.g., via environment variables, not hardcoded).

### 5.3 Data Requirements

- **Input Data:** Consumes records from the `raw_events` table. Key fields include `id`, `occurred_at`, `source`, `source_id`, and `payload` (containing text fields like `title`, `selftext`).
- **Output Data Models:**
    - `sentiment_results` table: Schema as defined in `sentiment/design.md`.
    - `sentiment_metrics` table: Schema as defined in `sentiment/design.md`.
    - API DTOs: Pydantic models will define the structure of API request and response bodies, ensuring type safety and validation.

## 6. Success Metrics

- **SM1: Sentiment Accuracy:** F1-score, precision, and recall on a manually curated and labeled dataset of financial texts (target: F1 > 0.80 for primary labels).
- **SM2: Data Coverage & Freshness:** Percentage of new events from `raw_events` processed within 1 hour of their arrival.
- **SM3: Processing Throughput:** Average number of events processed per minute during batch operations.
- **SM4: API Performance:** Average and 95th percentile (P95) response times for all API endpoints. (Target P95 < 500ms for `/analyze`, P95 < 200ms for data retrieval endpoints under typical load).
- **SM5: System Stability & Reliability:** Service uptime > 99.9%. Number of critical errors logged per week < 5.
- **SM6: Resource Efficiency:** Monitor CPU, GPU, and memory utilization to ensure efficient use of hardware resources without over-provisioning.

## 7. Future Considerations & Potential Enhancements

- **FC1: Expanded Data Source Support:** Integration with other data sources like Twitter, news APIs, or other financial forums.
- **FC2: Advanced Multi-Language Capabilities:** Full sentiment analysis for other relevant languages (e.g., German, Chinese) using appropriate models.
- **FC3: Custom Model Fine-Tuning:** Integration of a pipeline for fine-tuning custom BERT-style models on project-specific labeled data for improved accuracy.
- **FC4: Aspect-Based Sentiment Analysis (ABSA):** Identifying sentiment towards specific entities, topics, or aspects within the text.
- **FC5: Sentiment Trend Detection & Alerting:** Developing mechanisms to identify significant shifts or anomalies in sentiment trends over time and potentially trigger alerts.
- **FC6: Enhanced Dead-Letter Queue (DLQ):** A more sophisticated DLQ mechanism for events that consistently fail processing, with tools for inspection and reprocessing.
- **FC7: User Interface:** A simple web UI for basic interaction, data exploration, and monitoring of the sentiment service.
