# Rebate Formatter Studio

Dockerized web app for transforming supplier billing CSV files into `Header` + `Lumpsum` rows with:
- Drag-and-drop upload UI
- 5 switchable themes
- Validation and production logging
- Per-file + aggregate metrics (headers, lumpsum lines, row counts)

## What It Does

For each uploaded CSV:
1. Validates required columns.
2. Converts date columns to `MM/DD/YYYY`.
3. Creates one `Header` row per `Rebate Name`.
4. Clears lumpsum-specific columns in header rows.
5. Marks original rows as `Lumpsum`.
6. Sorts output by `Rebate Name` in ascending order, with `Header` before `Lumpsum`.
7. Writes downloadable CSV output.

## Required Columns

- `Rebate Name`
- `Level`
- `Lumpsum - Fee Type`
- `Lumpsum - Amount`
- `Lumpsum - Branch`
- `Lumpsum - Lumpsum Date`
- `Lumpsum - Pay Date`

## Run with Docker

```bash
docker compose up --build
```

Open: [http://localhost:8000](http://localhost:8000)

## Logs and Files

- Logs: `./logs/app.log`
- Uploaded files: `./uploads`
- Processed outputs: `./output`

## UI Sample Preview

Use the `Show UI Sample Data` button in the app to preview:
- Metrics card population
- File details table
- Download button placement
- Theme behavior

This lets you review layout and request UI adjustments before processing real files.
