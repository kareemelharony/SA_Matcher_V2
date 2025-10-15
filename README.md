# SA_Matcher_V2

SA Matcher ingests Amazon.sa listings, keeps a historical cache of seed products,
and ranks close competitors using Amazon Product Advertising API 5.0 data. The
project also ships with a Streamlit dashboard so you can inspect the top
competitors for each seed listing and monitor how prices, reviews and ratings
change over time.

## Features

* Fetch seed product data (title, description, bullets, BSR, price, reviews,
  etc.) using the Amazon Product Advertising API.
* Cache product metadata locally in SQLite so items are fetched at most once
  unless explicitly refreshed.
* Discover potential competitors from related products and keyword searches, run
  TF-IDF similarity on titles and descriptions, and store the top matches.
* Export competitor snapshots to CSV and visualise the data in a Streamlit
  dashboard (10 cards per page, including benchmark stats).

## Project layout

```
config/                    # API credential templates
src/sa_matcher/            # Python package implementing the pipeline
  competitor_service.py    # Finds competitor candidates and computes similarity
  config.py                # Loads Amazon PA-API credentials
  dashboard.py             # Streamlit dashboard
  main.py                  # Command line interface
  models.py                # Dataclasses for products and competitors
  paapi_client.py          # Signed API client for PA-API 5.0
  parsers.py               # Helpers that normalise raw API responses
  repository.py            # SQLite persistence layer
  seed_manager.py          # Seed ingestion workflow
  similarity.py            # TF-IDF cosine similarity utilities
requirements.txt           # Python dependencies
```

## Getting started

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Provide Amazon Product Advertising API 5.0 credentials. Copy the template
   and fill in your keys:

   ```bash
   cp config/api_keys.example.json config/api_keys.json
   # edit config/api_keys.json and add your access key, secret key and associate tag
   ```

   Alternatively, set the environment variables `PAAPI_ACCESS_KEY`,
   `PAAPI_SECRET_KEY`, and `PAAPI_PARTNER_TAG` (plus optional marketplace
   overrides).

3. Ingest one or more seed ASINs:

   ```bash
   python -m sa_matcher.main ingest B07XXXXXXX B08YYYYYYY
   ```

4. Compute the competitor list for a seed ASIN and export the results if needed:

   ```bash
   python -m sa_matcher.main competitors B07XXXXXXX --limit 10 --export data/B07XXXXXXX_competitors.csv
   ```

   The command stores similarity scores in `data/sa_matcher.db` and appends a new
   snapshot every time you run it.

5. Launch the dashboard to review the stored data (shows 10 competitor cards per
   page and highlights the strongest three competitors for price, BSR, reviews
   and ratings):

   ```bash
   streamlit run src/sa_matcher/dashboard.py
   ```

## Notes

* API rate limits apply. The system caches product information to avoid fetching
  the same ASIN twice unless `--force` or refresh buttons are used.
* Similarity calculations currently rely on title, description and bullet point
  text. Extend `similarity.py` if you want to incorporate image features.
* The SQLite database lives in `data/sa_matcher.db`. Back it up or ship it to an
  analytics warehouse for long-term storage if required.
