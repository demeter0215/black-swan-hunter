import json
import threading
from pathlib import Path
from typing import Dict, List, Optional


class LiveDataBridge:
    def __init__(self, output_path: Optional[str] = None, max_items: int = 200) -> None:
        default_path = Path(__file__).resolve().parent / "live_data.json"
        self.output_path = Path(output_path) if output_path else default_path
        self.max_items = max_items
        self.lock = threading.Lock()
        self.state: Dict[str, List[dict]] = {
            "liquidations": [],
            "hunts": [],
            "logs": [],
        }

    def _trim(self) -> None:
        self.state["liquidations"] = self.state["liquidations"][: self.max_items]
        self.state["hunts"] = self.state["hunts"][: self.max_items]
        self.state["logs"] = self.state["logs"][: self.max_items]

    def append_liquidation(self, item: dict) -> None:
        with self.lock:
            self.state["liquidations"].insert(0, item)
            self._trim()
            self.persist()

    def append_hunt(self, item: dict) -> None:
        with self.lock:
            self.state["hunts"].insert(0, item)
            self._trim()
            self.persist()

    def append_log(self, line: str) -> None:
        with self.lock:
            self.state["logs"].insert(0, {"line": line})
            self._trim()
            self.persist()

    def get_recent_liquidations(self, symbol: Optional[str] = None, limit: int = 50) -> List[dict]:
        with self.lock:
            items = self.state["liquidations"]
            if symbol:
                items = [x for x in items if x.get("symbol") == symbol]
            return items[:limit]

    def persist(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(
            json.dumps(self.state, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )


DEFAULT_BRIDGE = LiveDataBridge()
