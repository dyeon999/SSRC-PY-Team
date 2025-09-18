## Shodan API를 활용한 보안 모니터링 시스템

import shodan
from pymongo import MongoClient
from dotenv import load_dotenv
import os, requests, smtplib, schedule, time
from email.mime.text import MIMEText

# 환경 변수 로드
load_dotenv()

# Shodan API 초기화
SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")
api = shodan.Shodan(SHODAN_API_KEY)

# MongoDB 연결
client = MongoClient(os.getenv("mongodb"))
db = client[os.getenv("db_name")]
collection = db[os.getenv("collec_name")]

# Slack 설정

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def slack_upload(message):
    payload = {"text": message}
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    if response.status_code != 200:
        print(f"Slack 전송 실패: {response.status_code}, {response.text}")
    else:
        print("Slack 전송 성공")

# Email 설정

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT   = int(os.getenv("SMTP_PORT"))
EMAIL_USER  = os.getenv("SECRET_ID")
EMAIL_PASS  = os.getenv("SECRET_PASS")
TO_EMAIL    = os.getenv("TO_EMAIL").split(",")

def email_upload(subject, body):
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = ", ".join(TO_EMAIL)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, TO_EMAIL, msg.as_string())

# MongoDB 조작 함수

def get_previous_total(port):
    doc = collection.find_one({"port": port})
    return doc["total"] if doc else 0

def update_totals(port, current_total, diff):
    collection.update_one(
        {"port": port},
        {"$set": {"total": current_total, "diff": diff}},
        upsert=True
    )

def save_hosts(port, hosts):
    collection = db[f"port_{port}"]
    for host in hosts:
        data = {
            "ip": host["ip_str"],
            "port": host["port"]
        }
        collection.update_one({"ip": data["ip"]}, {"$set": data}, upsert=True)


# 메인 실행 로직
def alert():

    # 한국 상위 5개 포트 추출
    stats = api.count("country:KR", facets=["port:5"])
    ports = [facet["value"] for facet in stats["facets"]["port"]]
    print("선정된 상위 5개 포트:", ports)

    messages = []  # Slack/Email에 보낼 메시지 누적

    for port in ports:
        try:
            results = api.search(f"country:KR port:{port}")
            current_total = results["total"]
            save_hosts(port, results["matches"])
        except Exception as e:
            print(f"포트 {port} 검색 실패:", e)
            continue

        previous_total = get_previous_total(port)
        diff = current_total - previous_total
        update_totals(port, current_total, diff)

        if diff > 0:
            status = f"포트 {port}: {diff}개 증가 (총 {current_total})"
        elif diff < 0:
            status = f"포트 {port}: {-diff}개 감소 (총 {current_total})"
        else:
            status = f"포트 {port}: 변화 없음 (총 {current_total})"

        print(status)
        messages.append(status)

    # 루프 끝난 뒤 한 번만 전송
    if messages:
        final_message = "\n".join(messages)
        try:
            slack_upload(final_message)
        except Exception as e:
            print("Slack 전송 에러:", e)

        try:
            email_upload("[포트 모니터링 결과]", final_message)
        except Exception as e:
            print("Email 전송 에러:", e)

# 스케줄러 설정

schedule.every(5).minutes.do(alert)

print("예약 시작")
alert()  # 시작 시 1회 실행

while True:
    schedule.run_pending()
    time.sleep(1)
