import holidays
from datetime import datetime, timedelta

def is_us_market_open(kst_dt: datetime = None) -> bool:
    """
    한국 시간(KST)을 입력받아 미국(NYSE) 시장이 열리는 영업일인지 확인합니다.
    (주말 및 미국 공휴일 판단)
    """
    if kst_dt is None:
        kst_dt = datetime.now()
        
    # 한국 시간(UTC+9)에서 미국 동부 시간(UTC-5)으로 대략 변환 (14시간 차이)
    # 날짜(Date) 판단용이므로 서머타임 1시간 오차는 영업일 판별에 영향을 주지 않음
    us_dt = kst_dt - timedelta(hours=14)
    
    # 1. 주말(토, 일) 체크
    if us_dt.weekday() >= 5:
        return False
        
    # 2. 뉴욕증권거래소(NYSE) 공식 휴장일 체크
    nyse_holidays = holidays.financial_holidays('US')
    if us_dt.date() in nyse_holidays:
        return False
        
    return True

def is_kr_market_open(kst_dt: datetime = None) -> bool:
    """한국(KRX) 시장 영업일 여부 (주말 및 법정 공휴일 + 근로자의 날, 연말 휴장일 포함)"""
    if kst_dt is None:
        kst_dt = datetime.now()
        
    if kst_dt.weekday() >= 5:
        return False
        
    kr_holidays = holidays.country_holidays('KR')
    if kst_dt.date() in kr_holidays:
        return False
        
    # 한국거래소(KRX) 추가 휴장일 (근로자의 날, 매년 12월 31일)
    if kst_dt.month == 5 and kst_dt.day == 1:
        return False
    if kst_dt.month == 12 and kst_dt.day == 31:
        return False
        
    return True
