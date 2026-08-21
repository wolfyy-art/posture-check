# Technical Design Document — Roast My Form

## 1. Problem Statement
Users want quick, objective feedback on exercise starting posture (pushup,
squat, plank) without a coach present. A single photo, analyzed against a
fixed biomechanics checklist, can surface common form flaws immediately.

## 2. Data Flow
1. User selects an exercise from a dropdown and captures a photo via
   `st.camera_input`, both wrapped in a single `st.form` so the app doesn't
   re-run on every widget interaction — only on final submission.
2. `prompts.py` builds a per-exercise system prompt using an f-string,
   injecting the exercise name and its specific checklist (e.g., for squats:
   knee-over-toe alignment, back angle, foot width, hip depth).
3. `gemini_client.py` sends the image + prompt to Gemini Vision
   (`gemini-3.6-flash`) with a generation config that:
   - Forces `response_mime_type="application/json"`
   - Lowers the model's internal "thinking" budget (`thinking_level="low"`)
     so more of the token budget goes to the actual output rather than
     internal reasoning
   - Caps output at 2048 tokens to avoid truncation mid-response
4. The raw response is cleaned (markdown fences stripped, outermost `{...}`
   isolated) and parsed into a `FormAnalysis` Pydantic model, which enforces:
   - `overall_score` between 0–100
   - `grade` restricted to A–F
   - `severity` per flaw restricted to low/medium/high
   - `image_quality` restricted to ok/blurry/no_person/partial_frame
5. On a malformed or schema-invalid response, the client retries once
   (max 2 attempts total) before raising a typed `GeminiParseError` that the
   UI surfaces as a friendly message — never a raw stack trace.
6. On success, the validated result is appended to `st.session_state`
   history (last 3 attempts kept), enabling a lightweight progress trend via
   `st.metric` deltas.

## 3. API Integration Strategy
- **Multimodality:** the app sends a PIL `Image` object directly alongside
  the text prompt in the same `generate_content` call — this is Gemini's
  native multimodal input path, not a separate OCR/vision preprocessing step.
- **Structured output over free text:** rather than parsing prose with
  regex, the prompt and generation config both constrain Gemini toward a
  fixed JSON schema. This is the core "advanced prompt engineering" choice:
  it makes the AI's output directly renderable, not just readable.
- **Resilience:** the retry-with-backoff pattern (2 attempts, 2s delay)
  assumes occasional malformed JSON is expected behavior at scale for any
  LLM-backed structured-output pipeline, not an edge case to ignore.

## 4. Logic Modules
| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI, form handling, session_state, rendering |
| `prompts.py` | Per-exercise system prompt templates |
| `gemini_client.py` | API calls, response cleaning, Pydantic validation, retries |
| `utils.py` | Image preprocessing, session_state helper functions |

## 5. Known Limitations
- Single static frame only — no real-time movement/rep tracking.
- Analysis quality is sensitive to photo lighting, framing, and angle.
- Free-tier Render hosting sleeps after inactivity, causing a cold-start
  delay (~30–50s) on the first request after idle time.
