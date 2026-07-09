import urllib.request
import urllib.parse
import json
import logging
from config import TOSS_API_URL, TOSS_API_KEY, TOSS_SECRET_KEY, ACCOUNT_NUMBER, PAPER_TRADE

logger = logging.getLogger("TossAPI")

class TossAPIClient:
    """토스증권 실전 Open API 클라이언트"""
    def __init__(self):
        self.api_key = TOSS_API_KEY
        self.secret = TOSS_SECRET_KEY
        self.account = ACCOUNT_NUMBER
        self.base_url = TOSS_API_URL
        self.access_token = None
        self._authenticate()

    def _authenticate(self):
        """OAuth 2.0 Token 발급 (Client Credentials Grant)"""
        if self.api_key == "YOUR_API_KEY_HERE":
            logger.warning("API Key가 설정되지 않았습니다. config.py를 확인하세요.")
            return

        # '/api/v1' 엔드포인트를 제거하고 oauth base url 구성
        base_auth_url = self.base_url.replace('/api/v1', '')
        url = f"{base_auth_url}/oauth2/token"
        
        data = urllib.parse.urlencode({
            'grant_type': 'client_credentials',
            'client_id': self.api_key,
            'client_secret': self.secret
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=data)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                self.access_token = res_data.get('access_token')
                logger.info("토스증권 API 인증 토큰 발급 성공")
                
                # 인증 성공 후 계좌 식별자 자동 조회
                if not self.account or self.account == "YOUR_ACCOUNT_NUMBER_HERE":
                    self._fetch_account_sequence()
                    
        except urllib.error.HTTPError as e:
            logger.error(f"API 인증 실패 HTTP {e.code}: {e.read().decode('utf-8')}")
        except Exception as e:
            logger.error(f"API 인증 네트워크 오류: {e}")

    def _fetch_account_sequence(self):
        """API를 통해 사용자의 종합계좌 식별자(accountSeq)를 자동 조회합니다."""
        import time
        time.sleep(1) # 연속된 인스턴스 생성 시 Rate Limit 방지
        url = f"{self.base_url}/accounts"
        req = urllib.request.Request(url, method='GET')
        req.add_header('Authorization', f'Bearer {self.access_token}')
        req.add_header('Accept', 'application/json')
        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                if res_data and 'result' in res_data and len(res_data['result']) > 0:
                    self.account = str(res_data['result'][0].get('accountSeq'))
                    logger.info(f"계좌 식별자 자동 조회 완료: {self.account}")
                else:
                    logger.warning("조회된 계좌가 없습니다.")
        except Exception as e:
            logger.error(f"계좌 식별자 자동 조회 실패: {e}")

    def _request(self, method, endpoint, payload=None, requires_account=False, is_retry=False):
        """API 공통 호출 모듈 (401 에러 시 자동 갱신 지원)"""
        if not self.access_token:
            return None
            
        url = f"{self.base_url}{endpoint}"
        req = urllib.request.Request(url, method=method)
        req.add_header('Authorization', f'Bearer {self.access_token}')
        req.add_header('Accept', 'application/json')
        
        if requires_account:
            if not self.account or self.account == "YOUR_ACCOUNT_NUMBER_HERE":
                self._fetch_account_sequence()
            if self.account and self.account != "YOUR_ACCOUNT_NUMBER_HERE":
                req.add_header('X-Tossinvest-Account', str(self.account))
            else:
                logger.error("계좌 식별자(Account ID)가 설정되지 않아 요청이 취소되었습니다.")
                return None
            
        if payload:
            data = json.dumps(payload).encode('utf-8')
            req.data = data
            req.add_header('Content-Type', 'application/json')
            
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_data = e.read().decode('utf-8')
            
            # 토큰 만료(401) 처리 및 자동 갱신 (무한루프 방지를 위해 is_retry 확인)
            if e.code == 401 and not is_retry:
                logger.warning("API 토큰이 만료되었습니다. 새 토큰을 발급받아 재시도합니다.")
                self._authenticate()
                if self.access_token:
                    return self._request(method, endpoint, payload, requires_account, is_retry=True)
                    
            # Rate Limit (429) 처리: 1초 대기 후 재시도
            if e.code == 429 and not is_retry:
                import time
                logger.warning("API 요청 한도 초과(429). 1초 대기 후 재시도합니다.")
                time.sleep(1)
                return self._request(method, endpoint, payload, requires_account, is_retry=True)
                    
            logger.error(f"API 에러 [{method} {endpoint}] {e.code}: {error_data}")
            return None
        except Exception as e:
            logger.error(f"요청 에러 [{method} {endpoint}]: {e}")
            return None

    def get_account_balance(self):
        """계좌 잔고 조회 (API 명세서 구조 반영)"""
        if self.api_key == "YOUR_API_KEY_HERE":
            return {"total_assets_usd": 1500.0, "cash_usd": 5000.0, "cash_krw": 1000000.0} # 테스트용 목업
            
        usd_res = self._request('GET', '/buying-power?currency=USD', requires_account=True)
        krw_res = self._request('GET', '/buying-power?currency=KRW', requires_account=True)
        
        if usd_res is None or krw_res is None:
            return None
        
        cash_usd = 0.0
        if 'result' in usd_res:
            cash_usd = float(usd_res['result'].get('cashBuyingPower', 0.0))
            
        cash_krw = 0.0
        if 'result' in krw_res:
            cash_krw = float(krw_res['result'].get('cashBuyingPower', 0.0))
                    
        return {
            "total_assets_usd": cash_usd, # Rebalancer에서 다시 계산함
            "cash_usd": cash_usd,
            "cash_krw": cash_krw
        }

    def get_my_positions(self):
        """현재 계좌의 US 보유 종목 리스트 반환"""
        if self.api_key == "YOUR_API_KEY_HERE":
            # 테스트용 목업 데이터
            return {
                "IONQ": {"qty": 700, "avg_price": 50.0},
                "INFQ": {"qty": 1100, "avg_price": 20.0},
                "QBTS": {"qty": 500, "avg_price": 22.0},
                "RGTI": {"qty": 900, "avg_price": 18.0},
                "QUBT": {"qty": 1000, "avg_price": 9.15}
            }
            
        res = self._request('GET', '/holdings', requires_account=True)
        positions = {}
        if res and 'result' in res and 'items' in res['result']:
            for item in res['result']['items']:
                symbol = item.get('symbol')
                # API 스펙에 맞추어 parsing. US 종목만 매핑
                if symbol:
                    qty = float(item.get('quantity', 0))
                    avg_price = float(item.get('averagePurchasePrice', 0))
                    name = item.get('name', symbol)
                    currency = item.get('currency', 'USD')
                    val_str = item.get('marketValue', {}).get('amount', 0)
                    eval_value = float(val_str) if val_str else 0.0
                    rate_str = item.get('profitLoss', {}).get('rate', 0)
                    pnl_pct = float(rate_str) * 100 if rate_str else 0.0
                    
                    positions[symbol] = {
                        "qty": qty, 
                        "avg_price": avg_price,
                        "name": name,
                        "currency": currency,
                        "eval_value": eval_value,
                        "pnl_pct": pnl_pct
                    }
        return positions
        
    def get_portfolio_summary(self):
        """총 자산의 일일 등락폭 및 등락률 반환"""
        if self.api_key == "YOUR_API_KEY_HERE":
            return {"daily_pnl_usd": 15.5, "daily_pnl_krw": 20000, "daily_pnl_rate": 0.5, "stock_value_usd": 2000.0, "stock_value_krw": 2600000.0}
            
        res = self._request('GET', '/holdings', requires_account=True)
        if res and 'result' in res and 'dailyProfitLoss' in res['result']:
            dp = res['result']['dailyProfitLoss']
            usd_amt = float(dp.get('amount', {}).get('usd', 0.0))
            krw_amt = float(dp.get('amount', {}).get('krw', 0.0))
            rate = float(dp.get('rate', 0.0)) * 100
            
            stock_value_usd = float(res['result'].get('marketValue', {}).get('amount', {}).get('usd', 0.0))
            stock_value_krw = float(res['result'].get('marketValue', {}).get('amount', {}).get('krw', 0.0))
            return {
                "daily_pnl_usd": usd_amt,
                "daily_pnl_krw": krw_amt,
                "daily_pnl_rate": rate,
                "stock_value_usd": stock_value_usd,
                "stock_value_krw": stock_value_krw
            }
        return {"daily_pnl_usd": 0.0, "daily_pnl_krw": 0.0, "daily_pnl_rate": 0.0, "stock_value_usd": 0.0, "stock_value_krw": 0.0}

    def get_current_prices(self, tickers: list):
        """요청한 티커들의 현재가를 반환"""
        if not tickers: 
            return {}
            
        if self.api_key == "YOUR_API_KEY_HERE":
            # 테스트용 목업 데이터 (리밸런싱 유도)
            return {"IONQ": 55.0, "INFQ": 20.0, "QBTS": 15.0, "RGTI": 18.0, "QUBT": 9.15}
            
        symbols = ",".join(tickers)
        res = self._request('GET', f'/prices?symbols={symbols}')
        prices = {}
        if res and 'result' in res:
            for item in res['result']:
                symbol = item.get('symbol')
                price = float(item.get('lastPrice', 0))
                prices[symbol] = price
        return prices

    def get_exchange_rate(self):
        """실시간 원달러 환율(KRW-USD) 반환"""
        if self.api_key == "YOUR_API_KEY_HERE":
            return 1350.0
            
        res = self._request('GET', '/exchange-rate?baseCurrency=USD&quoteCurrency=KRW')
        if res and 'result' in res:
            return float(res['result'].get('rate', 0.0))
        return 0.0

    def get_candles(self, symbol: str, interval: str = '1d', count: int = 100):
        """종목의 캔들(OHLCV) 데이터를 가져옵니다."""
        import time
        time.sleep(0.5) # API Rate Limit(429) 방지를 위한 딜레이
        
        if self.api_key == "YOUR_API_KEY_HERE":
            # 테스트용 목업 데이터 (임의의 가격 변동)
            return [{"closePrice": 10.0 + i * 0.5, "openPrice": 10.0, "highPrice": 12.0, "lowPrice": 9.0, "volume": 1000} for i in range(count)]
            
        res = self._request('GET', f'/candles?symbol={symbol}&interval={interval}&count={count}')
        if res and 'result' in res and 'candles' in res['result']:
            return res['result']['candles']
        return []

    def place_order(self, ticker: str, side: str, qty: int, order_type: str = "MARKET") -> bool:
        """실제 매수/매도 주문 전송 (성공 여부 반환)"""
        qty = int(qty)
        if qty <= 0: 
            return False
        
        msg = f"[{side.upper()}] {ticker} {qty}주 주문 ({order_type})"
        if PAPER_TRADE:
            logger.info(f"[PAPER-TRADE/모의투자] {msg} -> (실제 주문 접수 안됨, 가상 성공)")
            return True
            
        logger.info(f"[REAL-TRADE/실전투자] {msg} -> 주문 접수 중...")
        
        if self.api_key == "YOUR_API_KEY_HERE":
            logger.error("API Key 미설정으로 실제 주문 접수 불가")
            return False
            
        payload = {
            "symbol": ticker,
            "side": side.upper(),
            "orderType": order_type.upper(),
            "quantity": qty,
            "timeInForce": "DAY"
        }
        
        res = self._request('POST', '/orders', payload=payload, requires_account=True)
        if res:
            logger.info(f"주문 체결 접수 성공: {res}")
            return True
        else:
            logger.error("주문 체결 접수 실패")
            return False
