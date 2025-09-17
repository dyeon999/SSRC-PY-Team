# app.py
from flask import Flask, render_template, redirect, url_for, jsonify
import monitor

app = Flask(__name__)

#스냅샷 확인 후 비교
@app.get("/")
def home():
    docs = monitor.latest_docs(2)
    latest = docs[0] if docs else None#
    prev   = docs[1] if len(docs) > 1 else None
    inc, dec = {}, {}
    if latest and prev:
        inc, dec = monitor.diff(prev["ports"], latest["ports"])
        print("[DIFF]", "inc:", inc, "dec:", dec)   #log확인
    return render_template("index.html", doc=latest, inc=inc, dec=dec)

#데이터 삽입
@app.get("/snapshot/html")
def snapshot_html():
    monitor.take_snapshot()
    return redirect(url_for("home"))

#삽입 json
# @app.post("/snapshot")
# def snapshot_json():
#     doc = monitor.take_snapshot()
#     return jsonify(doc)

#비교 json
# @app.get("/compare")
# def compare_json():
#     docs = monitor.latest_docs(2)
#     if len(docs) < 2:
#         return jsonify({"error": "not enough data"}), 400
#     latest, prev = docs[0], docs[1]
#     inc, dec = monitor.diff(prev["ports"], latest["ports"])
    # return jsonify({"increase": inc, "decrease": dec})


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
