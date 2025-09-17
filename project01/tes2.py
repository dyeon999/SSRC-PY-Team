import shodan

# Shodan API 키를 입력하세요.
SHODAN_API_KEY = "Bh2LpaIgqG4x4fxhsOZEbWNwkChvQFR7"

api = shodan.Shodan(SHODAN_API_KEY)


# facets 파라미터로 포트 통계 요청
query = 'country:KR'
facets = 'port'
results = api.search(query, facets=facets)

# Top Ports 출력
if 'facets' in results and 'port' in results['facets']:
    print("Top Ports in KR:")
    for port_info in results['facets']['port']:
        print(f"Port: {port_info['value']}, Count: {port_info['count']}")
else:
    print("Top Ports 정보가 없습니다.")