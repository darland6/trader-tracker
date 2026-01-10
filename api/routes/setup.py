"""Setup and initialization API for portfolio dashboard.

Handles first-time setup, demo mode, and database initialization.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
import shutil
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.demo_data import (
    create_demo_database,
    get_demo_status,
    DEMO_DB_PATH,
    DEMO_CSV_PATH,
    SCRIPT_DIR
)
from api.database import init_database, sync_csv_to_db, DB_PATH, CSV_PATH

router = APIRouter(prefix="/api/setup", tags=["setup"])


class SetupStatus(BaseModel):
    has_real_db: bool
    has_real_csv: bool
    has_demo_db: bool
    is_demo_mode: bool
    needs_setup: bool
    mode: str  # 'real', 'demo', or 'none'


class InitRequest(BaseModel):
    mode: str  # 'demo', 'fresh', or 'upload'
    starting_cash: float = 50000


@router.get("/status", response_model=SetupStatus)
async def get_setup_status():
    """Check current database/setup status."""
    from pathlib import Path

    # Check for actual data files
    real_csv = SCRIPT_DIR / 'event_log_enhanced.csv'
    real_db = SCRIPT_DIR / 'portfolio.db'

    has_real_csv = real_csv.exists()
    has_real_db = real_db.exists()
    has_demo_db = DEMO_DB_PATH.exists()

    # Check if CSV has actual data (not just headers)
    csv_has_data = False
    if has_real_csv:
        try:
            import pandas as pd
            df = pd.read_csv(real_csv)
            csv_has_data = len(df) > 0
        except:
            csv_has_data = False

    # Determine current mode
    if csv_has_data:
        mode = 'real'
        needs_setup = False
    elif has_demo_db:
        mode = 'demo'
        needs_setup = False
    else:
        mode = 'none'
        needs_setup = True

    # Check if running demo data
    is_demo = False
    if csv_has_data:
        try:
            import pandas as pd
            df = pd.read_csv(real_csv, nrows=1)
            if len(df) > 0:
                data_json = df.iloc[0].get('data_json', '')
                notes = df.iloc[0].get('notes', '')
                if 'is_demo' in str(data_json) or 'DEMO MODE' in str(notes):
                    is_demo = True
        except:
            pass

    return SetupStatus(
        has_real_db=has_real_db,
        has_real_csv=has_real_csv and csv_has_data,
        has_demo_db=has_demo_db,
        is_demo_mode=is_demo,
        needs_setup=needs_setup,
        mode=mode
    )


@router.post("/init-demo")
async def initialize_demo_mode():
    """Initialize the application in demo mode with sample data."""
    try:
        # Create demo database with 6 months of fake data
        db_path = create_demo_database()

        # Copy demo files to main locations for the app to use
        if DEMO_DB_PATH.exists():
            shutil.copy(DEMO_DB_PATH, DB_PATH)
        if DEMO_CSV_PATH.exists():
            shutil.copy(DEMO_CSV_PATH, CSV_PATH)

        # Re-sync to ensure everything is loaded
        sync_csv_to_db()

        return {
            "success": True,
            "message": "Demo mode initialized with 6 months of sample data",
            "mode": "demo"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize demo: {str(e)}")


@router.post("/init-fresh")
async def initialize_fresh_database(request: InitRequest):
    """Initialize a fresh empty database with optional starting cash."""
    try:
        import pandas as pd
        from datetime import datetime

        # Create empty CSV with just an initial deposit if starting_cash > 0
        events = []
        if request.starting_cash > 0:
            events.append({
                'event_id': 1,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'event_type': 'DEPOSIT',
                'data_json': json.dumps({
                    'amount': request.starting_cash,
                    'source': 'Initial funding'
                }),
                'reason_json': json.dumps({
                    'primary': 'INITIAL_FUNDING',
                    'explanation': 'Starting portfolio capital'
                }),
                'notes': 'Initial portfolio funding',
                'tags_json': json.dumps(['cash', 'deposit', 'initial']),
                'affects_cash': True,
                'cash_delta': request.starting_cash
            })

        df = pd.DataFrame(events) if events else pd.DataFrame(columns=[
            'event_id', 'timestamp', 'event_type', 'data_json',
            'reason_json', 'notes', 'tags_json', 'affects_cash', 'cash_delta'
        ])

        # Save CSV
        df.to_csv(CSV_PATH, index=False)

        # Initialize and sync database
        init_database()
        sync_csv_to_db()

        return {
            "success": True,
            "message": f"Fresh database initialized with ${request.starting_cash:,.0f} starting cash",
            "mode": "real"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize: {str(e)}")


@router.post("/upload-csv")
async def upload_existing_csv(file: UploadFile = File(...)):
    """Upload an existing event log CSV file."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Save uploaded file
        content = await file.read()
        with open(CSV_PATH, 'wb') as f:
            f.write(content)

        # Validate CSV structure
        import pandas as pd
        df = pd.read_csv(CSV_PATH)

        required_columns = ['event_id', 'timestamp', 'event_type', 'data_json']
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            # Remove invalid file
            CSV_PATH.unlink()
            raise HTTPException(
                status_code=400,
                detail=f"CSV missing required columns: {', '.join(missing)}"
            )

        # Initialize and sync database
        init_database()
        event_count = sync_csv_to_db()

        return {
            "success": True,
            "message": f"Loaded {event_count} events from uploaded CSV",
            "mode": "real",
            "event_count": event_count
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload: {str(e)}")


@router.post("/exit-demo")
async def exit_demo_mode():
    """Exit demo mode and clear demo data."""
    try:
        # Remove demo files
        if DEMO_DB_PATH.exists():
            DEMO_DB_PATH.unlink()
        if DEMO_CSV_PATH.exists():
            DEMO_CSV_PATH.unlink()

        # Also remove the copied files if they were demo
        # Check if current DB is demo by looking for demo markers
        if DB_PATH.exists():
            DB_PATH.unlink()
        if CSV_PATH.exists():
            CSV_PATH.unlink()

        return {
            "success": True,
            "message": "Demo mode exited. Please initialize or upload data.",
            "needs_setup": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to exit demo: {str(e)}")


@router.get("/is-demo")
async def check_demo_mode():
    """Quick check if running in demo mode (for UI branding)."""
    status = get_demo_status()

    # Check if we're using demo data
    # We consider it demo mode if:
    # 1. Demo DB exists and no real CSV exists, OR
    # 2. The CSV was generated by demo (check for demo markers)
    is_demo = False

    if status['has_demo_db'] and not status['has_real_csv']:
        is_demo = True
    elif CSV_PATH.exists():
        try:
            import pandas as pd
            df = pd.read_csv(CSV_PATH, nrows=5)
            # Check for demo markers in the data
            if not df.empty:
                first_notes = df.iloc[0].get('notes', '')
                if 'Demo portfolio' in str(first_notes) or 'demo-' in str(df.iloc[0].get('data_json', '')):
                    is_demo = True
        except:
            pass

    return {
        "is_demo": is_demo,
        "mode": "demo" if is_demo else "real" if status['has_real_db'] or status['has_real_csv'] else "none"
    }
