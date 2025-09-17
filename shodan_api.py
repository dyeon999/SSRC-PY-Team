import shodan
from pymongo import MongoClient

# DB 초기화
client = MongoClient('mongodb://localhost:27017/')
db = client['test']
collection = db['KR']

# # SHODAN 설정
SHODAN_API_KEY = 'nu9Gn9RlRJJIUtgjX4QYs22QGVUnq82s'
api = shodan.Shodan(SHODAN_API_KEY)

query = 'country:"KR"' # 쿼리값

results = api.search(query)

# 데이터 검색 및 저장
def save_db(query):
    results = api.search(query)

    try:
        for result in results['matches'][:50]:
            ip = result["ip_str"]
            port = result["port"]

            print(f"IP: {ip}")
            print(f"PORT: {port}")

            collection.update_one(
            {"IP": ip}, # IP
            {"$addToSet": {"PORTS": port}}, # PORTS를 배열로, 들어오는 값 추가
            upsert=True # 만약 IP 이름 가진 데이터 없을 경우 추가
            )
    except Exception as e:
        print(f"오류: {e}")


# 새롭게 열린 포트 확인
def detect_port(query):
    results = api.search(query)

    try:
        for result in results['matches'][:50]:
            ip = result["ip_str"]
            port = result["port"]

            print(f"IP: {ip}")
            print(f"PORT: {port}")

        a = collection.find_one(
            {"IP": ip},
            {"PORTS": port}
        )

        if a == None:
            print(f"새로운 포트 발견! {ip} --> {port} ")

    except Exception as e:
        print(f"오류: {e}")

