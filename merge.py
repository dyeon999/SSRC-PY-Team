import os
import time
import smtplib
import shodan
from pymongo import MongoClient
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()

client = MongoClient('mongodb://localhost:27017/')
db = client['test']  
ports = {
    80: 0,
    443: 0,
    135: 0,
    22: 0,
    70: 0
}

SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")
api = shodan.Shodan(SHODAN_API_KEY)

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
    if not (SEND_EMAIL and SEND_PWD and RECV_EMAIL):
        print("[EMAIL] 계정 미설정. 전송 생략")
        return

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    subject = f"[{now}] 열린 port 분석 결과"
    body    = f"<b>{now} 기준 열린 port 분석 결과입니다.</b><br><br><pre>{text}</pre>"

    smtp = smtplib.SMTP('smtp.naver.com', 587)
    smtp.ehlo()
    smtp.starttls()
    smtp.login(SEND_EMAIL, SEND_PWD)

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From']    = SEND_EMAIL
    msg['To']      = RECV_EMAIL
    msg.attach(MIMEText(body, 'html'))

    smtp.sendmail(SEND_EMAIL, RECV_EMAIL, msg.as_string())
    smtp.quit()
    print(f"[EMAIL] sent: {len(text)} chars")


def total_docs_in_db() -> int:
    """현재 DB의 모든 포트 컬렉션 총 문서 수"""
    total = 0
    for p in ports.keys():
        total += db[str(p)].count_documents({})
    return total


def build_report_text() -> str:
    lines = []
    grand_total = 0
    for p in sorted(ports.keys()):
        coll = db[str(p)]
        count = coll.count_documents({})
        grand_total += count
        lines.append(f"{p}번의 열린 port 개수: {count}개")
    lines.append("")  # 빈줄
    lines.append(f"전체 열린 포트 Doc 합계: {grand_total}개")
    return "\n".join(lines) if lines else "(데이터 없음)"


def execute():
    report = build_report_text()
    # Slack 길이 고려: 긴 경우 잘라서 전송(필요하면 분할 로직 추가)
    send_slack_message(SLACK_CHANNEL, report)
    send_email_message(report)
    print("[EXECUTE] 전송 완료")


def save(country: str, port: int):
    collection = db[f'{port}']
    query = f'country:"{country}" port:"{port}"'

    try:
        results = api.search(query)
    except Exception as e:
        print(f"[SHODAN ERROR] {country} {port}: {e}")
        return

    new_total = results.get('total', 0)
    # 포트별 최근 총량 대조(정보성 로그)
    prev_port_total = ports.get(port, 0)
    diff = abs(prev_port_total - new_total)

    if prev_port_total == 0:
        print(f"[INFO] 국가:{country} 포트:{port} 총 {new_total}개 감지")
    elif prev_port_total > new_total:
        print(f"[INFO] 포트 {port} 총 {diff} 감소 (Shodan total)")
    elif prev_port_total < new_total:
        print(f"[INFO] 포트 {port} 총 {diff} 증가 (Shodan total)")
    ports[port] = new_total

    matches = results.get('matches', [])
    inserted_or_updated = 0
    for result in matches:
        ip            = result.get("ip_str")
        r_port        = result.get("port")
        country_code  = (result.get("location") or {}).get("country_code")
        domains       = result.get("domains") or []

        collection.update_one(
            {"IP": ip},  
            {"$set": {
                "PORTS": r_port,
                "country": country_code,
                "domain": domains
            }},
            upsert=True
        )
        inserted_or_updated += 1

    print(f"[UPSERT] {country} {port} → upserted/updated: {inserted_or_updated}")


if __name__ == '__main__':
    prev_total = total_docs_in_db()
    print(f"[START] 현재 총 문서 수: {prev_total}")

    while True:
        for port in ports.keys():
            save('KR', port)

            current_total = total_docs_in_db()
            if current_total > prev_total:
                added = current_total - prev_total
                print(f"✅ MongoDB에 {added}개 추가 감지 → execute()")
                prev_total = current_total
                print(f"[WATCH] 기준 갱신: {prev_total}")
            
        execute()
        # 모든 포트에 대해 조회를 마쳤으면 n초 대기 후 다음 사이클로
        time.sleep(60)
