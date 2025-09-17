from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

# mongodb 연결
client = MongoClient('mongodb://localhost:27017/')
db = client['school_db']
collection = db['students']

# Slack API 토큰과 메시지를 보낼 채널 설정
SLACK_API_TOKEN = os.getenv("SLACK_API_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")




def send_message(channel, text):
    # WebClient 인스턴스 생성
    client = WebClient(token=SLACK_API_TOKEN)
    
    try:
        # 채널에 메시지 전송
        response = client.chat_postMessage(
            channel=channel,
            text=text
        )
        # 응답 출력
        print("Message sent successfully:", response["message"]["text"])
    except SlackApiError as e:
        # 에러 처리
        print("Error sending message:", e.response["error"])


result = collection.find_one({"name":"김철수"})

if result:
    msg = f"이름: {result['name']}, 나이: {result['age']}, 과목: {result['subjects']}, 등급: {result['grade']}"
    send_message(SLACK_CHANNEL, msg)
else:
    send_message(SLACK_CHANNEL, "학생을 찾을 수 없습니다.")




