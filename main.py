import os
import time
# 강제로 시스템 타임존을 KST(한국 시간)로 고정 (해외 출장 시 시간 꼬임 방지)
os.environ['TZ'] = 'Asia/Seoul'
time.tzset()

import schedule
from datetime import datetime
from rebalancer import PortfolioRebalancer
from briefer import MarketBriefer
from notifier import send_notification
from toss_api import TossAPIClient
from config import PAPER_TRADE

def run_daily_briefing():
    """하루 장 마감 후 수익률 요약을 보내는 추가 기능"""
    print("일일 브리핑 생성 중...")
    briefer = MarketBriefer()
    
    exchange_rate = briefer.api.get_exchange_rate()
    account = briefer.api.get_account_balance()
    positions = briefer.api.get_my_positions()
    
    if account is None or positions is None:
        send_notification("❌ [자정 브리핑] 토스증권 API 통신 장애로 계좌 정보를 불러오지 못했습니다.")
        print("API 장애로 일일 브리핑 생성을 취소합니다.")
        return
        
    portfolio_text = briefer.format_midnight_status(account, positions, exchange_rate)
    
    msg = f"📊 [자정 비중 체크 완료]\n\n{portfolio_text}\n\n🤖 모의투자 모드: {PAPER_TRADE}"
    send_notification(msg)

from market_calendar import is_us_market_open

def run_midnight_check(bot):
    """자정 실행 루틴: 리밸런싱 체크 후 브리핑 전송"""
    print(f"\n[{datetime.now()}] 자정 스케줄러 실행 중...")
    
    # 00:00 KST에 리밸런싱 실행 여부는 '지금 미국장이 열려있는가'와 직결됨.
    if not is_us_market_open():
        print("미국 휴장일(주말/공휴일)이므로 리밸런싱 및 자정 브리핑을 건너뜁니다.")
        return
        
    bot.check_and_rebalance()
    run_daily_briefing()

if __name__ == "__main__":
    bot = PortfolioRebalancer()
    briefer = MarketBriefer()
    
    print(f"[{datetime.now()}] 퀀텀 봇 시스템이 시작되었습니다. (텔레그램 연동 대기 중)")
    
    # 1. 스케줄 등록
    # 한국장(KR)
    schedule.every().day.at("08:30").do(briefer.generate_briefing, market="KR", is_close=False)
    schedule.every().day.at("15:40").do(briefer.generate_briefing, market="KR", is_close=True)
    # 미국장(US)
    schedule.every().day.at("22:00").do(briefer.generate_briefing, market="US", is_close=False)
    schedule.every().day.at("05:10").do(briefer.generate_briefing, market="US", is_close=True)
    # 장중 실시간 감시 (5분 간격)
    schedule.every(5).minutes.do(briefer.intraday_monitor)
    # 리밸런싱
    schedule.every().day.at("00:00").do(run_midnight_check, bot=bot)
    
    print("⏰ 스케줄러 등록 완료:")
    print("   - [08:30] 🇰🇷 한국장 개장 전 브리핑")
    print("   - [15:40] 🇰🇷 한국장 마감 브리핑")
    print("   - [22:00] 🇺🇸 미국장 개장 전 브리핑 (서머타임 기준)")
    print("   - [22:30~05:00] 🇺🇸 미국장 장중 실시간 시그널 감시 (5분 간격)")
    print("   - [00:00] 🔄 자정 자동 리밸런싱")
    print("   - [05:10] 🇺🇸 미국장 마감 브리핑 (서머타임 기준)")
    
    # 2. 첫 구동 시 테스트를 위해 즉시 1회 브리핑 실행 (옵션)
    # briefer.generate_briefing(market="US", is_close=False)
    
    # 3. 무한 루프 구동 (백그라운드에서 계속 실행되며 스케줄 대기)
    try:
        while True:
            schedule.run_pending()
            time.sleep(1) # 1초마다 깸
    except KeyboardInterrupt:
        print("\n스케줄러 봇을 종료합니다.")
