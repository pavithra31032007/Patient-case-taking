import streamlit as st
import sqlite3
import time
import hashlib
import hmac
import os
from datetime import datetime
from google import genai

st.set_page_config(page_title="Moksha", page_icon="🌿")
st.markdown("""<style>
h1 {color:#2e7d32;}
div.stButton > button {background:#2e7d32;color:white;border-radius:8px;}
</style>""", unsafe_allow_html=True)

MAX_QUESTIONS = 6

def ask_gemini(prompt):
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    for model in ["gemini-3.5-flash", "gemini-2.5-flash"]:
        for attempt in range(2):
            try:
                r = client.models.generate_content(model=model, contents=prompt)
                return r.text.strip()
            except Exception:
                time.sleep(2)
    return None

def transcript(messages):
    return "\n".join(
        f"{'Moksha' if m['role'] == 'assistant' else 'Patient'}: {m['content']}"
        for m in messages)

def next_question(info, messages):
    prompt = f"""You are Moksha, a polite patient case-taking assistant.
Patient: {info['name']}, age {info['age']}. Main problem: {info['complaint']}.
Conversation so far:
{transcript(messages) or '(none yet)'}

Ask exactly ONE short, simple question about a single thing. Use the
patient's previous answers and never ask about something already answered
(for example duration, location, severity, triggers, medicines taken,
other symptoms, past history). Do not diagnose or give advice.
Output only the question."""
    return ask_gemini(prompt) or "Can you tell me more about your symptoms?"

def make_summary(info, messages):
    prompt = f"""Patient: {info['name']}, age {info['age']}.
Main problem: {info['complaint']}.
Conversation:
{transcript(messages)}

Write a short case summary for the doctor (symptoms, duration, medicines,
relevant history). Do not give a diagnosis."""
    return ask_gemini(prompt) or "AI summary unavailable."

def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)

# ---------- database ----------
db = sqlite3.connect("cases.db", check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS cases
(id INTEGER PRIMARY KEY, name TEXT, age INT,
complaint TEXT, duration TEXT, details TEXT)""")
for col in ["summary", "transcript", "username"]:
    try:
        db.execute(f"ALTER TABLE cases ADD COLUMN {col} TEXT")
    except sqlite3.OperationalError:
        pass
db.execute("""CREATE TABLE IF NOT EXISTS users
(username TEXT PRIMARY KEY, full_name TEXT, role TEXT, salt BLOB, pw BLOB)""")
db.execute("""CREATE TABLE IF NOT EXISTS documents
(id INTEGER PRIMARY KEY, username TEXT, filename TEXT, data BLOB, uploaded TEXT)""")
db.commit()

# ---------- login / register ----------
if "user" not in st.session_state:
    st.title("🌿 Moksha")
    st.caption("Please log in to continue")
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        u = st.text_input("Username", key="lu")
        p = st.text_input("Password", type="password", key="lp")
        if st.button("Login"):
            row = db.execute(
                "SELECT full_name, role, salt, pw FROM users WHERE username=?",
                (u.strip().lower(),)).fetchone()
            if row and hmac.compare_digest(hash_pw(p, row[2]), row[3]):
                st.session_state.user = {
                    "username": u.strip().lower(), "name": row[0], "role": row[1]}
                st.rerun()
            else:
                st.error("Wrong username or password")
    with tab2:
        role = st.radio("I am a", ["Patient", "Doctor"], horizontal=True)
        full = st.text_input("Full name")
        ru = st.text_input("Choose a username (this is your login ID)", key="ru")
        rp = st.text_input("Choose a password (min 8 characters)",
                           type="password", key="rp")
        code = st.text_input("Doctor access code", type="password") if role == "Doctor" else ""
        if st.button("Register"):
            ru = ru.strip().lower()
            if not (full.strip() and ru and len(rp) >= 8):
                st.error("Fill all fields. Password needs at least 8 characters.")
            elif role == "Doctor" and code != st.secrets.get("DOCTOR_CODE", None):
                st.error("Wrong doctor access code.")
            else:
                salt = os.urandom(16)
                try:
                    db.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                               (ru, full.strip(), role, salt, hash_pw(rp, salt)))
                    db.commit()
                    st.success("Registered! Now go to the Login tab.")
                except sqlite3.IntegrityError:
                    st.error("That username is taken. Try another.")
    st.stop()

user = st.session_state.user
st.sidebar.write(f"👤 {user['name']} ({user['role']})")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# ---------- patient side ----------
if user["role"] == "Patient":
    page = st.sidebar.radio("Menu", ["New case", "My records", "My documents"])

    if page == "New case":
        st.title("🌿 Moksha")
        st.caption(f"Patient ID: {user['username']}")
        if "info" not in st.session_state:
            age = st.number_input("Age", 0, 120)
            complaint = st.text_input("What is your main problem?")
            if st.button("Start") and complaint:
                info = {"name": user["name"], "age": age, "complaint": complaint}
                with st.spinner("Preparing your first question..."):
                    q = next_question(info, [])
                st.session_state.info = info
                st.session_state.messages = [{"role": "assistant", "content": q}]
                st.rerun()
        else:
            info = st.session_state.info
            messages = st.session_state.messages
            for m in messages:
                with st.chat_message(m["role"]):
                    st.write(m["content"])
            if st.session_state.get("done"):
                st.success("Thank you! Your case has been sent to the doctor.")
                if st.button("New case"):
                    for k in ["info", "messages", "done"]:
                        st.session_state.pop(k, None)
                    st.rerun()
            else:
                answer = st.chat_input("Type your answer")
                if answer:
                    messages.append({"role": "user", "content": answer})
                    answered = sum(1 for m in messages if m["role"] == "user")
                    with st.spinner("Thinking..."):
                        if answered >= MAX_QUESTIONS:
                            summary = make_summary(info, messages)
                            db.execute(
                                "INSERT INTO cases(name,age,complaint,summary,transcript,username) VALUES(?,?,?,?,?,?)",
                                (info["name"], info["age"], info["complaint"],
                                 summary, transcript(messages), user["username"]))
                            db.commit()
                            st.session_state.done = True
                        else:
                            messages.append({"role": "assistant",
                                             "content": next_question(info, messages)})
                    st.rerun()

    elif page == "My records":
        st.title("🌿 My records")
        rows = db.execute(
            "SELECT complaint, summary, transcript FROM cases WHERE username=? ORDER BY id DESC",
            (user["username"],)).fetchall()
        if not rows:
            st.info("No previous cases yet.")
        for c, s, t in rows:
            with st.expander(c):
                st.write(s)
                st.text(t or "")

    else:
        st.title("🌿 My documents")
        up_key = f"up{st.session_state.get('upn', 0)}"
        f = st.file_uploader("Upload report, prescription or scan (PDF/JPG/PNG, max 5 MB)",
                             type=["pdf", "png", "jpg", "jpeg"], key=up_key)
        if f and st.button("Save document"):
            data = f.getvalue()
            if len(data) > 5 * 1024 * 1024:
                st.error("File is too large (max 5 MB).")
            else:
                db.execute(
                    "INSERT INTO documents(username,filename,data,uploaded) VALUES(?,?,?,?)",
                    (user["username"], f.name, data,
                     datetime.now().strftime("%d %b %Y %H:%M")))
                db.commit()
                st.session_state.upn = st.session_state.get("upn", 0) + 1
                st.rerun()
        docs = db.execute(
            "SELECT id, filename, data, uploaded FROM documents WHERE username=? ORDER BY id DESC",
            (user["username"],)).fetchall()
        for i, fn, data, ts in docs:
            st.download_button(f"📄 {fn} ({ts})", data, file_name=fn, key=f"d{i}")

# ---------- doctor side ----------
else:
    page = st.sidebar.radio("Menu", ["Patient cases", "Patient documents"])
    if page == "Patient cases":
        st.title("🌿 Moksha: Doctor Portal")
        rows = db.execute(
            "SELECT name,age,complaint,summary,transcript,username FROM cases ORDER BY id DESC").fetchall()
        for n, a, c, s, t, un in rows:
            with st.expander(f"{n}, {a} yrs: {c}"):
                st.caption(f"Patient ID: {un or 'old record'}")
                st.subheader("AI summary")
                st.caption("AI-generated summary. The doctor must verify all details.")
                st.write(s or "No AI summary")
                if t:
                    st.subheader("Conversation")
                    st.text(t)
    else:
        st.title("🌿 Patient documents")
        pats = db.execute(
            "SELECT username, full_name FROM users WHERE role='Patient'").fetchall()
        if not pats:
            st.info("No registered patients yet.")
        else:
            pick = st.selectbox("Patient", pats, format_func=lambda x: f"{x[1]} ({x[0]})")
            docs = db.execute(
                "SELECT id, filename, data, uploaded FROM documents WHERE username=? ORDER BY id DESC",
                (pick[0],)).fetchall()
            if not docs:
                st.info("No documents uploaded.")
            for i, fn, data, ts in docs:
                st.download_button(f"📄 {fn} ({ts})", data, file_name=fn, key=f"dd{i}")
