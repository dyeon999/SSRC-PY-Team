import os
import shodan
from pymongo import MongoClient
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ========== 1. 환경 설정 ==========
load_dotenv()
SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")
SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")
MONGO_URI = os.getenv("MONGO_URI")

#이메일 관련 옵션
SEND_EMAIL = os.getenv("SEND_EMAIL")
SEND_PWD   = os.getenv("SEND_PWD")
RECV_EMAIL = os.getenv("RECV_EMAIL")

api = shodan.Shodan(SHODAN_API_KEY)

# MongoDB 연결
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["shodan_db"]


# 기본 고정 포트
fixed_ports = [3389, 7547, 9000, 8009, 8008, 8443]

# Shodan에서 한국 기준 상위 5개 포트 가져오기
try:
    stats = api.count("country:KR", facets=["port:5"])
    top_ports = [facet['value'] for facet in stats['facets']['port']]
    print("Shodan 상위 5개 포트:", top_ports)
except Exception as e:
    print("[에러] Shodan 상위 포트 가져오기 실패:", e)
    top_ports = []

# 고정 포트 + 상위 포트 합치기 (중복 제거)
ports = list(set(fixed_ports + top_ports))
print("최종 모니터링 포트 목록:", ports)


# ========== 2. Slack 알림 함수 ==========
def send_slack_message(text: str) -> None:
    """Slack 채널에 메시지 전송"""
    if not SLACK_API_TOKEN or not SLACK_CHANNEL:
        print("[Slack 알림 건너뜀] 토큰/채널 설정 없음")
        return

    client = WebClient(token=SLACK_API_TOKEN)

    try:
        # Slack 메시지 길이 제한 처리
        if len(text) > 3500:
            text = text[:3500] + "\n... (메시지 길이 초과, 일부 생략)"

        response = client.chat_postMessage(channel=SLACK_CHANNEL, text=text)
        print("Slack 알림 전송 성공:", response["message"]["text"])
    except SlackApiError as e:
        print("Slack 알림 실패:", e.response["error"])

# ============ 이메일 추가 ============
def send_email_message(text: str):
    """이메일로 알림 전송"""
    if not SEND_EMAIL or not SEND_PWD or not RECV_EMAIL:
        print("[이메일 알림 건너뜀] 환경 변수 없음")
        return

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    subject = f"[{now}] Shodan 신규 포트 발견"
    body = f"<b>{now} 기준 신규 포트 발견</b><br><br><pre>{text}</pre>"

    try:
        smtp = smtplib.SMTP('smtp.naver.com', 587)  # Gmail은 smtp.gmail.com
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
        print("[EMAIL] 전송 완료")
    except Exception as e:
        print("[EMAIL] 전송 실패:", e)


# ========== 3. Shodan 검색 + MongoDB 저장 ==========
try:
    for port in ports:
        totals_db = db["totals"]  # 포트별 총량 기록 컬렉션
        collection = db[f"port_{port}"]  # 포트별 데이터 저장 컬렉션

        # 이전 total 값 불러오기
        total_doc = totals_db.find_one({"port": port})
        previous_total = total_doc["total"] if total_doc else 0

        # Shodan 검색 (예외처리 추가)
        query = f"country:KR port:{port}"
        try:
            results = api.search(query)
        except shodan.APIError as e:
            print(f"[에러] Shodan API 검색 실패 (포트 {port}): {e}")
            continue

        current_total = results["total"]

        print(f"\n==== 포트 {port} 검색 ====")
        print(f"총 {current_total}개의 호스트 발견됨")

        saved_count = 0
        new_ports_found = []

        for host in results["matches"]:
            ip = host["ip_str"]
            port_num = host["port"]
            org = host.get("org", "N/A")
            location = host.get("location", {}).get("country_name", "N/A")
            hostnames = ", ".join(host.get("hostnames", [])) if host.get("hostnames") else "N/A"

            # DB 저장
            data = {
                "ip": ip,
                "port": port_num,
                "org": org,
                "location": location,
                "hostnames": hostnames
            }

            # 기존 문서 확인
            prev_doc = collection.find_one({"ip": ip})
            if not prev_doc:
                new_ports_found.append(f"{ip}:{port_num}")

            collection.update_one({"ip": ip}, {"$set": data}, upsert=True)
            saved_count += 1

        # totals 업데이트
        totals_db.update_one({"port": port}, {"$set": {"total": current_total}}, upsert=True)

        # 증감 계산
        diff = current_total - previous_total
        if diff > 0:
            print(f"포트 {port}: {diff}개 증가")
            send_slack_message(f"[알림] 포트 {port}: {diff}개 증가")
        elif diff < 0:
            print(f"포트 {port}: {-diff}개 감소")
        else:
            print(f"포트 {port}: 변화 없음")

        # 신규 포트 발견 알림
        if new_ports_found:
            msg = "[신규 포트 발견]\n" + "\n".join(new_ports_found[:50])  # 최대 50개까지만 표시
            if len(new_ports_found) > 50:
                msg += f"\n... 외 {len(new_ports_found)-50}개 추가 발견"
            print(msg)
            send_slack_message(msg)
            send_email_message(msg)

        print(f"총 {saved_count}개 문서 저장 완료")
        print("====================================")

finally:
    mongo_client.close()
    print("\nMongoDB 연결 종료")
