import shodan
from pymongo import MongoClient
from pprint import pprint
import time


# DB 초기화
client = MongoClient('mongodb://localhost:27017/')
db = client['test']

# SHODAN 설정
SHODAN_API_KEY = 'f1dhVxRDYX74VO71TO8rXLYAfihEJXkl'
api = shodan.Shodan(SHODAN_API_KEY)

query_total = 0
new_total = 0
# ports = [80,443,3306,22,8080]
ports = {80 : 0,
         443: 0,
         135: 0,
         22: 0,
          70: 0}

def save(port):
    collection = db[f'{port}']
    
    query = f'country:"KR" port:"{port}"'

    results = api.search(query)

    query_total = ports[port]
    # 혹은 테이블 만들고 
    # query_total = collection.find() 

    new_total = results['total']
    
    diff = abs(query_total - new_total)

    if query_total == 0:
        print(f"새로운 포트 {port}번 {diff}개 감지")
    elif query_total > new_total:
        print(f"포트 {port}번 {diff}개 닫힘 감지")
    elif query_total < new_total:
        print(f"포트 {port}번 {diff}개 열림 감지")
    
    ports[port] = new_total # 쿼리 개수 저장
    
    for result in results['matches']:
        ip = result["ip_str"]
        port = result["port"]
        country_code = result["location"]["country_code"]
        domain = result["domains"]

        collection.update_one(
            {"IP": ip}, # IP
            {"$set": {
                "PORTS": port,
                "domain": domain
                }},
            upsert=True # 만약 IP 이름 가진 데이터 없을 경우 추가
        )
        # ip port 국가코드 domain
    
if __name__ == '__main__':
    for port in ports.keys():
        save(port)




# 출력 부분은 이후 수정