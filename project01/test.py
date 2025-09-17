import shodan
from pymongo import MongoClient

# API 키 초기화
SHODAN_API_KEY = 'f1dhVxRDYX74VO71TO8rXLYAfihEJXkl'
api = shodan.Shodan(SHODAN_API_KEY)

# MongoDB 연결
client = MongoClient('mongodb://localhost:27017/') # MongoDB 서버에 연결
db = client['shodan_db'] # 'shodan_db' 데이터베이스에 접근
totals_db = db['totals'] # 포트별 총 개수를 기록할 'totals'

#Shodan에서 country:KR 기준으로 TOP PORTS 5개 가져오기
stats = api.count("country:KR", facets=["port:5"])

ports = []
for facet in stats['facets']['port']:
    value = facet['value']
    ports.append(value)

print("선정된 상위 5개 포트:", ports)

# Shodan 검색 및 MongoDB 저장 로직
for port in ports: # ports 리스트의 각 포트 번호를 반복
    # 1. 이전 total 값 불러오기
    total_doc = totals_db.find_one({"port": port})
    if total_doc:
        previous_total = total_doc['total']
    else:
        previous_total = 0

    # 2. 현재 검색 결과
    query = f"country:KR port:{port}"
    results = api.search(query) 
    current_total = results['total']

    # 3. 포트별 컬렉션에 개별 호스트 정보 저장
    collection = db[f'port_{port}']
    print(f"\n==== 포트 {port} 검색 및 저장 시작 ====")
    print(f"쿼리: {query}")
    print(f"총 {results['total']}개의 호스트가 발견되었습니다.")
    
    saved_count = 0
    for host in results['matches']:
        data = {
            "ip": host['ip_str'],
            "port": host['port'],
            "org": host.get('org', 'N/A'),
            "location": host['location']['country_name'],
            "hostnames": ', '.join(host['hostnames']) if host['hostnames'] else 'N/A'
        }
        
        collection.update_one(
            {"ip": data["ip"]},
            {"$set": data},
            upsert=True
        )

        saved_count += 1
        print(f"- IP {data['ip']} 데이터 저장 완료")
        
    # 4. 증감 계산
    diff = current_total - previous_total
    if diff > 0:
        print(f"포트 {port}: {diff}개 증가")
    elif diff < 0:
        print(f"포트 {port}: {-diff}개 감소")
    else:
        print(f"포트 {port}: 변화 없음")

    # 5. total 값 업데이트
    totals_db.update_one(
        {"port": port},
        {"$set": {"total": current_total, "diff": diff}},
        upsert=True
    )
    
    print(f"\n총 {saved_count}개의 문서가 MongoDB에 성공적으로 저장되었습니다.")
    print("====================================")

# MongoDB 연결 종료
client.close()
print("\nMongoDB 연결이 종료되었습니다.")
