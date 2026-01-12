import streamlit as st
import sqlite3
import requests
import random
import re

# ================= CONFIG =================
WORDNIK_API_KEY = "8mua68owf2ae0sarae049njpelzl39ydn456om6pxqnci2pjj"
DB_NAME = "vocab.db"
QUIZ_SIZE = 5

# ================= DATABASE =================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS words (id INTEGER PRIMARY KEY, word TEXT UNIQUE)")
    c.execute("CREATE TABLE IF NOT EXISTS definitions (word_id INTEGER UNIQUE, definition TEXT)")
    c.execute("""
        CREATE TABLE IF NOT EXISTS sentences (
            id INTEGER PRIMARY KEY,
            word_id INTEGER,
            sentence TEXT,
            is_primary INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# ================= DATA =================
def fetch_definition(word):
    try:
        r = requests.get(
            f"https://api.wordnik.com/v4/word.json/{word}/definitions",
            params={"limit": 1, "api_key": WORDNIK_API_KEY},
            timeout=10
        ).json()
        if isinstance(r, list) and r:
            return r[0].get("text", "Definition unavailable.")
    except:
        pass
    return "Definition unavailable."

def generate_primary_sentence(word):
    templates = [
        f"The author presents a {word} argument supported by logical reasoning.",
        f"The essay advances a {word} claim grounded in evidence.",
        f"The speaker defends a {word} position throughout the passage.",
        f"The argument remains {word} due to careful qualification of ideas.",
        f"The writer offers a {word} interpretation of the issue."
    ]
    return random.choice(templates)

# ================= INIT =================
st.set_page_config(page_title="AP Lang Vocabulary Tutor", layout="wide")
st.title("📘 AP Language Vocabulary Tutor")

init_db()
conn = get_conn()
c = conn.cursor()

# CRITICAL: quiz container version
if "quiz_container_id" not in st.session_state:
    st.session_state.quiz_container_id = 0

tabs = st.tabs(["➕ Add Words", "📝 Review / Edit", "🧠 Flashcards", "📝 Quiz"])

# ================= ADD WORDS =================
with tabs[0]:
    words_input = st.text_area("Paste words (one per line):", height=200)

    if st.button("Fetch & Save"):
        for word in [w.strip().lower() for w in words_input.splitlines() if w.strip()]:
            c.execute("INSERT OR IGNORE INTO words (word) VALUES (?)", (word,))
            c.execute("SELECT id FROM words WHERE word=?", (word,))
            wid = c.fetchone()[0]

            c.execute("INSERT OR IGNORE INTO definitions VALUES (?, ?)",
                      (wid, fetch_definition(word)))

            c.execute("SELECT COUNT(*) FROM sentences WHERE word_id=?", (wid,))
            if c.fetchone()[0] == 0:
                c.execute(
                    "INSERT INTO sentences (word_id, sentence, is_primary) VALUES (?, ?, 1)",
                    (wid, generate_primary_sentence(word))
                )
        conn.commit()
        st.success("Words added.")

# ================= QUIZ =================
with tabs[3]:
    st.subheader("Multiple-Choice Quiz")

    quiz_key = f"quiz_container_{st.session_state.quiz_container_id}"

    with st.container(key=quiz_key):

        if "quiz" not in st.session_state:
            c.execute("""
                SELECT words.word, sentences.sentence
                FROM words
                JOIN sentences ON words.id = sentences.word_id
                WHERE sentences.is_primary = 1
                ORDER BY RANDOM()
                LIMIT ?
            """, (QUIZ_SIZE,))
            items = c.fetchall()

            quiz = []
            for w, s in items:
                options = [x[0] for x in items if x[0] != w]
                options = random.sample(options, min(3, len(options))) + [w]
                random.shuffle(options)
                quiz.append({"word": w, "sentence": s, "options": options})

            st.session_state.quiz = quiz

        answers = {}

        with st.form("quiz_form"):
            for i, q in enumerate(st.session_state.quiz):
                blank = re.sub(rf"\b{re.escape(q['word'])}\b", "_____", q["sentence"])
                st.markdown(f"**{i+1}. {blank}**")
                answers[i] = st.radio(
                    "Choose:",
                    q["options"],
                    index=None,
                    key=f"q_{quiz_key}_{i}"
                )

            submitted = st.form_submit_button("Submit Quiz")

        if submitted:
            score = 0
            st.markdown("---")
            for i, q in enumerate(st.session_state.quiz):
                user = answers.get(i)
                correct = q["word"]
                if user == correct:
                    score += 1
                restored = re.sub(rf"\b{re.escape(correct)}\b", correct, q["sentence"])
                st.write(f"Your answer: {user or '[none]'}")
                st.write(f"Correct answer: **{correct}**")
                st.write(restored)
                st.write("---")

            st.success(f"Score: {score}/{len(st.session_state.quiz)}")

            if st.button("Start New Quiz"):
                st.session_state.quiz_container_id += 1
                st.session_state.pop("quiz", None)
                st.rerun()
