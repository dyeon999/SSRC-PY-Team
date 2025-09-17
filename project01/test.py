import shodan
from pymongo import MongoClient

# API 키 초기화
SHODAN_API_KEY = 'Bh2LpaIgqG4x4fxhsOZEbWNwkChvQFR7'
api = shodan.Shodan(SHODAN_API_KEY)

# MongoDB 연결
client = MongoClient('mongodb://localhost:27017/')
db = client['shodan_db']

totals_db = db['totals']

# 검색할 포트 목록  top 5
ports = [7547, 9000, 8009, 8008, 8443]


# Shodan 검색 및 MongoDB 저장 로직
for port in ports:
    # 이전 total 값 불러오기
    total_doc = totals_db.find_one({"port": port})
    if total_doc:
        previous_total = total_doc['total']
    else:
        previous_total = 0

    # 현재 검색 결과
    results = api.search(f"country:KR port:{port}")
    current_total = results['total']


    # total 값 업데이트
    totals_db.update_one(
        {"port": port},
        {"$set": {"total": current_total}},
        upsert=True
    )
    

    # 포트별 컬렉션 이름 지정
    collection = db[f'port : {port}']
    print(f"\n==== 포트 {port} 검색 및 저장 시작 ====")

    # Shodan 쿼리 생성
    query = f"country:KR port:{port}"
    print(f"쿼리: {query}")
    
    # 검색 쿼리 실행
    results = api.search(query)
    print(f"총 {results['total']}개의 호스트가 발견되었습니다.")
    


    saved_count = 0
    # 검색 결과 반복
    for host in results['matches']:
        data = {
            "ip": host['ip_str'],
            "port": host['port'],
            "org": host.get('org', 'N/A'),
            "location": host['location']['country_name'],
            "hostnames": ', '.join(host['hostnames']) if host['hostnames'] else 'N/A'
        }
        
        # 데이터 저장
        # update_one() 함수와 upsert=True 옵션으로 데이터 저장
        collection.update_one(
            {"ip": data["ip"]},  # 검색 조건: 현재 호스트의 IP와 일치하는 문서
            {"$set": data},      # 업데이트할 데이터: 현재 호스트의 모든 데이터
            upsert=True          # upsert 옵션을 True로 설정 업데이트
        )

        saved_count += 1
        print(f"- IP {data['ip']} 데이터 저장 완료")
    
     # 증감 계산
    diff = current_total - previous_total
    if diff > 0:
        print(f"포트 {port}: {diff}개 증가")
    elif diff < 0:
        print(f"포트 {port}: {-diff}개 감소")
    else:
        print(f"포트 {port}: 변화 없음")
    
    print(f"\n총 {saved_count}개의 문서가 MongoDB에 성공적으로 저장되었습니다.")
    print("====================================")

# MongoDB 연결 종료
client.close()
print("\nMongoDB 연결이 종료되었습니다.")

