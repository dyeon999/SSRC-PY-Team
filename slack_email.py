from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from pymongo import MongoClient
from dotenv import load_dotenv
import os, time, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()

# MongoDB 연결
client = MongoClient('mongodb://localhost:27017/')
db = client['school_db']
collection = db['students']

# Slack/Email 설정
SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN")
SLACK_CHANNEL   = os.getenv("SLACK_CHANNEL")
SEND_EMAIL = os.getenv("SECRET_ID")
SEND_PWD   = os.getenv("SECRET_PASS")
RECV_EMAIL = os.getenv("RECV_ID")


def send_slack_message(channel: str, text: str):
    client = WebClient(token=SLACK_API_TOKEN)
    try:
        res = client.chat_postMessage(channel=channel, text=text)
        print(f"[SLACK] sent: {len(text)} chars")
    except SlackApiError as e:
        print(f"[SLACK ERROR] {e.response.get('error')}")

def send_email_message(text: str):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    subject = f"[{now}] 열린 port 분석 결과"
    body = f"<b>{now} 기준 열린 port 분석 결과입니다.</b><br><br><pre>{text}</pre>"

    smtp = smtplib.SMTP('smtp.naver.com', 587)
    smtp.ehlo()
    smtp.starttls()
    smtp.login(SEND_EMAIL, SEND_PWD)

    mime_msg = MIMEMultipart()
    mime_msg['Subject'] = subject
    mime_msg['From'] = SEND_EMAIL
    mime_msg['To'] = RECV_EMAIL
    mime_msg.attach(MIMEText(body, 'html'))

    smtp.sendmail(SEND_EMAIL, RECV_EMAIL, mime_msg.as_string())
    smtp.quit()
    print(f"[EMAIL] sent: {len(text)} chars")


def execute():
    results = collection.find({})
    lines = []
    for doc in results:
        lines.append(
            f"이름: {doc.get('name')}, 나이: {doc.get('age')}, "
            f"과목: {doc.get('subjects')}, 등급: {doc.get('grade')}"
        )
    final_msg = "\n".join(lines) if lines else "(데이터 없음)"

    send_email_message(final_msg)
    print("[EXECUTE] 전송 완료")


def watch_inserts_polling(collection, interval=5):
    prev_count = collection.count_documents({})
    print(f"[WATCH] 시작. 현재 문서 개수: {prev_count}")

    while True:
        time.sleep(interval)
        try:
            current_count = collection.count_documents({})
        except Exception as e:
            print(f"[WATCH ERROR] count 실패: {e}")
            continue

        if current_count > prev_count:
            added = current_count - prev_count
            print(f"✅ 새 문서 {added}개 추가 감지 → execute() 실행")
            try:
                execute()
            except Exception as e:
                print(f"[EXECUTE ERROR] {e}")
            # 실행 후 기준값 갱신
            prev_count = current_count
            print(f"[WATCH] 시작. 현재 문서 개수: {prev_count}")

        elif current_count < prev_count:
            # 삭제/정리 등 변동이 있을 수 있으니 기준값만 갱신
            print(f"ℹ️ 문서가 {prev_count - current_count}개 감소함. 기준 갱신.")
            prev_count = current_count
            print(f"[WATCH] 시작. 현재 문서 개수: {prev_count}")
        # 같으면 아무 일도 안 하고 계속 감시


if __name__ == "__main__":
    watch_inserts_polling(collection, interval=5)
