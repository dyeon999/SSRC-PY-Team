import shodan
from pymongo import MongoClient

# API 키 초기화
SHODAN_API_KEY = 'Bh2LpaIgqG4x4fxhsOZEbWNwkChvQFR7'
api = shodan.Shodan(SHODAN_API_KEY)

# MongoDB 연결
client = MongoClient('mongodb://localhost:27017/')
db = client['shodan_db']
collection = db['kr_search_results']

# 여러 포트를 쉼표(,)로 구분하여 하나의 쿼리로 통합
query = "country:KR port:7547"
print(f"통합 포트로 검색 중: {query}\n")

# 검색 쿼리를 한 번만 실행
results = api.search(query)

print(f"총 {results['total']}개의 호스트가 발견되었습니다.")

# 검색된 각 호스트에 대해 반복하며 MongoDB에 데이터 삽입
for host in results['matches']:
    data = {
        "ip": host['ip_str'],
        "port": host['port'],
        "org": host.get('org', 'N/A'),
        "location": host['location']['country_name'],
        "hostnames": ', '.join(host['hostnames']) if host['hostnames'] else 'N/A'
    }
    
    # insert_one 함수를 반복문 안에서 호출하여 각 호스트를 개별 문서로 저장
    collection.insert_one(data)
    print(f"- IP {data['ip']} 데이터 저장 완료")

print(f"\n총 {len(results['matches'])}개의 문서가 MongoDB에 성공적으로 저장되었습니다.")

# MongoDB 연결 종료
client.close()