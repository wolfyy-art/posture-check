# 🔥 Roast My Form

> **AI-powered exercise posture analyser** — snap a photo of your starting position and get instant, structured form feedback powered by Gemini Vision.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)
<!-- Replace the URL above after deploying to Streamlit Community Cloud -->

---

## What It Does

Upload or snap a photo of yourself performing a **Push-up**, **Squat**, or **Plank** setup position.  
Gemini Vision analyses your posture against a fixed biomechanics checklist and returns:

| Output | Where in the UI |
|--------|----------------|
| Overall score (0–100) + letter grade | `st.metric` KPI cards |
| Ranked flaw breakdown (area / issue / severity) | `st.data_editor` table |
| Actionable coaching tips | `st.expander` |
| Score trend across last 3 attempts | History cards with delta |

> ⚠️ **Scope notice:** This analyses a *single static frame* — not real-time rep tracking. It evaluates your starting/setup posture only. Not a substitute for professional physiotherapy advice.

---

## Architecture

```
User → st.form (exercise + photo)
     → utils.preprocess_image()
     → prompts.get_prompt(exercise)
     → gemini_client.analyse_form()   ←→   Gemini Vision API
     → Pydantic FormAnalysis model
     → st.session_state (history)
     → Results dashboard (metrics, table, expander)
```

See [`architecture.mmd`](./architecture.mmd) for the full Mermaid diagram  
(renders natively on GitHub — paste into [mermaid.live](https://mermaid.live) for a visual preview).

---

## Tech Stack

| Layer | Library / Tool |
|-------|---------------|
| UI framework | [Streamlit](https://streamlit.io) 1.37 |
| Vision AI | [google-generativeai](https://pypi.org/project/google-generativeai/) 0.7 · `gemini-2.0-flash` |
| Data validation | [Pydantic](https://docs.pydantic.dev) 2.8 |
| Tabular data | [Pandas](https://pandas.pydata.org) 2.2 |
| Image processing | [Pillow](https://pillow.readthedocs.io) 10.4 |
| Env management | [python-dotenv](https://pypi.org/project/python-dotenv/) 1.0 |
| Deployment | [Streamlit Community Cloud](https://streamlit.io/cloud) |

---

## Local Setup

### Prerequisites
- Python 3.11
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com)

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/your-username/roast-my-form.git
cd roast-my-form

# 2. Create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. Install dependencies (exact pinned versions)
pip install -r requirements.txt

# 4. Configure your API key
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
# Open .env and set GEMINI_API_KEY=<your key>

# 5. Run the app
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Deployment (Streamlit Community Cloud)

1. Push this repo to GitHub (ensure `.env` is in `.gitignore` — it already is).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → select your repo.
3. Set `GEMINI_API_KEY` under **Advanced settings → Secrets** (never commit the key).
4. Deploy. Test camera permissions in an incognito window before sharing the link.

---

## File Structure

```
roast-my-form/
├── app.py              # Streamlit entrypoint — UI layout, form, results dashboard
├── prompts.py          # Per-exercise system prompts + JSON schema enforcement
├── gemini_client.py    # Gemini SDK wrapper, retry logic, Pydantic validation
├── utils.py            # Image preprocessing, session_state helpers, badges
├── requirements.txt    # Pinned dependencies
├── architecture.mmd    # Mermaid architecture diagram source
├── .env.example        # API key template (real .env is gitignored)
└── README.md           # This file
```

---

## Prompt Engineering Strategy

Each exercise has a dedicated system prompt in `prompts.py` that:

1. **Assigns a persona** — "You are an expert strength-and-conditioning coach and biomechanics analyst."
2. **Defines a fixed checklist** — 7 biomechanics criteria per exercise (e.g. squat: knee tracking, hip depth, back angle…). This grounds the model and prevents hallucination of irrelevant feedback.
3. **Enforces strict JSON output** — Gemini is instructed to respond *only* with a JSON object matching a documented schema. No markdown fences, no preamble.
4. **Handles bad images explicitly** — if `image_quality` is not `"ok"`, the model is instructed to return score=0 and explain rather than guess.

This approach is more reliable than free-text parsing: the schema is validated by a Pydantic model (`FormAnalysis`) before any data reaches the UI, so a malformed response raises a typed exception rather than causing a silent rendering error.

---

## Data Flow (detailed)

```
1. User submits st.form
         │
2. utils.preprocess_image()
   • Convert to RGB (strip alpha)
   • Apply EXIF orientation
   • Resize longest edge to ≤ 1024 px
         │
3. prompts.get_prompt(exercise)
   • Returns the full system prompt string for the selected exercise
         │
4. gemini_client.analyse_form(image, prompt)
   • Calls gemini-2.0-flash with [prompt, PIL image]
   • temperature=0.2 for consistent JSON
   • On malformed JSON → strips markdown fences → retries once
   • Raises GeminiParseError / GeminiClientError on failure
         │
5. Pydantic FormAnalysis validation
   • overall_score: int 0-100
   • grade: A/B/C/D/F
   • flaws: list[{area, issue, severity}]
   • fix_tips: list[str]
   • image_quality: ok/blurry/no_person/partial_frame
   • summary: str
         │
6. st.session_state
   • Appends attempt record (timestamp, exercise, score, grade)
   • Trims history to last 3 entries
         │
7. UI renders
   • KPI row: st.metric (score + delta vs previous attempt)
   • Flaw table: st.data_editor (sorted by severity, read-only)
   • Tips: st.expander
   • History: inline HTML cards
```

---

## License

MIT — see [LICENSE](./LICENSE) if present, otherwise consider it open for educational use.

---

*Built as part of MirAI School of Technology — August 2026.*
