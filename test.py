from pymongo import MongoClient
import requests                                               
import smtplib                                         
from email.mime.text import MIMEText                                   
import schedule                                                          
import time                                                                                          

client = MongoClient("mongodb://localhost:27017/")             
db = client["shodan_db"]                                                                    
collection = db["webcam_results"]                              

SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/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" 

def slack_upload(message):                                            
    payload = {"text": message}              
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)                       
    if response.status_code != 200:
        print(f"Slack 전송에 실패하였습니다.: {response.status_code}, {response.text}")
    else:
        print(f"Slack 전송에 성공하였습니다.: {message}")


SMTP_SERVER = "smtp.gmail.com"                   
SMTP_PORT = 587          
EMAIL_USER = "97dmstjs2@gmail.com"           
EMAIL_PASS = ""                                   
TO_EMAIL = "cile0629@naver.com"

def send_email(subject, body):        
    msg = MIMEText(body, "plain")                                                                       
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = TO_EMAIL

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:  
        server.starttls()   
        server.login(EMAIL_USER, EMAIL_PASS)                                
        server.sendmail(EMAIL_USER, TO_EMAIL, msg.as_string())

# 알림 기능

def alert():
    results = collection.find().sort("_id", -1).limit(5)
    for r in results:
        msg = f"열린 포트를 발견했습니다.\nIP: {r['ip']}\nPort: {r['port']}\nOrg: {r.get('org', 'N/A')}\nlocation: {r['location']}"

        slack_upload(msg)
        send_email("[경고] 포트가 열려있습니다.", msg)

    print("알림 발송을 완료했습니다.")


# 작업 예약 기능 (5초(?)마다 실행)

schedule.every(1).minutes.do(alert)

alert()

print("자동화를 시작합니다.")
while True:
    schedule.run_pending()
    time.sleep(1)
