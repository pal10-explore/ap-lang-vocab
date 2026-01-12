# ================= QUIZ (BUTTON-BASED — RELIABLE) =================
with tabs[3]:
    st.subheader("Multiple-Choice Quiz")

    # Initialize quiz
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
        st.session_state.answers = {}
        st.session_state.submitted = False

    # Render quiz
    for i, q in enumerate(st.session_state.quiz):
        blank = re.sub(rf"\b{re.escape(q['word'])}\b", "_____", q["sentence"])
        st.markdown(f"**{i+1}. {blank}**")

        cols = st.columns(len(q["options"]))
        for col, opt in zip(cols, q["options"]):
            if col.button(opt, key=f"btn_{i}_{opt}"):
                st.session_state.answers[i] = opt

        if i in st.session_state.answers:
            st.write(f"Selected: **{st.session_state.answers[i]}**")

    # Submit
    if st.button("Submit Quiz"):
        st.session_state.submitted = True

    # Grade
    if st.session_state.submitted:
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
            st.session_state.pop("quiz", None)
            st.session_state.pop("answers", None)
            st.session_state.pop("submitted", None)
            st.rerun()
