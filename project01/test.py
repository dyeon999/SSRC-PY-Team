import shodan
from pymongo import MongoClient

#Shodan API 초기화
SHODAN_API_KEY = 'LTbqpWEzkE6yj43dnyH9HGYnOumnFrB8'
api = shodan.Shodan(SHODAN_API_KEY)  # Shodan API 객체 생성

# MongoDB 연결
client = MongoClient('mongodb://localhost:27017/')  # MongoDB 서버 연결
db = client['shodan_db']  # 'shodan_db' 데이터베이스
totals_db = db['totals']  # 포트별 총 개수를 기록할 'totals'


# MongoDB totals 컬렉션에서 해당 포트의 이전 total 값 가져오기
def get_previous_total(port):
    total_doc = totals_db.find_one({"port": port})  # 해당 포트의 문서 검색
    
    if total_doc:          # 문서가 존재하면
        previous_total = total_doc['total']  # total 값 가져오기
    else:                  # 문서가 없으면
        previous_total = 0  # 0으로 초기화
    
    return previous_total


# MongoDB totals 컬렉션에 현재 total과 증감(diff) 업데이트
def update_totals(port, current_total, diff):
    totals_db.update_one(
        {"port": port},
        {"$set": {"total": current_total, "diff": diff}},
        upsert=True  # 없으면 새로 생성
    )


# 포트별 컬렉션에 호스트 정보를 저장
def save_hosts_to_mongo(port, hosts):
    collection = db[f'port_{port}']  # 포트별 컬렉션 생성/선택
    saved_count = 0

    for host in hosts:
        data = {
            "ip": host['ip_str'],  # IP 주소
            "port": host['port'],  # 포트 번호
            "org": host.get('org', 'N/A'),  # 조직 정보 없으면 'N/A'
            "location": host['location']['country_name'],  # 국가
            "hostnames": ', '.join(host['hostnames']) if host['hostnames'] else 'N/A'  # 호스트명
        }
        # IP 기준으로 문서 업데이트 (이미 있으면 수정, 없으면 새로 생성)
        collection.update_one(
            {"ip": data["ip"]},
            {"$set": data},
            upsert=True
        )
        saved_count += 1  # 저장된 문서 수 카운트

    return saved_count


def main():
    ports = []
    # Shodan에서 한국 기준 상위 5개 포트 가져오기
    stats = api.count("country:KR", facets=["port:5"])
    for facet in stats['facets']['port']:
        ports.append(facet['value'])  # 포트 번호 추출하여 리스트에 추가

    print("선정된 상위 5개 포트:", ports)

    for port in ports:
        print(f"\n==== 포트 {port} 검색 및 저장 시작 ====")

        
        # Shodan에서 포트 검색
        query = f"country:KR port:{port}"  # Shodan 검색 쿼리
        results = api.search(query)        # 검색 수행
        current_total = results['total']   # 현재 총 호스트 수

        print(f"쿼리: {query}")
        print(f"총 {current_total}개의 호스트 발견")


        # MongoDB에 호스트 정보 저장
        saved_count = save_hosts_to_mongo(port, results['matches'])
        print(f"\n총 {saved_count}개의 문서 저장 완료")

        # 이전 total과 비교하여 증감 계산
        previous_total = get_previous_total(port)  # 이전 total 가져오기
        diff = current_total - previous_total     # 증감 계산
        if diff > 0:
            print(f"포트 {port}: {diff}개 증가")
        elif diff < 0:
            print(f"포트 {port}: {-diff}개 감소")
        else:
            print(f"포트 {port}: 변화 없음")

        # totals 컬렉션 업데이트
        update_totals(port, current_total, diff)
        print("====================================")

    # MongoDB 연결 종료
    client.close()
    print("\nMongoDB 연결이 종료되었습니다.")

if __name__ == "__main__":
    main()
