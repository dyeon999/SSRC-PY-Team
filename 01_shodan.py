import shodan 
import os 
from dotenv import load_dotenv

load_dotenv() 

API_key = os.getenv("SHODAN_API_KEY")

api = shodan.Shodan(API_key)

ip = "8.8.8.8"
result = api.host(ip)

print("IP :", result['ip_str'])
print("열린 포트:", [item['port'] for item in result['data']])
