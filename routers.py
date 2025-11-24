from fastapi import APIRouter, Query, HTTPException
from datetime import datetime
from typing import Optional
from data_fetcher import HurricaneDataFetcher
from data_fetcher import dataframe_to_records

router = APIRouter()


@router.get("/data")
def get_data(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    force: bool = Query(False, description="Force re-download even if cached")
) -> dict:
    """Get hurricane data for a specific date"""
    try:
        fetcher = HurricaneDataFetcher()
        
        df = fetcher.download_hurricane_data(date, force_download=force)
        if df is None:
            records = []
        else:
            records = dataframe_to_records(df)
        meta = {
            'date': date,
            'record_count': len(records),
            'source': 'local_or_remote',
            'cached': not force,
        }
        result =  {'meta': meta, 'records': records}

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
