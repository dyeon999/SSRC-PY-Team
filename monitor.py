# monitor.py
import os, requests
from datetime import datetime
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

load_dotenv()
APIKEY    = os.getenv("SHODAN_API_KEY")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

client = MongoClient(MONGO_URI)
db  = client["shodan_facets"]
col = db["top_ports"]
col.create_index([("country", ASCENDING), ("created_at", ASCENDING)])


SHODAN_URL = "https://api.shodan.io/shodan/host/count"
COUNTRY = "KR"
TOPN    = 10

# Shodan API로 데이터 수집
def fetch_top_ports(country=COUNTRY, topn=TOPN):
    params = {"key": APIKEY, "query": f"country:{country}", "facets": f"port:{topn}"}
    r = requests.get(SHODAN_URL, params=params, timeout=15)
    r.raise_for_status()
    facet = r.json().get("facets", {}).get("port", [])
    return {str(i["value"]): int(i["count"]) for i in facet}

# 디비에 데이터 삽입
def take_snapshot():
    ports = fetch_top_ports()
    doc = {"country": COUNTRY, "ports": ports, "created_at": datetime.utcnow()}
    res = col.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    print(f"[DB] inserted_id={doc['_id']} created_at={doc['created_at']}")  #로그확인
    return doc

#최신 데이터 2개
def latest_docs(n=2):
    return list(col.find({"country": COUNTRY}).sort("created_at", -1).limit(n))

#데이터 비교
def diff(prev: dict, curr: dict):
    ports = set(prev) | set(curr)
    inc, dec = {}, {}
    for p in ports:
        a, b = prev.get(p, 0), curr.get(p, 0)
        if b > a: inc[p] = b - a
        elif b < a: dec[p] = a - b
    return inc, dec


