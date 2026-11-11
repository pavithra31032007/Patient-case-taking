import streamlit as st
import sqlite3
import time
from google import genai

st.set_page_config(page_title="Moksha", page_icon="🌿")
st.markdown("""<style>
h1 {color:#2e7d32;}
div.stButton > button {background:#2e7d32;color:white;border-radius:8px;}
</style>""", unsafe_allow_html=True)

def summarize_case(name, age, complaint, duration, details):
    prompt = f"""Patient: {name}, age {age}.
Complaint: {complaint} for {duration}. Details: {details}.
Write a short case summary for the doctor and suggest 3 follow-up
questions to ask. Do not give a diagnosis."""
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    last = ""
    for model in ["gemini-3.5-flash", "gemini-2.5-flash"]:
        for attempt in range(2):
            try:
                r = client.models.generate_content(
                    model=model, contents=prompt)
                return r.text
            except Exception as e:
                last = e
                time.sleep(2)
    return f"AI summary unavailable right now. ({last})"

db = sqlite3.connect("cases.db")
db.execute("""CREATE TABLE IF NOT EXISTS cases
(id INTEGER PRIMARY KEY, name TEXT, age INT,
complaint TEXT, duration TEXT, details TEXT)""")
try:
    db.execute("ALTER TABLE cases ADD COLUMN summary TEXT")
except sqlite3.OperationalError:
    pass

page = st.sidebar.radio("Portal", ["Patient", "Doctor"])

if page == "Patient":
    st.title("🌿 Moksha")
    st.caption("Patient case taking")
    name = st.text_input("Name")
    age = st.number_input("Age", 0, 120)
    complaint = st.selectbox("Main complaint",
        ["Fever", "Headache", "Digestion", "Cough", "Other"])
    duration = st.text_input("Since how long?")
    details = ""
    if complaint == "Fever":
        details = st.radio("Fever type", ["Continuous", "Intermittent"])
    elif complaint == "Headache":
        details = st.radio("Where is the pain?", ["Front", "One side", "Back"])
    elif complaint == "Digestion":
        details = st.radio("Problem", ["Acidity", "Constipation", "Loose motion"])
    elif complaint == "Cough":
        details = st.radio("Type of cough", ["Dry", "With phlegm", "Mostly at night"])
    if st.button("Submit"):
        summary = summarize_case(name, age, complaint, duration, details)
        db.execute("INSERT INTO cases(name,age,complaint,duration,details,summary) VALUES(?,?,?,?,?,?)",
                   (name, age, complaint, duration, details, summary))
        db.commit()
        st.success("Saved!")
        st.write(summary)
else:
    st.title("🌿 Moksha: Doctor Portal")
    rows = db.execute("SELECT name,age,complaint,duration,details,summary FROM cases ORDER BY id DESC").fetchall()
    for n, a, c, d, det, s in rows:
        with st.expander(f"{n}, {a} yrs: {c}"):
            st.write(f"Since: {d} | Detail: {det}")
            st.write(s or "No AI summary")
