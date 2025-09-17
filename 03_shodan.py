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

    for match in results['matches'][:5]:
        ip = match['ip_str']
        print('\n========================')
        print(f"[검색 결과] {ip}:{match['port']} ({match.get('org','알 수 없음')})")

        host_info = api.host(ip)
        print(f"IP: {host_info['ip_str']}")
        print(f"ISP:", host_info.get('isp'))
        print(f"국가:",host_info.get('country_name'))

        for service in host_info['data']:
            print("\n[포트 {service.get['port']}] {service.get['product','알 수 없음']} {service.get('version','')}")
            print("배너:",service.get('data','').spilt("\n")[0][:100])

            if "vulns" in service:
                for cve, details in service['vulns'].items():
                    print(f" - 취약점: {cve} (CVSS {details.get('cvss')})")
except shodan.APIError as e:
    print("API 에러:", e)
              
        