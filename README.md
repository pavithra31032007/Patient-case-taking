# Patient-case-taking
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
        st.success("Saved!")
        st.write(summarize_case(name, age, complaint, duration, details))
