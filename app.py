import os
import shodan
from pymongo import MongoClient
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


# ========== 1. 환경 설정 ==========
load_dotenv()
SHODAN_API_KEY = os.getenv("SHODAN_API_KEY")
SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")
MONGO_URI = os.getenv("MONGO_URI")

api = shodan.Shodan(SHODAN_API_KEY)

# MongoDB 연결
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["shodan_db"]

# 포트 목록 (필요에 맞게 수정 가능)
ports = [3389, 7547, 9000, 8009, 8008, 8443]


# ========== 2. Slack 알림 함수 ==========
def send_slack_message(text):
    """Slack 채널에 메시지 전송"""
    if not SLACK_API_TOKEN or not SLACK_CHANNEL:
        print("[Slack 알림 건너뜀] 토큰/채널 설정 없음")
        return

    client = WebClient(token=SLACK_API_TOKEN)
    try:
        response = client.chat_postMessage(channel=SLACK_CHANNEL, text=text)
        print("Slack 알림 전송 성공:", response["message"]["text"])
    except SlackApiError as e:
        print("Slack 알림 실패:", e.response["error"])


# ========== 3. Shodan 검색 + MongoDB 저장 ==========
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
        print(f"[에러] Shodan API 검색 실패 (포트 {port}: {e}")
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
        location = host.get("location",{}).get("country_name","N/A")
        hostnames = ", ".join(host["hostnames"]) if host["hostnames"] else "N/A"

        # DB 저장
        data = {
            "ip": ip,
            "port": port_num,
            "org": org,
            "location": location,
            "hostnames": hostnames,
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
    for new in new_ports_found:
        print(f"새로운 포트 발견! {new}")
        send_slack_message(f"[신규 포트 발견] {new}")


    print(f"총 {saved_count}개 문서 저장 완료")
    print("====================================")
mongo_client.close()
print("\nMongoDB 연결 종료")
