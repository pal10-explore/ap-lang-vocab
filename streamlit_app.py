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

tabs = st.tabs(["➕ Add Words", "📝 Review / Edit", "🧠 Flashcards", "📝 Quiz"])

# ================= ADD WORDS =================
with tabs[0]:
    st.subheader("Add Weekly Vocabulary")

    words_input = st.text_area("Paste words (one per line):", height=200)

    if st.button("Fetch & Save"):
        for word in [w.strip().lower() for w in words_input.splitlines() if w.strip()]:
            c.execute("INSERT OR IGNORE INTO words (word) VALUES (?)", (word,))
            c.execute("SELECT id FROM words WHERE word=?", (word,))
            wid = c.fetchone()[0]

            c.execute(
                "INSERT OR IGNORE INTO definitions VALUES (?, ?)",
                (wid, fetch_definition(word))
            )

            c.execute(
                "SELECT COUNT(*) FROM sentences WHERE word_id=?",
                (wid,)
            )
            if c.fetchone()[0] == 0:
                c.execute(
                    "INSERT INTO sentences (word_id, sentence, is_primary) VALUES (?, ?, 1)",
                    (wid, generate_primary_sentence(word))
                )

        conn.commit()
        st.success("Words added successfully.")

    if st.button("🧹 Clear All Words (New Week)"):
        c.execute("DELETE FROM sentences")
        c.execute("DELETE FROM definitions")
        c.execute("DELETE FROM words")
        conn.commit()
        st.session_state.clear()
        st.success("All words cleared. Ready for a new week.")

# ================= REVIEW / EDIT =================
with tabs[1]:
    st.subheader("Review and Edit Words")

    c.execute("SELECT word FROM words ORDER BY word")
    words = [r[0] for r in c.fetchall()]

    if not words:
        st.info("No words added yet.")
    else:
        word = st.selectbox("Select a word:", words)

        c.execute("SELECT id FROM words WHERE word=?", (word,))
        wid = c.fetchone()[0]

        # Definition
        c.execute("SELECT definition FROM definitions WHERE word_id=?", (wid,))
        definition = c.fetchone()[0]
        new_def = st.text_area("Definition:", definition, height=100)

        if st.button("Save Definition"):
            c.execute(
                "UPDATE definitions SET definition=? WHERE word_id=?",
                (new_def.strip(), wid)
            )
            conn.commit()
            st.success("Definition saved.")

        # Sentences
        c.execute("""
            SELECT id, sentence, is_primary
            FROM sentences
            WHERE word_id=?
            ORDER BY is_primary DESC, id
        """, (wid,))
        rows = c.fetchall()

        st.markdown("### Sentences")

        if rows:
            sentence_map = {
                f"{'⭐ ' if r[2] else ''}{r[1]}": r[0]
                for r in rows
            }

            selected = st.radio(
                "Select a sentence:",
                list(sentence_map.keys()),
                index=0
            )
            sid = sentence_map[selected]

            col1, col2 = st.columns(2)

            if col1.button("Set as Primary"):
                c.execute("UPDATE sentences SET is_primary=0 WHERE word_id=?", (wid,))
                c.execute("UPDATE sentences SET is_primary=1 WHERE id=?", (sid,))
                conn.commit()
                st.rerun()

            if col2.button("Delete Sentence"):
                c.execute("DELETE FROM sentences WHERE id=?", (sid,))
                conn.commit()
                st.rerun()
        else:
            st.info("No sentences exist for this word. Add one below.")

        new_sentence = st.text_input("Add a new sentence:")
        if st.button("Add Sentence") and new_sentence:
            c.execute(
                "SELECT COUNT(*) FROM sentences WHERE word_id=?",
                (wid,)
            )
            count = c.fetchone()[0]
            is_primary = 1 if count == 0 else 0

            c.execute(
                "INSERT INTO sentences (word_id, sentence, is_primary) VALUES (?, ?, ?)",
                (wid, new_sentence, is_primary)
            )
            conn.commit()
            st.success("Sentence added.")
            st.rerun()

# ================= FLASHCARDS =================
with tabs[2]:
    st.subheader("Flashcards")

    if st.button("Next Card"):
        st.session_state.pop("flash", None)

    if "flash" not in st.session_state:
        c.execute("""
            SELECT words.word, definitions.definition, sentences.sentence
            FROM words
            JOIN definitions ON words.id = definitions.word_id
            JOIN sentences ON words.id = sentences.word_id
            WHERE sentences.is_primary = 1
            ORDER BY RANDOM()
            LIMIT 1
        """)
        st.session_state.flash = c.fetchone()

    if st.session_state.flash:
        word, definition, sentence = st.session_state.flash
        st.markdown(f"## **{word}**")
        if st.button("Reveal"):
            st.write(definition)
            st.write(sentence)
    else:
        st.info("No words available.")

# ================= QUIZ =================
with tabs[3]:
    st.subheader("Multiple-Choice Quiz")

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
            options = random.sample(options, min(3, len(options)))
            options.append(w)
            random.shuffle(options)
            quiz.append({"word": w, "sentence": s, "options": options})

        st.session_state.quiz = quiz
        st.session_state.answers = {}

    for i, q in enumerate(st.session_state.quiz):
        blank = re.sub(rf"\b{re.escape(q['word'])}\b", "_____", q["sentence"])
        st.markdown(f"**{i+1}. {blank}**")
        st.session_state.answers[i] = st.radio(
            "Choose:",
            q["options"],
            key=f"q{i}",
            index=None
        )

    if st.button("Submit Quiz"):
        score = 0
        st.markdown("---")
        for i, q in enumerate(st.session_state.quiz):
            user = st.session_state.answers.get(i)
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
            # Clear quiz data
            st.session_state.pop("quiz", None)
            st.session_state.pop("answers", None)

            # Clear radio button widget state
            for key in list(st.session_State.keys()):
                if key.startswith("q"):
                    del st.session_State[key]
                    
            st.rerun()

