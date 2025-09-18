import shodan
from pymongo import MongoClient
from slack_sdk import WebClient
from dotenv import load_dotenv
import os, smtplib
from dotenv import load_dotenv
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, render_template

load_dotenv()

SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL')
SEND_EMAIL = os.getenv('SEND_EMAIL')
SEND_PWD = os.getenv('SEND_PWD')
SHODAN_API_KEY = os.getenv('SHODAN_API_KEY')


client = MongoClient('mongodb://localhost:27017/')
# 'shodan_db'라는 데이터베이스를 선택한다.
db = client['shodan_db']
# 'totals' 컬렉션은 포트별 총 호스트 수를 기록한다.
totals_collection = db['totals']

api = shodan.Shodan(SHODAN_API_KEY)  # Shodan API 인스턴스 생성

app = Flask(__name__)  # Flask 앱 생성

#  이메일 전송 함수 
def send_email_message(text: str, recv_email: str):
    if not SEND_EMAIL or not SEND_PWD or not recv_email:
        print("이메일 계정 정보 미설정, 전송 생략")
        return

    now = datetime.now().strftime('%Y-%m-%d %H:%M')  # 현재 시각
    subject = f"[{now}] Shodan 포트 감지 알림"  # 이메일 제목
    body = f"<b>{now} 기준 Shodan 데이터 변경 사항입니다.</b><br><br><pre>{text}</pre>"  # 본문 HTML

    smtp = smtplib.SMTP('smtp.naver.com', 587)  # SMTP 서버 연결(naver)
    smtp.starttls()  # TLS 보안 연결
    smtp.login(SEND_EMAIL, SEND_PWD)  # 로그인

    msg = MIMEMultipart()  # 이메일 객체 생성
    msg['Subject'] = subject  # 제목
    msg['From'] = SEND_EMAIL  # 발신자
    msg['To'] = recv_email  # 수신자
    msg.attach(MIMEText(body, 'html'))  # 본문 첨부

    smtp.sendmail(SEND_EMAIL, recv_email, msg.as_string())  # 이메일 전송
    smtp.quit()  # SMTP 종료
    print(f"이메일 전송 완료: {len(text)} chars")

# 포트별 이전 총 호스트 수 조회
def get_previous_total(port):
    
    total_doc = totals_collection.find_one({"port": port})  # MongoDB 조회
    return total_doc['total'] if total_doc else 0  # 없으면 0 반환

#포트별 총 호스트 수 및 증감량 업데이트
def update_totals(port, current_total, diff):
    totals_collection.update_one(
        {"port": port},  # 포트 기준
        {"$set": {"total": current_total, "diff": diff, "last_updated": datetime.now()}},  # 업데이트
        upsert=True  # 문서 없으면 새로 생성
    )

#호스트 정보 포트별 컬렉션에 저장
def save_hosts_to_mongo(port, hosts):
    collection = db[f'port_{port}']  # 컬렉션 생성
    saved_count = 0
    for host in hosts:
        data = {
            "ip": host['ip_str'],  # IP
            "port": host['port'],  # 포트
            "org": host.get('org', 'N/A'),  # 조직
            "location": host['location']['country_name'],  # 국가
            "hostnames": ', '.join(host['hostnames']) if host['hostnames'] else 'N/A',  # 호스트명
            "last_seen": datetime.now()  # 저장 시각
        }
        collection.update_one(
            {"ip": data["ip"]},
            {"$set": data}, upsert=True  # IP 기준 업데이트
        )

        saved_count += 1
    return saved_count  # 저장된 수 반환

def get_examples(port: int):
    """포트별 예시 IP 2개 반환"""
    collection = db[f'port_{port}']
    ips = [doc.get('ip') for doc in collection.find().limit(2)]
    return ', '.join(ips) if ips else 'None'

# Shodan 보고서 생성 
def generate_shodan_report():
    stats = api.count("country:KR", facets=["port:5"])  # 상위 5개 포트 통계
    top_ports = [facet['value'] for facet in stats['facets']['port']]  # 포트 번호 추출

    lines = ["Shodan 포트 감지 종합 보고서"]
    lines.append(f"수신 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    for port in top_ports:
        query = f"country:KR port:{port}"  # 검색 쿼리
        results = api.search(query)  # Shodan 검색
        current_total = results['total']  # 현재 호스트 수
        previous_total = get_previous_total(port)  # 이전 호스트 수
        diff = current_total - previous_total  # 증감 계산

        save_hosts_to_mongo(port, results['matches'])  # MongoDB 저장
        update_totals(port, current_total, diff)  # totals 업데이트

        lines.append(f"포트 {port}: 총 {current_total}개 ({'+' if diff>0 else ''}{diff} 증감)")  # 요약
        lines.append(f"  └ 예시 IP: {get_examples(port)}\n")  # 예시 IP

    return "\n".join(lines)  # 보고서 문자열 반환

# Flask 라우트 
@app.route('/')
def index():
    return render_template("email_form.html")  # 이메일 폼 렌더링

@app.route('/send_email', methods=['POST'])
def send_email_route():
    recipient = request.form['recipient']  # 수신자 이메일 가져오기
    report_text = generate_shodan_report()  # 보고서 생성
    send_email_message(report_text, recipient)  # 이메일 전송
    return f"Shodan 알림 이메일이 {recipient}에게 전송되었습니다!"

# Slack 메시지 전송 
def send_slack_message(channel: str, text: str):
    client = WebClient(token=SLACK_API_TOKEN)  # Slack 클라이언트 생성
    client.chat_postMessage(channel=channel, text=text[:3800])  # 메시지 전송
    print(f"[SLACK] 전송 완료: {len(text)} chars")

# 통합 알림 전송
def execute_notification():
    lines = ["Shodan 포트 감지 종합 보고서"]
    lines.append(f"수신 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    ports_data = list(totals_collection.find().sort("port"))  # 모든 포트 데이터 조회
    for data in ports_data:
        port = data.get('port')  # 포트
        diff = data.get('diff', 0)  # 증감
        total = data.get('total', 'N/A')  # 총 호스트 수
        diff_str = f"({'+' if diff>0 else ''}{diff} 증감)"
        lines.append(f"포트 {port}: 총 {total}개 {diff_str}")  # 요약
        lines.append(f"  └ 예시 IP: {get_examples(port)}\n")  # 예시 IP

    final_msg = "\n".join(lines)  #개행 추가
    send_slack_message(SLACK_CHANNEL, final_msg)  # Slack 전송
    send_email_message(final_msg, SEND_EMAIL)  # 이메일 전송
    print("종합 보고서 알림 전송 완료")


def main():
    stats = api.count("country:KR", facets=["port:5"])  # 상위 5개 포트 조회, facets옵션은 쿼리 조건에서 자주 등장하는 값들을 집계하여 반환
    top_ports = [facet['value'] for facet in stats['facets']['port']]
    print(f"선정된 상위 5개 포트: {top_ports}")

    for port in top_ports:
        print(f"\n==== 포트 {port} 검색 및 저장 시작 ====")
        query = f"country:KR port:{port}"
        results = api.search(query)  # Shodan 검색
        current_total = results['total']  # 현재 총 호스트
        previous_total = get_previous_total(port)  # 이전 총 호스트
        diff = current_total - previous_total  # 증감 계산
        saved_count = save_hosts_to_mongo(port, results['matches'])  # 저장
        update_totals(port, current_total, diff)  # totals 업데이트

        print(f"총 {current_total}개 호스트 발견, {saved_count}개 문서 저장/업데이트 완료")
        print(f"변화 감지: 이전 {previous_total} -> 현재 {current_total}, 증감: {diff}")

    execute_notification()  # Slack + 이메일 알림 전송
    client.close()  # MongoDB 연결 종료
    print("\nMongoDB 연결 종료.")

#  Flask 서버 실행
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
