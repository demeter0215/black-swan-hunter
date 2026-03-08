import json
import subprocess
import sys
import os
import requests

# 确保能加载到同目录下的 hunter.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import hunter
except ImportError as e:
    print(f"Error loading hunter.py: {e}")
    sys.exit(1)

def main():
    # 实例化最新的 V5 引擎 (不再使用 adapter 参数)
    v5_engine = hunter.BlackSwanHunterV5()
    
    if len(sys.argv) < 2:
        print("Usage: python3 boot_hunter.py [scan_v5|hunt_v5] [args...]")
        return

    command = sys.argv[1]
    
    if command == "hunt_v5":
        # 兼容旧调用格式或 CLI 直接调用
        symbol = sys.argv[2].upper()
        funding_rate = 0.0
        # 查找命令行中的 --funding-rate
        for i, arg in enumerate(sys.argv):
            if arg == "--funding-rate" and i+1 < len(sys.argv):
                funding_rate = float(sys.argv[i+1])
        
        result = v5_engine.hunt_v5(symbol=symbol, funding_rate=funding_rate)
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
