---
description: Power BI Hybrid Integration Setup
---

# Power BI Integration Guide

This document explains how to configure a *hybrid* dashboard that combines:

1. **Real-time streaming** via a Power BI *push dataset*.
2. **Historical & ad-hoc analysis** via DirectQuery on TimescaleDB.

> Prerequisites: Power BI Pro (or higher), a workspace, and gateway access to the database.

---
## 1  Create the Push Dataset
1. In the workspace, choose *New ➜ Streaming dataset ➜ API*.
2. Schema example:
   | column            | type |
   |-------------------|------|
   | timestamp         | DateTime |
   | source            | Text |
   | source_id         | Text |
   | sentiment_score   | Decimal |
   | sentiment_label   | Text |
3. Note the *Push URL*; add it to `.env`:
   ```
   POWERBI_PUSH_URL=https://api.powerbi.com/beta/…
   POWERBI_API_KEY=<datasetKey>
   ```

---
## 2  Configure DirectQuery
1. Ensure the TimescaleDB instance is reachable by an **on-premises data gateway**.
2. Create a read-only DB role with minimal privileges (`SELECT`).
3. (Optional) Build SQL views/materialised views e.g. `sentiment_metrics_daily`.
4. In Power BI Desktop: *Get Data ➜ PostgreSQL ➜ DirectQuery*, provide gateway creds.

---
## 3  Build a Composite Model
1. Load the push dataset table (live connection).
2. Load DirectQuery tables/views.
3. Add a `Date` dimension; relate on `[timestamp] → Date[Date]`.
4. Use the push table for live cards/line-charts (last N minutes) and DirectQuery tables for historical visuals.

---
## 4  Service-side Changes
* **`sentiment_analyzer/integrations/powerbi.py`** – async client that posts rows with retry/back-off.
* Startup event initialises the client when `POWERBI_PUSH_URL` is present.
* `ResultProcessor` calls `powerbi_client.push_row()` after each successful commit.

---
## 5  Security
* Store keys in environment variables only.
* Use HTTPS for the push URL.
* Limit DB role to SELECT.

---
## 6  Troubleshooting
* 429 / throttling → implementation should back-off and retry.
* Gateway errors → test connectivity in Power BI *Manage Gateways*.
* Dataset schema changes require recreating the push dataset.

---
Happy dashboarding!
