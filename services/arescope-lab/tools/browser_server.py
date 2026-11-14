"""Isolated local server used only by the browser QA runner."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from app import Settings, create_app

runtime = Path(sys.argv[1]).resolve()
settings = Settings(producer_token="test-producer", viewer_token="test-viewer",
    db=runtime / "live.sqlite3", mesh_dir=runtime / "meshes", log_dir=runtime / "logs",
    min_history_interval=0)
uvicorn.run(create_app(settings), host="127.0.0.1", port=18965, access_log=False, log_level="warning")
