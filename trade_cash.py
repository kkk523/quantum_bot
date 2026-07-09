import sys
from toss_api import TossAPIClient
from config import TARGET_WEIGHTS
from notifier import send_notification

def execute_smart_trade(action: str, amount: float):
    api = TossAPIClient()
    tickers = list(TARGET_WEIGHTS.keys())
    
    positions = api.get_my_positions()
    current_prices = api.get_current_prices(tickers)
    
    if not current_prices:
        print("🚨 가격 정보를 불러올 수 없습니다.")
        return

    # 1. 현재 주식 평가금 계산
    holdings = {}
    stock_value = 0.0
    for t in tickers:
        qty = positions.get(t, {"qty": 0})["qty"]
        price = current_prices.get(t, 0)
        value = qty * price
        stock_value += value
        holdings[t] = {"qty": qty, "price": price, "value": value}

    print(f"🔹 현재 총 주식 평가액: ${stock_value:,.2f}")
    
    orders = []
    
    if action == "buy":
        account = api.get_account_balance()
        if account["cash_usd"] < amount:
            msg = f"🚨 매수 불가: 토스 계좌의 달러 예수금(${account['cash_usd']:,.2f})이 매수 희망 금액(${amount:,.2f})보다 부족합니다."
            print(msg)
            send_notification(msg)
            return
            
        target_total = stock_value + amount
        print(f"🔹 매수 후 예상 주식 평가액: ${target_total:,.2f}")
        
        # 부족분(Shortfall) 계산
        shortfalls = {}
        total_positive_shortfall = 0.0
        
        for t, weight in TARGET_WEIGHTS.items():
            target_value = target_total * weight
            current_value = holdings[t]["value"]
            diff = target_value - current_value
            if diff > 0:
                shortfalls[t] = diff
                total_positive_shortfall += diff
                
        # 배분 로직
        report_lines = [f"📥 [추가 투자 {amount}달러 매수 내역]"]
        for t, weight in TARGET_WEIGHTS.items():
            # 모두 비중이 초과상태(혹은 완벽)라면 그냥 목표 비중대로 쪼갬
            if total_positive_shortfall == 0:
                allocated_cash = amount * weight
            else:
                # 부족한 종목들에만 집중 배분
                if t in shortfalls:
                    allocated_cash = amount * (shortfalls[t] / total_positive_shortfall)
                else:
                    allocated_cash = 0
                    
            if allocated_cash > 0:
                qty_to_buy = int(allocated_cash / holdings[t]["price"])
                if qty_to_buy > 0:
                    trade_amount = qty_to_buy * holdings[t]["price"]
                    orders.append({"ticker": t, "side": "buy", "qty": qty_to_buy, "trade_amount": trade_amount})
                    report_lines.append(f"🟢 {t}: {qty_to_buy}주 매수 (할당액: ${trade_amount:,.2f})")
                    
    elif action == "sell":
        if amount > stock_value:
            print("🚨 매도 금액이 현재 주식 평가액보다 큽니다!")
            return
            
        target_total = stock_value - amount
        print(f"🔹 매도 후 예상 주식 평가액: ${target_total:,.2f}")
        
        # 초과분(Surplus) 계산
        surpluses = {}
        total_positive_surplus = 0.0
        
        for t, weight in TARGET_WEIGHTS.items():
            target_value = target_total * weight
            current_value = holdings[t]["value"]
            diff = current_value - target_value
            if diff > 0:
                surpluses[t] = diff
                total_positive_surplus += diff
                
        # 배분 로직
        report_lines = [f"📤 [부분 매도 {amount}달러 내역]"]
        for t, weight in TARGET_WEIGHTS.items():
            if total_positive_surplus == 0:
                extracted_cash = amount * weight
            else:
                if t in surpluses:
                    extracted_cash = amount * (surpluses[t] / total_positive_surplus)
                else:
                    extracted_cash = 0
                    
            if extracted_cash > 0:
                qty_to_sell = int(extracted_cash / holdings[t]["price"])
                if qty_to_sell > 0:
                    trade_amount = qty_to_sell * holdings[t]["price"]
                    orders.append({"ticker": t, "side": "sell", "qty": qty_to_sell, "trade_amount": trade_amount})
                    report_lines.append(f"🔴 {t}: {qty_to_sell}주 매도 (회수액: ${trade_amount:,.2f})")
    
    if not orders:
        print("💡 체결할 주문(1주 미만)이 없습니다.")
        return
        
    # 실제 주문 실행
    success_count = 0
    for o in orders:
        if api.place_order(o["ticker"], o["side"], o["qty"]):
            success_count += 1
            print(f"[{o['side'].upper()}] {o['ticker']} {o['qty']}주 체결 성공")
        else:
            report_lines.append(f"❌ {o['ticker']} {o['qty']}주 {o['side']} 실패 (API 주문 거절)")
            print(f"[{o['side'].upper()}] {o['ticker']} {o['qty']}주 체결 실패")
            
    if success_count > 0:
        report_lines.append("✅ 스마트 매매 분배 및 주문이 완료되었습니다.")
        
    # 텔레그램 알림 전송
    msg = "\n".join(report_lines)
    send_notification(msg)
    print("✅ 모든 처리가 완료되었습니다.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python3 trade_cash.py [buy/sell] [금액]")
        print("예시: python3 trade_cash.py buy 200")
        sys.exit(1)
        
    action_arg = sys.argv[1].lower()
    if action_arg not in ["buy", "sell"]:
        print("🚨 'buy' 또는 'sell' 만 입력 가능합니다.")
        sys.exit(1)
        
    try:
        amount_arg = float(sys.argv[2])
    except ValueError:
        print("🚨 금액은 숫자로 입력해주세요.")
        sys.exit(1)
        
    if amount_arg <= 0:
        print("🚨 금액은 0보다 커야 합니다.")
        sys.exit(1)
        
    execute_smart_trade(action_arg, amount_arg)
