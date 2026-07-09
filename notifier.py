import urllib.request
import urllib.parse
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_notification(message: str):
    """텔레그램 봇으로 알림 메시지를 전송합니다."""
    print(f"[알림] {message}")
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or TELEGRAM_CHAT_ID == "YOUR_TELEGRAM_CHAT_ID_HERE":
        return # 키가 설정되지 않았으므로 로컬 출력만 함
        
    try:
        encoded_msg = urllib.parse.quote(message)
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={encoded_msg}"
        req = urllib.request.Request(url)
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"텔레그램 알림 전송 실패: {e}")
