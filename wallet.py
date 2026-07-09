import json
import os
from datetime import datetime

WALLET_FILE = "quantum_wallet.json"

def get_virtual_cash() -> float:
    """가상 지갑의 대기 현금을 조회합니다."""
    if not os.path.exists(WALLET_FILE):
        return 0.0
    try:
        with open(WALLET_FILE, "r") as f:
            data = json.load(f)
            return float(data.get("virtual_cash", 0.0))
    except Exception:
        return 0.0

def set_virtual_cash(amount: float):
    """가상 지갑의 금액을 덮어씁니다."""
    data = {}
    if os.path.exists(WALLET_FILE):
        try:
            with open(WALLET_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            pass
            
    data["virtual_cash"] = amount
    data["last_updated"] = datetime.now().isoformat()
    
    with open(WALLET_FILE, "w") as f:
        json.dump(data, f, indent=4)

def add_virtual_cash(amount: float):
    """매도 등 수익금을 가상 지갑에 추가합니다."""
    if amount <= 0: return
    current_cash = get_virtual_cash()
    set_virtual_cash(current_cash + amount)

def subtract_virtual_cash(amount: float):
    """매수 등 비용 지출 시 가상 지갑에서 차감합니다."""
    if amount <= 0: return
    current_cash = get_virtual_cash()
    new_cash = max(0.0, current_cash - amount) # 마이너스 통장 방지
    set_virtual_cash(new_cash)
