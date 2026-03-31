from flask import Flask, render_template, request, redirect, session, jsonify, Response
import mysql.connector
import requests  # to call Rasa
import csv
from io import StringIO
from flask import render_template
import yaml
import subprocess
from flask import Flask, jsonify
import time
from flask import flash

app = Flask(__name__)
app.secret_key = "secret123"


# 📁 NLU file path
NLU_FILE = "data/nlu.yml"

def connect_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="python_bank_chatbot")


# ✅ User UI-Index.html
@app.route("/")
def home():
    return render_template("index.html")

#User query Response - whenever a user type a query it will give ans from faq if exist otherwise from rasa bot it
#will response and that query and response message will store into databse 
#The FAQ system is a static knowledge source for your chatbot and users, giving quick 
# and reliable answers to commonly asked questions while reducing the need for AI processing every time.
@app.route("/send_query", methods=["POST"])
def send_query():
    data = request.get_json()
    message = data.get("message", "")
    user_id = 1

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ Check FAQ first
    cursor.execute("SELECT answer FROM faqs WHERE question = %s", (message,))
    faq = cursor.fetchone()

    if faq:
        bot_response = faq["answer"]
        intent = "faq"
        confidence = 1.0

    else:
        # 2️⃣ Get intent & confidence from Rasa
        parse_response = requests.post(
            "http://localhost:5005/model/parse",
            json={"text": message}
        ).json()

        intent = parse_response.get("intent", {}).get("name", "unknown")
        confidence = parse_response.get("intent", {}).get("confidence", 0.0)

        # 3️⃣ Get bot response from Rasa
        rasa_response = requests.post(
            "http://localhost:5005/webhooks/rest/webhook",
            json={"sender": "user", "message": message}
        ).json()

        if rasa_response:
            bot_response = " ".join([r.get("text", "") for r in rasa_response])
        else:
            bot_response = "Sorry, I didn't understand that."

    # 4️⃣ Save to DB
    cursor.execute("""
        INSERT INTO user_queries (message, intent, confidence, response)
        VALUES (%s, %s, %s, %s)
    """, (message, intent, confidence, bot_response))

    conn.commit()
    conn.close()

    # 5️⃣ Send response back to UI
    return jsonify({
        "response": bot_response,
        "intent": intent,
        "confidence": confidence
    })

# ADMIN - LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session["admin"] = username
            return redirect("/admin")
        else:
            return "Invalid Login"

    return render_template("login.html")

# ADMIN - LOGOUT
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/login")


# ADMIN DASHBOARD
@app.route("/admin")
def admin():
    if "admin" not in session:
        return redirect("/login")
    return render_template("admin.html")


# Dashboard cards 
@app.route("/DASHBOARD")
def DASHBOARD():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM user_queries")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(confidence) FROM user_queries")
    avg_conf = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(DISTINCT intent) FROM user_queries")
    intents = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM faqs")
    faqs = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        "total": total,
        "success": round(avg_conf * 100, 2),
        "intents": intents,
        "faqs": faqs
    })

#ADMIN -Training data
@app.route("/training_data")
def training_data():
    if "admin" not in session:
        return redirect("/login")

    import yaml

    NLU_FILE = "data/nlu.yml"

    try:
        with open(NLU_FILE, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        nlu_data = data.get("nlu", [])

    except Exception as e:
        print("Error:", e)
        nlu_data = []

    return render_template("training_data.html", nlu_data=nlu_data)


# ➕ ADD EXAMPLE
# ===============================
@app.route("/add_example")
def add_example():
    intent = request.args.get("intent")
    example = request.args.get("example")

    try:
        with open(NLU_FILE, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        for item in data["nlu"]:
            if item["intent"] == intent:
                item["examples"] += f"\n- {example}"

        with open(NLU_FILE, "w", encoding="utf-8") as file:
            yaml.dump(data, file, allow_unicode=True)

    except Exception as e:
        print("Error adding example:", e)

    return redirect("/training_data")


# ===============================
# ❌ DELETE EXAMPLE
# ===============================
@app.route("/delete_example")
def delete_example():
    intent = request.args.get("intent")
    example = request.args.get("example")

    try:
        with open(NLU_FILE, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        for item in data["nlu"]:
            if item["intent"] == intent:
                examples = item["examples"].split("\n")

                # remove matching example
                examples = [e for e in examples if example.strip() not in e.strip()]

                item["examples"] = "\n".join(examples)

        with open(NLU_FILE, "w", encoding="utf-8") as file:
            yaml.dump(data, file, allow_unicode=True)

    except Exception as e:
        print("Error deleting example:", e)

    return redirect("/training_data")


# ===============================
# ❌ DELETE INTENT
# ===============================
@app.route("/delete_intent")
def delete_intent():
    intent = request.args.get("intent")

    try:
        with open(NLU_FILE, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        # remove intent
        data["nlu"] = [item for item in data["nlu"] if item["intent"] != intent]

        with open(NLU_FILE, "w", encoding="utf-8") as file:
            yaml.dump(data, file, allow_unicode=True)

    except Exception as e:
        print("Error deleting intent:", e)

    return redirect("/training_data")

# ===============================
# ➕ ADD INTENT
# ===============================
@app.route("/add_intent", methods=["POST"])
def add_intent():
    if "admin" not in session:
        return redirect("/login")

    intent = request.form.get("intent").strip()
    examples = request.form.get("examples")
    response = request.form.get("response")

    import yaml

    try:
        # =========================
        # 1️⃣ UPDATE NLU FILE
        # =========================
        with open("data/nlu.yml", "r", encoding="utf-8") as f:
            nlu_data = yaml.safe_load(f)

        found = False
        for item in nlu_data["nlu"]:
            if item["intent"] == intent:
                found = True
                new_examples = "\n".join(
                    [f"- {e.strip()}" for e in examples.split("\n") if e.strip()]
                )
                item["examples"] += "\n" + new_examples
                break

        if not found:
            new_intent = {
                "intent": intent,
                "examples": "\n".join(
                    [f"- {e.strip()}" for e in examples.split("\n") if e.strip()]
                )
            }
            nlu_data["nlu"].append(new_intent)

        with open("data/nlu.yml", "w", encoding="utf-8") as f:
            yaml.dump(nlu_data, f, allow_unicode=True)

        # =========================
        # =========================
        # 2️⃣ UPDATE DOMAIN FILE (SAFE)
        # =========================
        with open("domain.yml", "r", encoding="utf-8") as f:
            domain_data = yaml.safe_load(f)

        if not domain_data:
            domain_data = {}

        action_name = f"utter_{intent}"

        # ✅ Ensure intents list exists
        if "intents" not in domain_data:
            domain_data["intents"] = []

        # ✅ Add intent WITHOUT overwriting
        if intent not in domain_data["intents"]:
            domain_data["intents"].append(intent)

        # ✅ Ensure responses exist
        if "responses" not in domain_data:
            domain_data["responses"] = {}

        # ✅ Add response ONLY if not exists
        if action_name not in domain_data["responses"]:
            domain_data["responses"][action_name] = [
                {"text": response}
            ]

        # 💾 Save safely
        with open("domain.yml", "w", encoding="utf-8") as f:
            yaml.dump(domain_data, f, allow_unicode=True, sort_keys=False)

        # =========================
        # 3️⃣ UPDATE STORIES FILE
        # =========================
        with open("data/stories.yml", "r", encoding="utf-8") as f:
            stories_data = yaml.safe_load(f)

        if not stories_data:
            stories_data = {"stories": []}

        new_story = {
            "story": f"{intent} story",
            "steps": [
                {"intent": intent},
                {"action": action_name}
            ]
        }

        exists = any(
            s.get("story") == f"{intent} story"
            for s in stories_data.get("stories", [])
        )

        if not exists:
            stories_data["stories"].append(new_story)

        with open("data/stories.yml", "w", encoding="utf-8") as f:
            yaml.dump(stories_data, f, allow_unicode=True)

    except Exception as e:
        print("ERROR:", e)

    return redirect("/training_data")
# ===============================
#retrain_model
RASA_PATH = r"H:\Infosys\banking-chatbot\rasa_env\Scripts\rasa.exe"
RASA_SERVER_URL = "http://127.0.0.1:5005/model"  # Rasa default API for model reload

@app.route("/retrain_model")
def retrain_model():
    import os

    try:
        # Step 1: train Rasa model
        result = subprocess.run(
            [RASA_PATH, "train"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return jsonify({"status": "error", "message": result.stderr})

        # Step 2: reload latest model
        try:
            latest_model = os.path.join("models", "latest.tar.gz")
            reload_resp = requests.post(RASA_SERVER_URL, json={"model": latest_model})
            if reload_resp.status_code == 200:
                return jsonify({"status": "success", "message": "Model trained and reloaded successfully!"})
            else:
                return jsonify({"status": "warning", "message": "Model trained but failed to reload. Restart Rasa server manually."})
        except Exception as e:
            return jsonify({"status": "warning", "message": f"Model trained but failed to reload: {str(e)}"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    
#USER_QUERIES
#Open user_queries page
@app.route("/user_queries")
def user_queries():
    if "admin" not in session:
        return redirect("/login")
    return render_template("user_queries.html")

#Open user_queries get information
@app.route("/get_queries")
def get_queries():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT message, intent, confidence, response, timestamp
        FROM user_queries
        ORDER BY timestamp DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    data = []
    for r in rows:
        data.append({
            "message": r["message"],
            "intent": r["intent"],
            "confidence": r["confidence"],
            "response": r["response"],
            "timestamp": r["timestamp"]
        })

    return jsonify(data)

# ✅ CSV Export Route
@app.route("/export_csv")
def export_csv():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM user_queries")
    rows = cursor.fetchall()

    conn.close()

    si = StringIO()
    writer = csv.writer(si)

    # Header
    writer.writerow(["Message", "Intent", "Confidence", "Response", "Timestamp"])

    # Data
    for row in rows:
        writer.writerow([
            row["message"],
            row["intent"],
            row["confidence"],
            row["response"],
            row["timestamp"]
        ])

    output = si.getvalue()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=user_queries.csv"}
    )


#FAQs
# Get all FAQs
@app.route("/faqs")
def faqs():
    if "admin" not in session:
        return redirect("/login")
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM faqs")
    data = cursor.fetchall()
    conn.close()
    return render_template("faqs.html", faqs=data)

# Add FAQ
@app.route("/add_faq", methods=["POST"])
def add_faq():
    if "admin" not in session:
        return redirect("/login")

    question = request.form.get("question")
    answer = request.form.get("answer")

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO faqs (question, answer) VALUES (%s, %s)", (question, answer))
    conn.commit()
    conn.close()

    flash("FAQ added successfully!", "success")   # ✅
    return redirect("/faqs")

@app.route("/delete_faq/<int:faq_id>")
def delete_faq(faq_id):
    if "admin" not in session:
        return redirect("/login")

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM faqs WHERE id=%s", (faq_id,))
    conn.commit()
    conn.close()

    flash("FAQ deleted successfully!", "danger")  # ✅
    return redirect("/faqs")

#analytics_page
@app.route("/analytics_page")
def analytics_page():
    if "admin" not in session:
        return redirect("/login")
    return render_template("analytics_page.html")

#analytics_page
# ANALYTICS DATA (CHARTS)

@app.route("/analytics_data")
def analytics_data():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Top intents
    cursor.execute("""
        SELECT intent, COUNT(*) as count
        FROM user_queries
        GROUP BY intent
        ORDER BY count DESC
    """)
    intents = cursor.fetchall()

    # Last 14 days data
    cursor.execute("""
        SELECT DATE(timestamp) as date, COUNT(*) as count
        FROM user_queries
        WHERE timestamp >= NOW() - INTERVAL 14 DAY
        GROUP BY DATE(timestamp)
        ORDER BY date
    """)
    daily = cursor.fetchall()

    conn.close()

    return jsonify({
        "intents": intents,
        "daily": daily
    })



@app.route("/export_analytics")
def export_analytics():
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    # Top intents
    cursor.execute("""
        SELECT intent, COUNT(*) as count
        FROM user_queries
        GROUP BY intent
        ORDER BY count DESC
    """)
    intents = cursor.fetchall()

    # Daily queries
    cursor.execute("""
        SELECT DATE(timestamp) as date, COUNT(*) as count
        FROM user_queries
        WHERE timestamp >= NOW() - INTERVAL 14 DAY
        GROUP BY DATE(timestamp)
        ORDER BY date
    """)
    daily = cursor.fetchall()

    conn.close()

    # Calculate total for percentage
    total = sum(i["count"] for i in intents)

    from io import StringIO
    import csv

    si = StringIO()
    writer = csv.writer(si)

    # ✅ Section 1: Top Intents
    writer.writerow(["Top Intents"])
    writer.writerow(["Intent", "Count"])
    for i in intents:
        writer.writerow([i["intent"], i["count"]])

    writer.writerow([])

    # ✅ Section 2: Intent Distribution (Pie Data)
    writer.writerow(["Intent Distribution (%)"])
    writer.writerow(["Intent", "Percentage"])

    for i in intents:
        percent = (i["count"] / total) * 100 if total > 0 else 0
        writer.writerow([i["intent"], f"{percent:.2f}%"])

    writer.writerow([])

    # ✅ Section 3: Daily Queries
    writer.writerow(["Daily Queries (Last 14 Days)"])
    writer.writerow(["Date", "Count"])

    for d in daily:
        writer.writerow([d["date"], d["count"]])

    output = si.getvalue()

    from flask import Response
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=analytics_report.csv"}
    )


if __name__ == "__main__":
    app.run(debug=True)