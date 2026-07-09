import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
import math
from datetime import datetime, timedelta
from toss_api import TossAPIClient
from notifier import send_notification
from wallet import get_virtual_cash
from config import TARGET_WEIGHTS
from market_calendar import is_us_market_open, is_kr_market_open

class MarketBriefer:
    def __init__(self):
        self.api = TossAPIClient()
        self.tickers = list(TARGET_WEIGHTS.keys())
        self.alert_history = {} # 종목별 당일 알림 발송 기록 저장

    def get_latest_news(self, market: str) -> list:
        """구글 뉴스 RSS를 통해 시황 및 양자 뉴스를 가져옵니다."""
        market_keyword = "국내 증시 마감 시황" if market == "KR" else "미국 증시 시황"
        quantum_keyword = "양자컴퓨터 기술 주식"
        
        news_list = []
        
        def fetch_news(keyword, limit):
            query = f"{keyword} when:1d"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            try:
                with urllib.request.urlopen(req) as response:
                    root = ET.fromstring(response.read())
                    for item in root.findall('.//item')[:limit]:
                        title = item.find('title').text if item.find('title') is not None else ""
                        link = item.find('link').text if item.find('link') is not None else ""
                        news_list.append(f"📰 [{title}]({link})")
            except Exception as e:
                pass
                
        fetch_news(market_keyword, 2)
        fetch_news(quantum_keyword, 2)
        
        if not news_list:
            news_list.append("뉴스를 불러오지 못했습니다.")
            
        return news_list

    def get_market_indices(self, market: str) -> str:
        """야후 파이낸스를 통해 시장 지수(KOSPI/KOSDAQ 또는 S&P500/NASDAQ)를 가져옵니다."""
        if market == "KR":
            tickers = {"코스피": "^KS11", "코스닥": "^KQ11", "원달러 환율": "KRW=X"}
        else:
            tickers = {"S&P 500": "^GSPC", "나스닥": "^IXIC", "원달러 환율": "KRW=X"}
            
        result_lines = []
        for name, ticker in tickers.items():
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            try:
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read())
                    meta = data['chart']['result'][0]['meta']
                    price = float(meta['regularMarketPrice'])
                    prev_close = float(meta['chartPreviousClose'])
                    diff = price - prev_close
                    pct_change = (diff / prev_close) * 100
                    
                    sign_pct = "+" if pct_change > 0 else ""
                    sign_diff = "▲" if diff > 0 else ("▼" if diff < 0 else "")
                    icon = "🔴" if diff > 0 else ("🔵" if diff < 0 else "⚫")
                    
                    unit = "원" if name == "원달러 환율" else ""
                    result_lines.append(f"{icon} {name}: {price:,.2f}{unit} ({sign_diff}{abs(diff):.2f}, {sign_pct}{pct_change:.2f}%)")
            except Exception as e:
                print(f"Index fetch error for {name} ({ticker}): {e}")
                
        if not result_lines:
            return "지수 정보를 불러올 수 없습니다."
        return "\n".join(result_lines)

    def analyze_and_recommend(self, symbol: str, avg_price: float, current_price: float) -> tuple:
        """4대 기술적 지표와 평단가를 종합하여 월가 수준의 스코어를 계산합니다."""
        candles = self.api.get_candles(symbol, count=100)
        if len(candles) < 50:
            return 0, f"현재가 ${current_price:.2f} | 지표 계산 불가 (데이터 부족)"
            
        prices = [float(c.get('closePrice', 0)) for c in candles]
        prices.reverse() # [과거, ..., 최신]
        
        if current_price == 0.0:
            current_price = prices[-1]
            
        score = 0
        
        # 1. 다중 이동평균선 (최대 10점)
        ma5 = sum(prices[-5:]) / 5 if len(prices) >= 5 else current_price
        ma20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else current_price
        ma50 = sum(prices[-50:]) / 50 if len(prices) >= 50 else current_price
        
        if ma5 > ma20 > ma50: score += 10 # 완벽한 정배열
        elif ma5 > ma20: score += 5
        elif ma5 < ma20 < ma50: score -= 10 # 완벽한 역배열
        elif ma5 < ma20: score -= 5
        
        # 2. 볼린저 밴드 (최대 20점)
        bb_period = 20
        bb_prices = prices[-bb_period:]
        bb_sma = sum(bb_prices) / bb_period
        variance = sum((p - bb_sma) ** 2 for p in bb_prices) / bb_period
        std_dev = math.sqrt(variance)
        upper_band = bb_sma + (std_dev * 2)
        lower_band = bb_sma - (std_dev * 2)
        
        bb_status = "밴드 내 위치"
        if current_price > upper_band: 
            score -= 20
            bb_status = "상단 돌파 (과열)"
        elif current_price < lower_band: 
            score += 20
            bb_status = "하단 돌파 (낙폭 과대)"
            
        # EMA 계산 헬퍼 함수
        def calculate_ema(data, period):
            k = 2 / (period + 1)
            ema = [sum(data[:period]) / period]
            for price in data[period:]:
                ema.append((price - ema[-1]) * k + ema[-1])
            return ema
            
        # 3. MACD (최대 20점)
        if len(prices) >= 26:
            ema12 = calculate_ema(prices, 12)
            ema26 = calculate_ema(prices, 26)
            macd_line = [e12 - e26 for e12, e26 in zip(ema12[-len(ema26):], ema26)]
            signal_line = calculate_ema(macd_line, 9)
            
            curr_macd = macd_line[-1]
            curr_signal = signal_line[-1]
            prev_macd = macd_line[-2] if len(macd_line) > 1 else curr_macd
            prev_signal = signal_line[-2] if len(signal_line) > 1 else curr_signal
            
            macd_status = "약세 (MACD < Signal)"
            if curr_macd > curr_signal:
                score += 10
                macd_status = "강세 (MACD > Signal)"
                if prev_macd <= prev_signal: # 골든크로스 발생
                    score += 10
                    macd_status = "🔥 매수 시그널 (골든크로스)"
            else:
                score -= 10
                if prev_macd >= prev_signal: # 데드크로스 발생
                    score -= 10
                    macd_status = "❄️ 매도 시그널 (데드크로스)"
        else:
            macd_status = "데이터 부족"
        
        # 4. RSI (최대 20점)
        period = 14
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        rsi = 50.0
        if avg_loss > 0:
            for i in range(period, len(deltas)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            else: rsi = 100.0
        else: rsi = 100.0
            
        rsi_status = "중립"
        if rsi < 30: 
            score += 20
            rsi_status = "과매도 (Oversold)"
        elif rsi < 40: 
            score += 10
            rsi_status = "하락 진정"
        elif rsi > 70: 
            score -= 20
            rsi_status = "과매수 (Overbought)"
        elif rsi > 60: 
            score -= 10
            rsi_status = "과열 징후"
            
        # 5. 내 평단가 대비 수익률 점수 (최대 30점)
        pnl_pct = 0.0
        pnl_text = "미보유"
        if avg_price > 0:
            pnl_pct = ((current_price - avg_price) / avg_price) * 100
            pnl_text = f"{pnl_pct:+.1f}%"
            if pnl_pct <= -20: score += 30 # 낙폭 과대, 물타기 추천
            elif pnl_pct <= -10: score += 15
            elif pnl_pct >= 20: score -= 30 # 수익 실현 구간
            elif pnl_pct >= 10: score -= 15
            
        # 총점 기반 추천 의견 산출
        if score >= 50: recommendation = "🟢 강력 매수 (Strong Buy)"
        elif score >= 10: recommendation = "🟡 분할 매수 (Buy)"
        elif score >= -10: recommendation = "⚪ 관망 (Hold)"
        elif score >= -49: recommendation = "🟠 부분 매도 (Sell)"
        else: recommendation = "🔴 강력 매도 (Strong Sell)"
        
        result_text = (f"현재가 ${current_price:.2f} (내 수익률: {pnl_text})\n"
                f"   ├ 밴드위치: {bb_status}\n"
                f"   ├ MACD: {macd_status}\n"
                f"   └ RSI: {rsi:.1f} ({rsi_status})\n"
                f"   👉 [추천: {recommendation}] (합계 스코어: {score}점)")
                
        return score, result_text

    def format_portfolio_status(self, account: dict, positions: dict, exchange_rate: float) -> str:
        """현재 계좌 자산 및 종목 보유 현황을 문자열로 포맷팅합니다."""
        cash_usd = account.get("cash_usd", 0.0)
        cash_krw = account.get("cash_krw", 0.0)
        
        pos_lines = []
        for ticker, pos in positions.items():
            qty = pos.get("qty", 0)
            if qty <= 0:
                continue
            
            name = pos.get("name", ticker)
            pnl_pct = pos.get("pnl_pct", 0.0)
            eval_value = pos.get("eval_value", 0.0)
            currency = pos.get("currency", "USD")
            
            if currency == "KRW":
                val_str = f"₩{eval_value:,.0f}"
            else:
                val_str = f"${eval_value:,.2f}"
                
            sign = "+" if pnl_pct > 0 else ""
            icon = "🔴" if pnl_pct > 0 else ("🔵" if pnl_pct < 0 else "⚪")
            pos_lines.append(f"{icon} {name}({ticker})\n   └ {qty:g}주 {val_str} (수익률: {sign}{pnl_pct:.2f}%)")
            
        summary = self.api.get_portfolio_summary()
        # Toss API는 KRW 주식의 합은 krw에, USD 주식의 합은 usd에 분리해서 줌
        pnl_usd_raw = summary.get('daily_pnl_usd', 0.0)
        pnl_krw_raw = summary.get('daily_pnl_krw', 0.0)
        pnl_rate = summary.get('daily_pnl_rate', 0.0)
        
        stock_value_usd = summary.get('stock_value_usd', 0.0)
        stock_value_krw = summary.get('stock_value_krw', 0.0)
        
        text = f"💰 투자 평가금 (주식)\n"
        
        nodes = []
        if stock_value_krw > 0:
            krw_base = stock_value_krw - pnl_krw_raw
            krw_rate = (pnl_krw_raw / krw_base * 100) if krw_base > 0 else 0.0
            krw_sign = "+" if pnl_krw_raw > 0 else ""
            krw_icon = "▲" if pnl_krw_raw > 0 else ("▼" if pnl_krw_raw < 0 else "")
            nodes.append(f"🇰🇷 한국: ₩{stock_value_krw:,.0f}\n   {{}}   └ 일일 수익: {krw_icon}₩{abs(pnl_krw_raw):,.0f} ({krw_sign}{krw_rate:.2f}%)")

        if stock_value_usd > 0:
            usd_base = stock_value_usd - pnl_usd_raw
            usd_rate = (pnl_usd_raw / usd_base * 100) if usd_base > 0 else 0.0
            usd_sign = "+" if pnl_usd_raw > 0 else ""
            usd_icon = "▲" if pnl_usd_raw > 0 else ("▼" if pnl_usd_raw < 0 else "")
            nodes.append(f"🇺🇸 미국: ${stock_value_usd:,.2f}\n   {{}}   └ 일일 수익: {usd_icon}${abs(pnl_usd_raw):,.2f} ({usd_sign}{usd_rate:.2f}%)")
            
        for i, node in enumerate(nodes):
            is_last = (i == len(nodes) - 1)
            prefix = "└" if is_last else "├"
            child_prefix = " " if is_last else "│"
            text += f"   {prefix} {node.format(child_prefix)}\n"
        text += f"💵 예수금: ₩{cash_krw:,.0f} / ${cash_usd:,.2f}\n"
        text += "━━━━━━━━━━━━━━━\n"
        text += "\n".join(pos_lines)
        return text

    def format_midnight_status(self, account: dict, positions: dict, exchange_rate: float) -> str:
        """자정 비중 체크 전용 포맷 (양자 5개 종목 비중 + 가상 지갑 포함, 한국 주식 제외)"""
        cash_usd = account.get("cash_usd", 0.0)
        
        # 가상 지갑 잔액 읽어오기
        virtual_cash = get_virtual_cash()
        
        total_us_stock_value = 0.0
        for ticker in self.tickers:
            pos = positions.get(ticker, {})
            total_us_stock_value += pos.get("eval_value", 0.0)
            
        # 총 자산 = 주식 평가금 + 가상 지갑 잔액
        total_quantum_value = total_us_stock_value + virtual_cash
            
        pos_lines = []
        for ticker in self.tickers:
            pos = positions.get(ticker, {})
            qty = pos.get("qty", 0)
            name = pos.get("name", ticker)
            pnl_pct = pos.get("pnl_pct", 0.0)
            eval_value = pos.get("eval_value", 0.0)
            
            weight_pct = (eval_value / total_quantum_value * 100) if total_quantum_value > 0 else 0.0
            from config import TARGET_WEIGHTS
            target_w = TARGET_WEIGHTS.get(ticker, 0.0) * 100
            val_str = f"${eval_value:,.2f}"
            sign = "+" if pnl_pct > 0 else ""
            
            if qty > 0:
                icon = "🔴" if pnl_pct > 0 else ("🔵" if pnl_pct < 0 else "⚪")
                pos_lines.append(f"{icon} {name}({ticker})\n   ├ {qty:g}주 {val_str}\n   ├ 수익률: {sign}{pnl_pct:.2f}%\n   └ 비중: {weight_pct:.1f}% (목표: {target_w:.0f}%)")
            else:
                pos_lines.append(f"⚪ {name}({ticker})\n   └ 미보유 (목표: {target_w:.0f}%)")
                
        # 가상 지갑 현금도 리스트의 마지막에 추가
        cash_weight_pct = (virtual_cash / total_quantum_value * 100) if total_quantum_value > 0 else 0.0
        pos_lines.append(f"⚪ 대기 현금 (가상 지갑)\n   └ 잔액: ${virtual_cash:,.2f} (비중: {cash_weight_pct:.1f}%)")
                
        summary = self.api.get_portfolio_summary()
        pnl_usd_raw = summary.get('daily_pnl_usd', 0.0)
        pnl_krw_raw = summary.get('daily_pnl_krw', 0.0)
        pnl_rate = summary.get('daily_pnl_rate', 0.0)
        
        stock_value_usd = summary.get('stock_value_usd', 0.0)
        
        pnl_usd = pnl_usd_raw + (pnl_krw_raw / exchange_rate) if exchange_rate > 0 else pnl_usd_raw
        pnl_krw = pnl_krw_raw + (pnl_usd_raw * exchange_rate) if exchange_rate > 0 else pnl_krw_raw
        
        sign_pnl = "+" if pnl_usd > 0 else ""
        sign_pnl_icon = "▲" if pnl_usd > 0 else ("▼" if pnl_usd < 0 else "")
        
        text = f"💰 투자 평가금 (미국 주식)\n"
        text += f"   ├ 🇺🇸 미국: ${stock_value_usd:,.2f}\n"
        text += f"   └ 📊 전체 수익: {sign_pnl_icon}₩{abs(pnl_krw):,.0f} (${abs(pnl_usd):,.2f}) ({sign_pnl}{pnl_rate:.2f}%)\n"
        
        cash_krw = account.get("cash_krw", 0.0)
        text += f"💵 예수금: ₩{cash_krw:,.0f} / ${cash_usd:,.2f}\n"
        text += "━━━━━━━━━━━━━━━\n"
        text += "\n".join(pos_lines)
        return text

    def generate_briefing(self, market: str, is_close: bool = False):
        """장 시작 전 또는 마감 후 브리핑을 생성하여 전송합니다."""
        
        # 휴장일 체크
        now = datetime.now()
        if market == "KR" and not is_kr_market_open(now):
            print(f"[{market}] 한국 휴장일이므로 브리핑을 생략합니다.")
            return
            
        if market == "US":
            # 새벽 5시 10분 마감 브리핑의 경우, 어제(미국장 기준)가 영업일이었는지 판단해야 함
            check_dt = now if not is_close else now - timedelta(hours=6)
            if not is_us_market_open(check_dt):
                print(f"[{market}] 미국 휴장일이므로 브리핑을 생략합니다.")
                return

        market_name = "🇰🇷 한국장(KRX)" if market == "KR" else "🇺🇸 미국장(US)"
        timing = "마감 브리핑" if is_close else "개장 전 브리핑"
        print(f"[{market}] {timing} 생성 중...")
        
        # 1. 통합 데이터 페치
        exchange_rate = self.api.get_exchange_rate()
        account = self.api.get_account_balance()
        positions = self.api.get_my_positions()
        
        if account is None or positions is None:
            send_notification(f"❌ [{market_name}] {timing} 생성 실패: 토스증권 API 통신 장애로 계좌 정보를 불러오지 못했습니다.")
            print(f"[{market}] API 장애로 브리핑 생성을 취소합니다.")
            return
            
        current_prices = self.api.get_current_prices(self.tickers)
        
        # 2. 계좌 현황 (총 자산, 예수금, 종목별 수량, 금액, 수익률)
        portfolio_text = self.format_portfolio_status(account, positions, exchange_rate)
        
        # 3. 인공지능 퀀트 분석 및 매매 추천
        tech_lines = []
        for ticker in self.tickers:
            curr_price = current_prices.get(ticker, 0.0)
            pos = positions.get(ticker, {})
            avg_price = pos.get("avg_price", 0.0)
            
            score, analysis = self.analyze_and_recommend(ticker, avg_price, curr_price)
            tech_lines.append(f"🔬 {ticker}\n   └ {analysis}")
        tech_text = "\n\n".join(tech_lines)
        
        # 4. 뉴스 수집
        news_text = "\n\n".join(self.get_latest_news(market))
        
        # 5. 시장 지수 수집
        market_indices_text = self.get_market_indices(market)
        
        msg = (
            f"🔔 {market_name} {timing} 🔔\n\n"
            f"📈 주요 지수 및 환율\n"
            f"{market_indices_text}\n\n"
            f"💼 내 계좌 현황\n"
            f"{portfolio_text}\n\n"
            f"🤖 인공지능 퀀트 분석 및 매매 추천\n"
            f"{tech_text}\n\n"
            f"🗞️ 주요 증시 및 양자 섹터 뉴스\n"
            f"{news_text}"
        )
        
        send_notification(msg)

    def intraday_monitor(self):
        """장중 5분 단위로 초대형 시그널(강력 매수/매도)을 감시합니다."""
        now = datetime.now()
        
        # 장 시작 직전(22시~22시 30분 사이)에 캐시 초기화
        if now.hour == 22 and now.minute < 30:
            self.alert_history.clear()
            
        # 서머타임 미국장 시간 (22:30 ~ 05:00) 및 휴장일 검사
        is_market_open = (now.hour == 22 and now.minute >= 30) or (now.hour >= 23) or (now.hour < 5)
        if not is_market_open:
            return
            
        # 자정 이후(새벽) 감시는 전날 미국장이 열렸는지 확인하기 위해 시차 보정
        check_dt = now if now.hour >= 22 else now - timedelta(hours=6)
        if not is_us_market_open(check_dt):
            return
            
        positions = self.api.get_my_positions()
        current_prices = self.api.get_current_prices(self.tickers)
        
        for ticker in self.tickers:
            pos = positions.get(ticker, {"avg_price": 0.0})
            avg_price = pos["avg_price"]
            curr_price = current_prices.get(ticker, 0.0)
            
            score, analysis = self.analyze_and_recommend(ticker, avg_price, curr_price)
            
            if score >= 50 or score <= -50:
                signal_type = "BUY" if score >= 50 else "SELL"
                
                # 오늘 이미 동일한 시그널을 보냈다면 스킵
                if self.alert_history.get(ticker) == signal_type:
                    continue
                    
                alert_msg = (
                    f"🚨 [긴급 퀀트 시그널 감지] 🚨\n"
                    f"종목: {ticker}\n"
                    f"상태: {'🟢 강력 매수' if signal_type == 'BUY' else '🔴 강력 매도'} (스코어 {score}점)\n"
                    f"{analysis}"
                )
                
                send_notification(alert_msg)
                print(f"[{datetime.now()}] 긴급 시그널 발송 완료: {ticker} ({signal_type})")
                self.alert_history[ticker] = signal_type

if __name__ == "__main__":
    briefer = MarketBriefer()
    briefer.generate_briefing("US", is_close=False)
