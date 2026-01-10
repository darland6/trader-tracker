"""Backup and restore routes for the event log."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime
from pathlib import Path
import shutil
import json
import os

router = APIRouter(prefix="/api/backup", tags=["backup"])

SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()
EVENT_LOG = SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'
BACKUP_DIR = SCRIPT_DIR / 'backups'


def ensure_backup_dir():
    """Ensure backup directory exists."""
    BACKUP_DIR.mkdir(exist_ok=True)


@router.get("/list")
async def list_backups():
    """List all available backups."""
    ensure_backup_dir()

    backups = []
    for f in BACKUP_DIR.glob("event_log_*.csv"):
        stat = f.stat()
        backups.append({
            "filename": f.name,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "size_kb": round(stat.st_size / 1024, 1)
        })

    # Sort by creation time, newest first
    backups.sort(key=lambda x: x['created'], reverse=True)

    return {"backups": backups}


@router.post("/create")
async def create_backup():
    """Create a new backup of the current event log."""
    ensure_backup_dir()

    if not EVENT_LOG.exists():
        raise HTTPException(status_code=404, detail="Event log not found")

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"event_log_{timestamp}.csv"
    backup_path = BACKUP_DIR / backup_name

    try:
        shutil.copy2(EVENT_LOG, backup_path)

        # Get file size
        size = backup_path.stat().st_size

        return {
            "success": True,
            "message": f"Backup created: {backup_name}",
            "filename": backup_name,
            "size_kb": round(size / 1024, 1)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{filename}")
async def download_backup(filename: str):
    """Download a specific backup file."""
    # Validate filename to prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    backup_path = BACKUP_DIR / filename

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")

    return FileResponse(
        path=str(backup_path),
        filename=filename,
        media_type="text/csv"
    )


@router.get("/download-current")
async def download_current():
    """Download the current event log."""
    if not EVENT_LOG.exists():
        raise HTTPException(status_code=404, detail="Event log not found")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return FileResponse(
        path=str(EVENT_LOG),
        filename=f"event_log_current_{timestamp}.csv",
        media_type="text/csv"
    )


@router.post("/restore/{filename}")
async def restore_backup(filename: str):
    """Restore from a specific backup file."""
    # Validate filename
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    backup_path = BACKUP_DIR / filename

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")

    try:
        # Create a backup of current before restoring
        if EVENT_LOG.exists():
            ensure_backup_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_restore_backup = BACKUP_DIR / f"event_log_pre_restore_{timestamp}.csv"
            shutil.copy2(EVENT_LOG, pre_restore_backup)

        # Restore from backup
        shutil.copy2(backup_path, EVENT_LOG)

        # Sync to database
        from api.database import sync_csv_to_db
        sync_csv_to_db()

        return {
            "success": True,
            "message": f"Restored from {filename}",
            "restored_from": filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_backup(file: UploadFile = File(...)):
    """Upload and restore from a backup file."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Read uploaded content
        content = await file.read()

        # Validate it looks like a valid event log (has expected headers)
        first_line = content.decode('utf-8').split('\n')[0]
        expected_headers = ['event_id', 'timestamp', 'event_type', 'data_json']
        if not all(h in first_line for h in expected_headers):
            raise HTTPException(status_code=400, detail="Invalid event log format")

        # Backup current before restoring
        if EVENT_LOG.exists():
            ensure_backup_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_restore_backup = BACKUP_DIR / f"event_log_pre_upload_{timestamp}.csv"
            shutil.copy2(EVENT_LOG, pre_restore_backup)

        # Write uploaded content to event log
        with open(EVENT_LOG, 'wb') as f:
            f.write(content)

        # Sync to database
        from api.database import sync_csv_to_db
        sync_csv_to_db()

        return {
            "success": True,
            "message": "Uploaded and restored successfully",
            "filename": file.filename
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{filename}")
async def delete_backup(filename: str):
    """Delete a specific backup file."""
    # Validate filename
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    backup_path = BACKUP_DIR / filename

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")

    try:
        os.remove(backup_path)
        return {"success": True, "message": f"Deleted {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
