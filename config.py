import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수를 불러옵니다.
load_dotenv()

# 토스증권 API 접근 정보 (.env 파일에서 읽어옴)
TOSS_API_URL = "https://openapi.tossinvest.com/api/v1" # 실전용 공식 엔드포인트
TOSS_API_KEY = os.getenv("TOSS_API_KEY", "YOUR_API_KEY_HERE")
TOSS_SECRET_KEY = os.getenv("TOSS_SECRET_KEY", "YOUR_SECRET_KEY_HERE")
ACCOUNT_NUMBER = None # 봇이 API 키를 통해 자동으로 조회하여 채워넣습니다.

# 텔레그램 봇 알림 설정 (.env 파일에서 읽어옴)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_HERE")

# 모의투자(Dry-Run) 모드 여부. True일 경우 실제 주문이 들어가지 않습니다.
PAPER_TRADE = False 

# 양자컴퓨팅 타겟 포트폴리오 비중 (%)
# IonQ 35%, Infleqtion 25%, D-Wave 15%, Rigetti 15%, QCI 10%
TARGET_WEIGHTS = {
    "IONQ": 0.35,
    "INFQ": 0.25,
    "QBTS": 0.15,
    "RGTI": 0.15,
    "QUBT": 0.10
}

# 비중 리밸런싱을 촉발하는 임계값 (예: 5% = 0.05)
REBALANCE_THRESHOLD = 0.05
