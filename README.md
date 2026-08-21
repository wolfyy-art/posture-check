```
██████╗  ██████╗  █████╗ ███████╗████████╗    ███╗   ███╗██╗   ██╗    ███████╗ ██████╗ ██████╗ ███╗   ███╗
██╔══██╗██╔═══██╗██╔══██╗██╔════╝╚══██╔══╝    ████╗ ████║╚██╗ ██╔╝    ██╔════╝██╔═══██╗██╔══██╗████╗ ████║
██████╔╝██║   ██║███████║███████╗   ██║       ██╔████╔██║ ╚████╔╝     █████╗  ██║   ██║██████╔╝██╔████╔██║
██╔══██╗██║   ██║██╔══██║╚════██║   ██║       ██║╚██╔╝██║  ╚██╔╝      ██╔══╝  ██║   ██║██╔══██╗██║╚██╔╝██║
██║  ██║╚██████╔╝██║  ██║███████║   ██║       ██║ ╚═╝ ██║   ██║       ██║     ╚██████╔╝██║  ██║██║ ╚═╝ ██║
╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝   ╚═╝       ╚═╝     ╚═╝   ╚═╝       ╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝
```

> `$ ./analyze --exercise=squat --input=camera`
> AI-powered exercise posture analyzer built on Gemini Vision.

**🔴 LIVE:** [roast-posture.onrender.com](https://roast-posture.onrender.com/)

---

## `$ cat about.txt`

Roast My Form is a Streamlit web app that captures a single photo of your
exercise starting posture (pushup, squat, or plank) and sends it to Gemini's
Vision model for a structured biomechanics critique — not a generic chatbot
reply, but a scored, checklist-driven analysis.

The AI is constrained to return **strict JSON** (score, flaw list, fix tips,
image-quality flag), which gets validated through a Pydantic schema before
ever touching the UI. If Gemini's response doesn't match the schema, the app
retries once and fails gracefully instead of crashing.

> ⚠️ **Note:** `st.camera_input` captures a single static frame, not video.
> This app analyzes starting posture/setup — it does not track reps or
> movement in real time.

---

## `$ ls features/`

```
✔ Gemini Vision multimodal input (camera capture)
✔ Per-exercise system prompts (pushup / squat / plank)
✔ Strict JSON-schema output, validated via Pydantic
✔ Retry-on-malformed-response logic (max 2 attempts)
✔ st.session_state history — tracks your last 3 attempts
✔ st.metric KPI cards with score deltas across attempts
✔ st.data_editor flaw breakdown table
✔ st.expander for detailed coaching notes
✔ Graceful error handling — no raw stack traces surfaced to the user
```

---

## `$ cat architecture.txt`

```
┌─────────────┐     ┌───────────────┐     ┌─────────────────────┐
│   User      │────▶│  Streamlit UI │────▶│  gemini_client.py    │
│ (camera in) │     │   (app.py)    │     │  - builds prompt      │
└─────────────┘     └───────────────┘     │  - calls Gemini Vision│
                            ▲              │  - parses + validates │
                            │              │    JSON via Pydantic  │
                            │              └──────────┬────────────┘
                            │                         │
                            │                         ▼
                     ┌──────┴────────┐      ┌─────────────────────┐
                     │ st.session_    │◀─────│  FormAnalysis model  │
                     │ state history  │      │  (score, flaws,      │
                     └───────────────┘       │   fix_tips, etc.)    │
                                              └─────────────────────┘
```

Full Mermaid version: [`architecture.mmd`](./architecture.mmd)

---

## `$ ./setup.sh`

```bash
# 1. Clone the repo
git clone https://github.com/wolfyy-art/posture-check.git
cd posture-check

# 2. Create venv and activate (Python 3.11 required — see note below)
py -3.11 -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your API key
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env

# Open .env and set:
# GEMINI_API_KEY=your_key_here
# Get a free key at: https://aistudio.google.com/apikey

# 5. Run
streamlit run app.py
```

> **Why Python 3.11 specifically?** `pandas` doesn't ship a prebuilt wheel
> for 3.14 yet, and compiling it from source needs build tools most
> machines don't have. 3.11 avoids that entirely.

---

## `$ cat stack.txt`

```
Frontend/UI     : Streamlit
AI Engine       : Gemini Vision (gemini-3.6-flash)
Validation      : Pydantic
Data handling   : Pandas
Deployment      : Render (Web Service, free tier)
Version Control : Git + GitHub
```

---

## `$ cat known_limitations.txt`

```
- Single-frame analysis only — no real-time rep tracking
- Free-tier Render instance sleeps after inactivity (~30-50s cold start)
- Gemini's output quality depends on photo lighting/framing/angle
```

---

## `$ whoami`

Built by [Mayank Saroha](https://github.com/wolfyy-art) as a capstone
project for **MirAI School of Technology**.

[LinkedIn](https://linkedin.com/in/mayank-saroha-235953295) · [GitHub](https://github.com/wolfyy-art)
