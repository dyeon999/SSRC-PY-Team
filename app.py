from flask import Flask, render_template, request, redirect, url_for
import os, time, smtplib
import shodan
from pymongo import MongoClient
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ───────── 기본 환경 ─────────
load_dotenv()

client = MongoClient('mongodb://localhost:27017/')
db = client['test']  # 포트번호별 컬렉션 사용 (예: "80","443"...)
ports = {80: 0, 443: 0, 135: 0, 22: 0, 70: 0}

SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")
api = shodan.Shodan(SHODAN_API_KEY)

SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN")
SLACK_CHANNEL   = os.getenv("SLACK_CHANNEL")

SEND_EMAIL = os.getenv("SECRET_ID")
SEND_PWD   = os.getenv("SECRET_PASS")
RECV_EMAIL = os.getenv("RECV_ID")

app = Flask(__name__)


# ───────── 유틸/비즈니스 로직 (기존 유지) ─────────
def send_slack_message(channel: str, text: str):
    if not (SLACK_API_TOKEN and channel):
        return "[SLACK] 토큰/채널 미설정, 전송 생략"
    client = WebClient(token=SLACK_API_TOKEN)
    try:
        client.chat_postMessage(channel=channel, text=text[:3800])  # 길이 보호
        return f"[SLACK] sent: {min(len(text),3800)} chars"
    except SlackApiError as e:
        return f"[SLACK ERROR] {e.response.get('error')}"

def send_email_message(text: str):
    if not (SEND_EMAIL and SEND_PWD and RECV_EMAIL):
        return "[EMAIL] 계정 미설정, 전송 생략"

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    subject = f"[{now}] 열린 port 분석 결과"
    body    = f"<b>{now} 기준 열린 port 분석 결과입니다.</b><br><br><pre>{text}</pre>"

    smtp = smtplib.SMTP('smtp.naver.com', 587)
    smtp.ehlo(); smtp.starttls(); smtp.login(SEND_EMAIL, SEND_PWD)

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From']    = SEND_EMAIL
    msg['To']      = RECV_EMAIL
    msg.attach(MIMEText(body, 'html'))

    smtp.sendmail(SEND_EMAIL, RECV_EMAIL, msg.as_string())
    smtp.quit()
    return f"[EMAIL] sent: {len(text)} chars"

def total_docs_in_db() -> int:
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
    lines.append("")
    lines.append(f"전체 열린 포트 Doc 합계: {grand_total}개")
    return "\n".join(lines) if lines else "(데이터 없음)"

def save(country: str, port: int, logs: list):
    collection = db[f'{port}']
    query = f'country:"{country}" port:"{port}"'
    try:
        results = api.search(query)
    except Exception as e:
        logs.append(f"[SHODAN ERROR] {country} {port}: {e}")
        return

    new_total = results.get('total', 0)
    prev_port_total = ports.get(port, 0)
    diff = abs(prev_port_total - new_total)

    if prev_port_total == 0:
        logs.append(f"[INFO] 국가:{country} 포트:{port} 총 {new_total}개 감지")
    elif prev_port_total > new_total:
        logs.append(f"[INFO] 포트 {port} 총 {diff} 감소 (Shodan total)")
    elif prev_port_total < new_total:
        logs.append(f"[INFO] 포트 {port} 총 {diff} 증가 (Shodan total)")
    ports[port] = new_total

    matches = results.get('matches', [])
    up_cnt = 0
    for result in matches:
        ip            = result.get("ip_str")
        r_port        = result.get("port")
        country_code  = (result.get("location") or {}).get("country_code")
        domains       = result.get("domains") or []

        collection.update_one(
            {"IP": ip},
            {"$set": {"PORTS": r_port, "country": country_code, "domain": domains}},
            upsert=True
        )
        up_cnt += 1
    logs.append(f"[UPSERT] {country} {port} → upserted/updated: {up_cnt}")


# ───────── Flask 라우트 ─────────
@app.route('/', methods=['GET'])
def home():
    # 최초 진입: main.html
    return render_template('main.html', logs=None, preview=None)

@app.route('/start', methods=['POST'])
def start():
    logs = []
    prev_total = total_docs_in_db()
    logs.append(f"[START] 현재 총 문서 수: {prev_total}")

    # 한 사이클 실행 (동기)
    for p in ports.keys():
        save('KR', p, logs)

    current_total = total_docs_in_db()
    if current_total != prev_total:
        delta = current_total - prev_total
        sign = '+' if delta > 0 else ''
        logs.append(f"🔔 MongoDB 총 문서 변화: {prev_total} → {current_total} ({sign}{delta})")
    else:
        logs.append("ℹ️ 총 문서 수 변화 없음")

    return render_template('main.html', logs=logs, preview=None)

@app.route('/preview', methods=['GET'])
def preview():
    report = build_report_text()
    return render_template('main.html', logs=None, preview=report)

@app.route('/send', methods=['POST'])
def send_now():

    report = build_report_text()
    sres = send_slack_message(SLACK_CHANNEL, report)
    eres = send_email_message(report)

    logs = [sres, eres, "[EXECUTE] 전송 완료"]
    return render_template('main.html', logs=logs, preview=report)


if __name__ == '__main__':
    # flask run 과 별개로 직접 실행 시
    app.run(debug=True)
