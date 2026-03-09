import json
import os
import time
from datetime import datetime
import threading

class SwanLiveManager:
    def __init__(self):
        self.file_path = "/home/node/clawd/skills/black-swan-hunter/live_data.json"
        self.lock = threading.Lock()
        self.meta = {"engine_status": "running", "last_scan_ts": 0, "candidate_count": 0}
        self.hunts = []
        self.liquidation_map = {}
        self.logs = []

    def sync_data(self, final_hunts, final_map):
        with self.lock:
            self.hunts = final_hunts
            self.liquidation_map = final_map
            self.meta["candidate_count"] = len(final_hunts)
            self.meta["last_scan_ts"] = int(time.time() * 1000)
            self._atomic_sync_handshake()

    def _atomic_sync_handshake(self):
        """镜像双文件握手逻辑：先写影子文件，再发信号灯"""
        try:
            data = {
                "meta": self.meta,
                "hunts": self.hunts,
                "liquidation_map": self.liquidation_map,
                "logs": self.logs[:30]
            }
            # 1. 写入影子文件
            shadow_path = f"{self.file_path}.new"
            with open(shadow_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # 2. 产生信号灯文件 (内容无关，仅作存在性证明)
            ready_flag = "/home/node/clawd/skills/black-swan-hunter/sync.ready"
            with open(ready_flag, "w") as f:
                f.write(str(time.time()))
                f.flush()
                os.fsync(f.fileno())
            
            # 3. 闭环同步：引擎直接完成物理覆盖，不依赖外部消费者
            import shutil
            shutil.copy2(shadow_path, self.file_path)
                
            print(f"Handshake: Data ready in {shadow_path}, and physically synced to {self.file_path}")
        except Exception as e:
            print(f"Handshake Error: {e}")

    def add_log(self, line):
        with self.lock:
            self.logs.insert(0, {"line": f"[{datetime.now().strftime('%H:%M:%S')}] {line}", "ts": int(time.time() * 1000)})
        # 日志变动不强制触发全量握手，仅在 sync_data 时触发，节省同步资源

live_manager = SwanLiveManager()
