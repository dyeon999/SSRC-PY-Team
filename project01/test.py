import shodan
from pymongo import MongoClient

# API 키 초기화
SHODAN_API_KEY = 'f1dhVxRDYX74VO71TO8rXLYAfihEJXkl'
api = shodan.Shodan(SHODAN_API_KEY)

# MongoDB 연결
client = MongoClient('mongodb://localhost:27017/') # MongoDB 서버에 연결
db = client['shodan_db'] # 'shodan_db' 데이터베이스에 접근

totals_db = db['totals'] # 포트별 총 개수를 기록할 'totals' 컬렉션

# 검색할 포트 목록 top 5
ports = [7547, 9000, 8009, 8008, 8443]

# Shodan 검색 및 MongoDB 저장 로직
for port in ports: # ports 리스트의 각 포트 번호를 반복
    # 1. 이전 total 값 불러오기
    # totals 컬렉션에서 현재 포트의 이전 기록을 찾음
    total_doc = totals_db.find_one({"port": port})
    if total_doc:
        previous_total = total_doc['total'] # 이전 기록이 있으면 total 값을 가져옴
    else:
        previous_total = 0 # 없으면 0으로 초기화

    # 2. 현재 검색 결과
    # Shodan API를 호출하여 현재 시점의 총 호스트 수를 가져옴
    query = f"country:KR port:{port}"
    results = api.search(query) 
    current_total = results['total'] # 현재 검색된 호스트의 총 개수

   
    # 3. 포트별 컬렉션에 개별 호스트 정보 저장
    collection = db[f'port_{port}'] # 예: port_7547 컬렉션에 접근
    print(f"\n==== 포트 {port} 검색 및 저장 시작 ====")
    
    print(f"쿼리: {query}")
    
     
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
            upsert=True          # upsert 옵션을 True로 설정
        )

        saved_count += 1
        print(f"- IP {data['ip']} 데이터 저장 완료")
        
    # 4. 증감 계산
    # 이전 총 개수와 현재 총 개수를 비교하여 증감량 계산
    diff = current_total - previous_total
    if diff > 0:
        print(f"포트 {port}: {diff}개 증가")
    elif diff < 0:
        print(f"포트 {port}: {-diff}개 감소")
    else:
        print(f"포트 {port}: 변화 없음")

    # 5. total 값 업데이트
    # totals 컬렉션에 현재 포트의 총 개수를 업데이트하거나 새로 삽입
    totals_db.update_one(
        {"port": port},
        {"$set": {"total": current_total, "diff":diff}},
        upsert=True # 문서가 없으면 새로 생성
    )
    
    print(f"\n총 {saved_count}개의 문서가 MongoDB에 성공적으로 저장되었습니다.")
    print("====================================")
    

# MongoDB 연결 종료
client.close()
print("\nMongoDB 연결이 종료되었습니다.")