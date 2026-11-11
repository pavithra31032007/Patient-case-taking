import streamlit as st
import sqlite3
from google import genai

def summarize_case(name, age, complaint, duration, details):
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        prompt = f"""Patient: {name}, age {age}.
Complaint: {complaint} for {duration}. Details: {details}.
Write a short case summary for the doctor and suggest 3 follow-up
questions to ask. Do not give a diagnosis."""
        r = client.models.generate_content(
            model="gemini-3.5-flash", contents=prompt)
        return r.text
    except Exception as e:
        return f"AI summary unavailable: {e}"

db = sqlite3.connect("cases.db")
db.execute("""CREATE TABLE IF NOT EXISTS cases
(id INTEGER PRIMARY KEY, name TEXT, age INT,
complaint TEXT, duration TEXT, details TEXT)""")

page = st.sidebar.radio("Portal", ["Patient", "Doctor"])

if page == "Patient":
    st.title("Patient Case Taking")
    name = st.text_input("Name")
    age = st.number_input("Age", 0, 120)
    complaint = st.selectbox("Main complaint",
        ["Fever", "Headache", "Digestion", "Other"])
    duration = st.text_input("Since how long?")
    details = ""
    if complaint == "Fever":
        details = st.radio("Fever type", ["Continuous", "Intermittent"])
    elif complaint == "Headache":
        details = st.radio("Where is the pain?", ["Front", "One side", "Back"])
    elif complaint == "Digestion":
        details = st.radio("Problem", ["Acidity", "Constipation", "Loose motion"])
    if st.button("Submit"):
        db.execute("INSERT INTO cases(name,age,complaint,duration,details) VALUES(?,?,?,?,?)",
                   (name, age, complaint, duration, details))
        db.commit()
        st.success("Saved!")
        st.write(summarize_case(name, age, complaint, duration, details))
else:
    st.title("Doctor Portal")
    st.table(db.execute("SELECT * FROM cases").fetchall())
