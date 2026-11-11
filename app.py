import streamlit as st
import sqlite3
import time
from google import genai

st.set_page_config(page_title="Moksha", page_icon="🌿")
st.markdown("""<style>
h1 {color:#2e7d32;}
div.stButton > button {background:#2e7d32;color:white;border-radius:8px;}
</style>""", unsafe_allow_html=True)

MAX_QUESTIONS = 6  # how many questions the AI asks

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

Ask ONE short, simple follow-up question based on the patient's previous
answers (for example duration, location, severity, triggers, medicines
taken, other symptoms, past history). Never repeat a question. Do not
diagnose or give advice. Output only the question."""
    return ask_gemini(prompt) or "Can you tell me more about your symptoms?"

def make_summary(info, messages):
    prompt = f"""Patient: {info['name']}, age {info['age']}.
Main problem: {info['complaint']}.
Conversation:
{transcript(messages)}

Write a short case summary for the doctor (symptoms, duration, medicines,
relevant history). Do not give a diagnosis."""
    return ask_gemini(prompt) or "AI summary unavailable."

db = sqlite3.connect("cases.db")
db.execute("""CREATE TABLE IF NOT EXISTS cases
(id INTEGER PRIMARY KEY, name TEXT, age INT,
complaint TEXT, duration TEXT, details TEXT)""")
for col in ["summary", "transcript"]:
    try:
        db.execute(f"ALTER TABLE cases ADD COLUMN {col} TEXT")
    except sqlite3.OperationalError:
        pass

page = st.sidebar.radio("Portal", ["Patient", "Doctor"])

if page == "Patient":
    st.title("🌿 Moksha")
    st.caption("Patient case taking")

    if "info" not in st.session_state:
        name = st.text_input("Name")
        age = st.number_input("Age", 0, 120)
        complaint = st.text_input("What is your main problem?")
        if st.button("Start") and name and complaint:
            info = {"name": name, "age": age, "complaint": complaint}
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
            if st.button("New patient"):
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
                            "INSERT INTO cases(name,age,complaint,summary,transcript) VALUES(?,?,?,?,?)",
                            (info["name"], info["age"], info["complaint"],
                             summary, transcript(messages)))
                        db.commit()
                        st.session_state.done = True
                    else:
                        messages.append({"role": "assistant",
                                         "content": next_question(info, messages)})
                st.rerun()
else:
    st.title("🌿 Moksha: Doctor Portal")
    rows = db.execute(
        "SELECT name,age,complaint,summary,transcript FROM cases ORDER BY id DESC").fetchall()
    for n, a, c, s, t in rows:
        with st.expander(f"{n}, {a} yrs: {c}"):
            st.subheader("AI summary")
            st.write(s or "No AI summary")
            if t:
                st.subheader("Conversation")
                st.text(t)
