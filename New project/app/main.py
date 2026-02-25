import logging
from logging.handlers import RotatingFileHandler
import os
import time
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("rebate_processor")
logger.setLevel(logging.INFO)
logger.handlers.clear()

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    LOG_DIR / "app.log", maxBytes=2_000_000, backupCount=5
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

app = FastAPI(title="Rebate CSV Formatter", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

REQUIRED_COLUMNS = [
    "Rebate Name",
    "Level",
    "Lumpsum - Fee Type",
    "Lumpsum - Amount",
    "Lumpsum - Branch",
    "Lumpsum - Lumpsum Date",
    "Lumpsum - Pay Date",
]

DATE_COLUMNS = [
    "Lumpsum - Lumpsum Date",
    "Lumpsum - Pay Date",
]

LUMPSUM_COLUMNS = [
    "Lumpsum - Fee Type",
    "Lumpsum - Amount",
    "Lumpsum - Branch",
    "Lumpsum - Lumpsum Date",
    "Lumpsum - Pay Date",
]


def sanitize_filename(filename: str) -> str:
    safe = "".join(ch for ch in filename if ch.isalnum() or ch in ("-", "_", "."))
    return safe or f"upload-{uuid.uuid4().hex[:8]}.csv"


def validate_columns(df: pd.DataFrame) -> list[str]:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    return missing


def process_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    rebate_column = "Rebate Name"
    level_column = "Level"

    original_columns = df.columns.tolist()

    for col in DATE_COLUMNS:
        if col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce")
            df[col] = parsed.dt.strftime("%m/%d/%Y").fillna("")

    source_rows = len(df)
    distinct_rebates = int(df[rebate_column].nunique(dropna=False))

    header_rows = df.groupby(rebate_column, dropna=False, as_index=False).first()
    header_rows[level_column] = "Header"

    for col in LUMPSUM_COLUMNS:
        if col in header_rows.columns:
            header_rows[col] = ""

    df[level_column] = "Lumpsum"

    # Keep Rebate Name ascending while ensuring Header appears before Lumpsum per rebate.
    final_df = pd.concat([header_rows, df], ignore_index=True)
    final_df["_level_sort"] = final_df[level_column].map({"Header": 0, "Lumpsum": 1}).fillna(2)
    final_df[rebate_column] = final_df[rebate_column].fillna("")
    final_df = final_df.sort_values(by=[rebate_column, "_level_sort"], kind="stable")
    final_df = final_df.drop(columns=["_level_sort"])

    final_df = final_df[original_columns]

    metrics = {
        "input_rows": source_rows,
        "distinct_rebates": distinct_rebates,
        "header_count": len(header_rows),
        "lumpsum_count": source_rows,
        "output_rows": len(final_df),
    }
    return final_df, metrics


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/process")
async def process_files(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    results: list[dict[str, Any]] = []

    for upload in files:
        started = time.time()
        safe_name = sanitize_filename(upload.filename or "input.csv")
        if not safe_name.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail=f"Only CSV files are supported: {safe_name}")

        unique_prefix = uuid.uuid4().hex[:8]
        stored_input = UPLOAD_DIR / f"{unique_prefix}-{safe_name}"

        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"Uploaded file is empty: {safe_name}")

        stored_input.write_bytes(content)
        logger.info("Uploaded file saved: name=%s size_bytes=%s", safe_name, len(content))

        try:
            df = pd.read_csv(stored_input, dtype=str, keep_default_na=False)
        except Exception as exc:
            logger.exception("CSV read failed for file=%s", safe_name)
            raise HTTPException(status_code=400, detail=f"Invalid CSV format for {safe_name}: {exc}") from exc

        missing_columns = validate_columns(df)
        if missing_columns:
            logger.warning("Validation failed for file=%s missing_columns=%s", safe_name, missing_columns)
            raise HTTPException(
                status_code=422,
                detail={
                    "file": safe_name,
                    "message": "Missing required columns.",
                    "missing_columns": missing_columns,
                },
            )

        try:
            final_df, metrics = process_dataframe(df)
        except Exception as exc:
            logger.exception("Processing failed for file=%s", safe_name)
            raise HTTPException(status_code=500, detail=f"Failed to process {safe_name}: {exc}") from exc

        output_name = f"processed-{unique_prefix}-{safe_name}"
        output_path = OUTPUT_DIR / output_name

        try:
            final_df.to_csv(output_path, index=False)
        except Exception as exc:
            logger.exception("Output write failed for file=%s", safe_name)
            raise HTTPException(status_code=500, detail=f"Could not write output for {safe_name}: {exc}") from exc

        elapsed_ms = round((time.time() - started) * 1000, 2)
        result = {
            "input_file": safe_name,
            "output_file": output_name,
            "download_url": f"/api/download/{output_name}",
            "size_bytes": len(content),
            "elapsed_ms": elapsed_ms,
            **metrics,
        }
        results.append(result)

        logger.info(
            "File processed successfully file=%s output=%s rows_in=%s rows_out=%s elapsed_ms=%s",
            safe_name,
            output_name,
            metrics["input_rows"],
            metrics["output_rows"],
            elapsed_ms,
        )

    totals = {
        "files_processed": len(results),
        "total_headers": sum(item["header_count"] for item in results),
        "total_lumpsum": sum(item["lumpsum_count"] for item in results),
        "total_output_rows": sum(item["output_rows"] for item in results),
    }

    return {"results": results, "totals": totals}


@app.get("/api/download/{filename}")
def download(filename: str):
    from fastapi.responses import FileResponse

    safe = sanitize_filename(filename)
    path = OUTPUT_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="text/csv", filename=safe)
