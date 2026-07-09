from toss_api import TossAPIClient
from config import TARGET_WEIGHTS, REBALANCE_THRESHOLD
from notifier import send_notification
from wallet import get_virtual_cash, add_virtual_cash, subtract_virtual_cash, set_virtual_cash

class PortfolioRebalancer:
    def __init__(self):
        self.api = TossAPIClient()
        self.target_weights = TARGET_WEIGHTS
        self.threshold = REBALANCE_THRESHOLD
        
    def check_and_rebalance(self):
        print("=== 포트폴리오 자동 리밸런싱 시작 ===")
        positions = self.api.get_my_positions()
        tickers = list(self.target_weights.keys())
        current_prices = self.api.get_current_prices(tickers)
        
        if not current_prices:
            print("🚨 시세 정보를 가져오지 못했습니다. API 키 설정 또는 네트워크 상태를 확인하세요.")
            return
            
        virtual_cash = get_virtual_cash()
        
        stock_value = 0.0
        holdings = {}
        
        for t in tickers:
            pos = positions.get(t, {"qty": 0})
            qty = pos["qty"]
            price = current_prices.get(t, 0)
            value = qty * price
            stock_value += value
            holdings[t] = {"qty": qty, "price": price, "value": value}
            
        total_quantum_value = stock_value + virtual_cash
        print(f"양자 펀드 총 자산: ${total_quantum_value:,.2f} (투자금: ${stock_value:,.2f}, 대기 현금: ${virtual_cash:,.2f})")
        
        status_lines = [f"💰 양자 펀드 총 자산: ${total_quantum_value:,.2f} (투자금: ${stock_value:,.2f}, 가상 지갑: ${virtual_cash:,.2f})", "-" * 20]
        needs_rebalance = False
        deviations = []
        
        for ticker, target_w in self.target_weights.items():
            current_value = holdings[ticker]["value"]
            current_w = current_value / total_quantum_value if total_quantum_value > 0 else 0
            diff = current_w - target_w
            
            deviations.append({
                "ticker": ticker,
                "current_w": current_w,
                "target_w": target_w,
                "diff": diff,
                "price": holdings[ticker]["price"],
                "qty": holdings[ticker]["qty"]
            })
            
            status_lines.append(f"{ticker}: {current_w*100:.1f}% (목표 {target_w*100:.1f}%)")
            
        # 가상 지갑 잔액 표시
        cash_w = virtual_cash / total_quantum_value if total_quantum_value > 0 else 0
        status_lines.append(f"가상 지갑 대기 현금: {cash_w*100:.1f}% (목표 0.0%)")
            
        for dev in deviations:
            if abs(dev["diff"]) >= self.threshold:
                needs_rebalance = True
                
        status_text = "\n".join(status_lines)
                
        if not needs_rebalance:
            print("리밸런싱이 필요하지 않습니다. (임계값 이내)")
            send_notification(f"🔄 자정 포트폴리오 점검 🔄\n\n{status_text}\n\n✅ 모든 종목이 목표 비중(오차 5% 이내)을 유지하고 있어 리밸런싱을 생략합니다.")
            return
            
        send_notification(f"🚨 포트폴리오 비중 이탈 감지 🚨\n\n{status_text}\n\n자동 리밸런싱 계산 및 주문을 시작합니다.")
        
        sell_orders = []
        buy_orders = []
        
        for item in deviations:
            target_value = total_quantum_value * item["target_w"]
            value_diff = target_value - (item["qty"] * item["price"])
            qty_diff = round(value_diff / item["price"])
            
            if qty_diff < 0:
                sell_orders.append({"ticker": item["ticker"], "qty": abs(qty_diff), "price": item["price"]})
            elif qty_diff > 0:
                buy_orders.append({"ticker": item["ticker"], "qty": qty_diff, "price": item["price"], "diff_pct": item["diff"]})

        report_lines = ["🔄 [리밸런싱 주문 완료 상세 내역]"]
        
        available_cash = virtual_cash
        for o in sell_orders:
            if self.api.place_order(o["ticker"], "sell", o["qty"]):
                sold_amount = o["qty"] * o["price"]
                add_virtual_cash(sold_amount)
                available_cash += sold_amount
                report_lines.append(f"✅ {o['ticker']} {o['qty']}주 매도 (확보: ${sold_amount:,.2f})")
            else:
                report_lines.append(f"❌ {o['ticker']} {o['qty']}주 매도 실패 (API 주문 거절)")

        real_account = self.api.get_account_balance()
        if real_account is None:
            report_lines.append("\n❌ [치명적 오류] 토스증권 API 통신 장애로 계좌 잔고 조회를 실패했습니다.")
            report_lines.append("⚠️ 안전을 위해 가상 지갑 자가 치유 및 매수(리밸런싱)를 전면 중단합니다. (매도는 정상 처리됨)")
            send_notification("\n".join(report_lines))
            print("=== 리밸런싱 중단 (잔고 API 에러) ===")
            return

        real_cash = real_account.get("cash_usd", 0.0)
        
        if available_cash > real_cash:
            report_lines.append(f"\n⚠️ 장부상 현금(${available_cash:,.2f})이 실제 토스 잔고(${real_cash:,.2f})보다 큽니다. 잔고에 맞춰 장부를 삭감 조정합니다. (외부 출금 등 반영)")
            available_cash = real_cash
            set_virtual_cash(real_cash)

        buy_orders.sort(key=lambda x: x["diff_pct"])
        
        for o in buy_orders:
            ticker = o["ticker"]
            price = o["price"]
            ideal_qty = o["qty"]
            
            max_affordable_qty = int(available_cash / price)
            actual_qty = min(ideal_qty, max_affordable_qty)
            
            if actual_qty > 0:
                if self.api.place_order(ticker, "buy", actual_qty):
                    bought_amount = actual_qty * price
                    subtract_virtual_cash(bought_amount)
                    available_cash -= bought_amount
                    report_lines.append(f"✅ {ticker} {actual_qty}주 매수 (소진: ${bought_amount:,.2f})")
                    
                    if actual_qty < ideal_qty:
                        shortfall = ideal_qty - actual_qty
                        report_lines.append(f"⚠️ {ticker} {shortfall}주 매수 보류 (장부 현금 부족 - 필요: ${shortfall * price:,.2f}, 잔액: ${available_cash:,.2f})")
                else:
                    report_lines.append(f"❌ {ticker} {actual_qty}주 매수 실패 (API 주문 거절)")
            else:
                report_lines.append(f"❌ {ticker} {ideal_qty}주 매수 실패 (장부 현금 부족 - 필요: ${ideal_qty * price:,.2f}, 잔액: ${available_cash:,.2f})")
                
        if not sell_orders and not buy_orders:
            report_lines.append("수량 계산 결과 매매할 내역이 없습니다.")
            
        final_virtual_cash = get_virtual_cash()
        report_lines.append(f"\n💵 리밸런싱 후 가상 지갑 잔액: ${final_virtual_cash:,.2f}")
            
        send_notification("\n".join(report_lines))
        print("=== 리밸런싱 완료 ===")
