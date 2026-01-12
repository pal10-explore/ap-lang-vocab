import streamlit as st
import sqlite3
import requests
import random
import re
import os

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

    c.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY,
            word TEXT UNIQUE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS definitions (
            word_id INTEGER UNIQUE,
            definition TEXT
        )
    """)
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
        f"In the passage, the author defends a {word} claim through logical reasoning and supporting evidence.",
        f"The argument remains {word} because the writer carefully qualifies opposing perspectives.",
        f"The speaker’s position is {word}, grounded in a clear analysis of the issue.",
        f"The essay presents a {word} interpretation supported by concrete examples.",
        f"The author advances a {word} assertion that strengthens the central argument."
    ]
    return random.choice(templates)

# ================= UI =================
st.set_page_config(page_title="AP Lang Vocabulary Tutor", layout="wide")
st.title("📘 AP Language Vocabulary Tutor")

init_db()
conn = get_conn()
c = conn.cursor()

tabs = st.tabs([
    "➕ Add Words",
    "📝 Review / Edit",
    "🧠 Flashcards",
    "📝 Multiple-Choice Quiz"
])

# ---------- ADD WORDS ----------
with tabs[0]:
    st.subheader("Add Weekly Vocabulary")

    words_input = st.text_area("Paste words (one per line):", height=200)

    col1, col2 = st.columns(2)

    if col1.button("Fetch & Save"):
        words = [w.strip().lower() for w in words_input.splitlines() if w.strip()]
        for word in words:
            c.execute("INSERT OR IGNORE INTO words (word) VALUES (?)", (word,))
            c.execute("SELECT id FROM words WHERE word=?", (word,))
            word_id = c.fetchone()[0]

            c.execute("SELECT 1 FROM definitions WHERE word_id=?", (word_id,))
            if not c.fetchone():
                c.execute("INSERT INTO definitions VALUES (?, ?)",
                          (word_id, fetch_definition(word)))

            c.execute("SELECT 1 FROM sentences WHERE word_id=? AND is_primary=1", (word_id,))
            if not c.fetchone():
                c.execute(
                    "INSERT INTO sentences (word_id, sentence, is_primary) VALUES (?, ?, 1)",
                    (word_id, generate_primary_sentence(word))
                )

        conn.commit()
        st.success("Words added successfully.")

    if col2.button("🧹 Clear All Words (New Week)"):
        if st.confirm("This will delete ALL words. Continue?"):
            c.execute("DELETE FROM sentences")
            c.execute("DELETE FROM definitions")
            c.execute("DELETE FROM words")
            conn.commit()
            st.success("All words cleared. Ready for a new week.")

# ---------- REVIEW / EDIT ----------
with tabs[1]:
    st.subheader("Review and Edit Words")

    c.execute("SELECT word FROM words ORDER BY word")
    words = [r[0] for r in c.fetchall()]

    if words:
        selected = st.selectbox("Select a word:", words)

        c.execute("SELECT id FROM words WHERE word=?", (selected,))
        word_id = c.fetchone()[0]

        c.execute("SELECT definition FROM definitions WHERE word_id=?", (word_id,))
        definition = c.fetchone()[0]

        new_def = st.text_area("Definition:", value=definition, height=100)
        if st.button("Save Definition"):
            c.execute("UPDATE definitions SET definition=? WHERE word_id=?",
                      (new_def.strip(), word_id))
            conn.commit()
            st.success("Definition saved.")

        c.execute("""
            SELECT sentence, is_primary FROM sentences
            WHERE word_id=?
            ORDER BY is_primary DESC, id ASC
        """, (word_id,))
        sentences = c.fetchall()

        st.markdown("**Sentences (primary shown first):**")
        for s, primary in sentences:
            st.write(("⭐ " if primary else "• ") + s)

        new_sentence = st.text_input("Add a new sentence:")
        if st.button("Add Sentence") and new_sentence:
            c.execute(
                "INSERT INTO sentences (word_id, sentence, is_primary) VALUES (?, ?, 0)",
                (word_id, new_sentence)
            )
            conn.commit()
            st.success("Sentence added.")

# ---------- FLASHCARDS ----------
with tabs[2]:
    st.subheader("Flashcards")

    c.execute("""
        SELECT words.word, definitions.definition, sentences.sentence
        FROM words
        JOIN definitions ON words.id=definitions.word_id
        JOIN sentences ON words.id=sentences.word_id
        WHERE sentences.is_primary=1
        ORDER BY RANDOM() LIMIT 1
    """)
    row = c.fetchone()

    if row:
        if st.button("Next Card"):
            st.experimental_rerun()

        st.markdown(f"## **{row[0]}**")
        if st.button("Reveal"):
            st.write(row[1])
            st.write(row[2])
    else:
        st.info("No words added yet.")

# ---------- MULTIPLE CHOICE ----------
with tabs[3]:
    st.subheader("Multiple-Choice Quiz")

    c.execute("""
        SELECT words.word, sentences.sentence
        FROM words JOIN sentences ON words.id=sentences.word_id
        WHERE sentences.is_primary=1
        ORDER BY RANDOM() LIMIT ?
    """, (QUIZ_SIZE,))
    quiz_items = c.fetchall()

    answers = {}
    score = 0

    for i, (correct, sentence) in enumerate(quiz_items):
        blank = re.sub(rf"\b{re.escape(correct)}\b", "_____", sentence)
        st.write(f"**{i+1}. {blank}**")

        options = random.sample(
            [w for w, _ in quiz_items if w != correct],
            min(3, len(quiz_items)-1)
        ) + [correct]
        random.shuffle(options)

        answers[i] = st.radio(
            "Choose:",
            options,
            key=f"q{i}",
            index=None
        )

    if st.button("Submit Quiz"):
        for i, (correct, sentence) in enumerate(quiz_items):
            if answers[i] == correct:
                score += 1

            restored = re.sub(rf"\b{re.escape(correct)}\b", correct, sentence)
            st.write(f"**Q{i+1}** — Your answer: {answers[i] or '[none]'}")
            st.write(f"Correct answer: **{correct}**")
            st.write(f"Sentence: {restored}")
            st.write("---")

        st.success(f"Final Score: {score}/{len(quiz_items)}")
