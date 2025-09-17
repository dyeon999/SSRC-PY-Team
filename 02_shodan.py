import shodan 
import os 
from dotenv import load_dotenv

load_dotenv() 

API_key = os.getenv("SHODAN_API_KEY")
api = shodan.Shodan(API_key)

query = 'port:3389 country:KR'

try:
    results = api.search(query)
    print(f"총 발견된 서버 수: {results['total']}")

    for match in results['matches'][:10]:
        ip = match['ip_str']
        port = match['port']
        org = match.get('org', '알 수 없음')
        product = match.get('product', '알 수 없음')
        version = match.get('veresion','알 수 없음')

        print(f"[{ip}:{port}] {org} / {product} {version}")

except shodan.APIError as e:
    print("API 에러:",e)
'''   
ip = "8.8.8.8"
result = api.host(ip)

print("IP :", result['ip_str'])
print("열린 포트:", [item['port'] for item in result['data']])'''