from flask import Flask, render_template, request, redirect
from flask import send_from_directory
from flask import session
from firefly_model import count_fireflies_still, count_fireflies_pan 
import sqlite3
import os
import re

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS
app = Flask(__name__)
ALLOWED_EXTENSIONS = {"mp4","avi","mov","mkv"}
UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
app.secret_key = "firefly_secret"


def connect_db():
    return sqlite3.connect("database.db")
def init_db():
    db = connect_db()
    db.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        fullname TEXT,
        email TEXT UNIQUE
    )
    """)
    db.commit()

init_db()
# หน้า home
@app.route("/")
def home():
    return render_template("index.html")

# หน้า register
@app.route("/signup", methods=["GET","POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]
        fullname = request.form["fullname"]
        email = request.form["email"]

        db = connect_db()

        # password length
        if len(password) < 8:
            return render_template("signup.html", error="Password must be at least 8 characters")

        # email format
        email_pattern = r"[^@]+@[^@]+\.[^@]+"
        if not re.match(email_pattern, email):
            return render_template("signup.html", error="Invalid email format")

        # username already exists
        user = db.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if user:
            return render_template("signup.html", error="Username already exists")

        # email already exists
        email_check = db.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        if email_check:
            return render_template("signup.html", error="Email already registered")

        # insert user
        db.execute(
            "INSERT INTO users(username,password,fullname,email) VALUES(?,?,?,?)",
            (username,password,fullname,email)
        )

        db.commit()

        return redirect("/login")

    return render_template("signup.html")

# หน้า login
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = connect_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username,password)
        ).fetchone()
        if user:
            session["user"] = username
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Wrong username or password")
    return render_template("login.html")

# หน้า dashboard
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template("dashboard.html")

@app.route("/upload", methods=["GET","POST"])
def upload():
    if "user" not in session:
        return redirect("/login")
        
    if request.method == "POST":
        video = request.files["video"]
        # รับค่าประเภทวิดีโอจากฟอร์มในหน้า HTML
        model_type = request.form.get("model_type") 

        if video and allowed_file(video.filename):
            input_path = os.path.join(app.config["UPLOAD_FOLDER"], video.filename)
            video.save(input_path)
            
            # --- เลือกใช้ Model ตามที่ผู้ใช้เลือก ---
            if model_type == "pan":
                firefly_count = count_fireflies_pan(input_path)
            else:
                firefly_count = count_fireflies_still(input_path)
            
            # หมายเหตุ: ตอนนี้โมเดลของคุณคืนค่ามาแค่ตัวเลข (ไม่ได้คืนค่า output_path)
            # เราจึงส่งแค่ชื่อไฟล์วิดีโอต้นฉบับกลับไปแสดงผลชั่วคราวก่อน
            return render_template(
                "result.html",
                video=video.filename, 
                count=firefly_count,
                model_used=model_type # ส่งไปบอกหน้า result ด้วยว่าใช้โหมดไหนเผื่ออยากแสดงผล
            )
        else:
            return render_template("upload.html", error="Only video files allowed")
            
    return render_template("upload.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

# หน้า processed
@app.route('/processed/<filename>')
def processed_video(filename):
    return send_from_directory("processed", filename)

@app.route("/activity")
def activity():
    return render_template("activity.html")

@app.route("/learning")
def learning():
    return render_template("learning.html")

@app.route("/map")
def map():
    return render_template("map.html")

@app.route("/schedule")
def schedule():
    return render_template("schedule.html")

""" #จำกัดขนาด VDO
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024 """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)