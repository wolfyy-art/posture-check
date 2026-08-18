"""
app.py
------
"Roast My Form" — AI-powered exercise posture analyser.

Run locally:
    streamlit run app.py

Requires GEMINI_API_KEY in .env (or in Streamlit Cloud secrets).
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from gemini_client import FormAnalysis, GeminiClientError, GeminiParseError, analyse_form
from prompts import SUPPORTED_EXERCISES, get_prompt
from utils import (
    bytes_to_pil,
    get_score_delta,
    grade_colour,
    init_session_state,
    preprocess_image,
    record_attempt,
    severity_emoji,
)

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

# Load .env relative to this file's location so it works regardless of which
# directory Streamlit was launched from.
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

st.set_page_config(
    page_title="Roast My Form 🔥",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_session_state(st.session_state)

# ---------------------------------------------------------------------------
# Custom CSS — minimal, keeps things readable on mobile too
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
        /* Score ring container */
        .score-ring {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }
        /* Grade badge */
        .grade-badge {
            font-size: 3rem;
            font-weight: 900;
            line-height: 1;
        }
        /* Severity colour helpers for the table */
        .sev-high   { color: #e74c3c; font-weight: 700; }
        .sev-medium { color: #e67e22; font-weight: 700; }
        .sev-low    { color: #f1c40f; font-weight: 700; }
        /* Subtle card border */
        [data-testid="stExpander"] {
            border: 1px solid #2d2d2d;
            border-radius: 8px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🔥 Roast My Form")
st.caption(
    "AI-powered exercise posture analysis using Gemini Vision. "
    "Snap a photo of your starting position and get instant form feedback."
)
st.divider()

# ---------------------------------------------------------------------------
# Two-column layout: LEFT = input panel, RIGHT = results dashboard
# ---------------------------------------------------------------------------

left_col, right_col = st.columns([1, 1.4], gap="large")

# ── LEFT: Input panel ────────────────────────────────────────────────────────
with left_col:
    st.subheader("📸 Capture Your Form")

    # Privacy notice — shown before camera activates
    st.info(
        "🔒 **Privacy notice:** Your photo is sent directly to Google's Gemini API "
        "for analysis and is not stored by this application.",
        icon=None,
    )

    # st.form batches all widgets — avoids re-running the script on every
    # dropdown change or camera click before the user is ready.
    with st.form(key="analysis_form", clear_on_submit=False):
        exercise = st.selectbox(
            "Select your exercise",
            options=SUPPORTED_EXERCISES,
            index=0,
            help="Choose the movement you want analysed.",
        )

        camera_image = st.camera_input(
            label="Take a photo of your starting position",
            help="Position yourself so your full body is visible in the frame.",
        )

        submitted = st.form_submit_button(
            "🔥 Roast My Form",
            use_container_width=True,
            type="primary",
        )

    # ── Exercise tip cards (shown below the form) ─────────────────────────
    with st.expander("💡 Tips for a good photo", expanded=False):
        st.markdown(
            """
            - **Full body visible** — step back so your whole body fits in frame.
            - **Side or front angle** — most flaws are visible from a 45° or side view.
            - **Good lighting** — avoid backlighting; face a window if possible.
            - **Hold the position** — stay still while the photo is taken.
            - **Wear fitted clothing** — baggy clothes hide joint alignment cues.
            """
        )

# ── RIGHT: Results dashboard ─────────────────────────────────────────────────
with right_col:
    st.subheader("📊 Form Analysis")

    # ── Processing ────────────────────────────────────────────────────────
    if submitted:
        if camera_image is None:
            st.warning("⚠️ No photo captured. Use the camera above, then tap **Roast My Form**.")
            st.stop()

        with st.spinner("Analysing your form with Gemini Vision… this takes ~5-10 seconds"):
            try:
                pil_image = preprocess_image(bytes_to_pil(camera_image.getvalue()))
                prompt = get_prompt(exercise)
                analysis: FormAnalysis = analyse_form(pil_image, prompt)

                # Persist to session state
                st.session_state.last_analysis = analysis
                st.session_state.last_exercise = exercise
                record_attempt(st.session_state, exercise, analysis)

            except GeminiClientError as exc:
                st.error(f"🔑 Configuration error: {exc}")
                st.stop()

            except GeminiParseError as exc:
                st.error(
                    "⚠️ Gemini returned an unexpected response. "
                    "Please try again — if the problem persists, check the logs."
                )
                with st.expander("🐛 Debug: raw API response", expanded=False):
                    st.code(exc.raw_response or "(empty)", language="text")
                st.stop()

            except Exception as exc:
                st.error(f"❌ Unexpected error: {type(exc).__name__}: {exc}")
                st.stop()

    # ── Render stored analysis (persists across reruns) ───────────────────
    analysis = st.session_state.last_analysis
    exercise_label = st.session_state.last_exercise

    if analysis is None:
        # Placeholder — shown before first submission
        st.markdown(
            """
            <div style="text-align:center; padding: 3rem; color: #666;">
                <p style="font-size:3rem;">🏋️</p>
                <p>Your analysis results will appear here.</p>
                <p>Select an exercise, snap a photo, then hit <strong>Roast My Form</strong>.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # ── Image quality guard ───────────────────────────────────────────
        if analysis.image_quality != "ok":
            quality_messages = {
                "blurry": "📷 The photo is too blurry for accurate analysis.",
                "no_person": "🕵️ No person detected in the photo.",
                "partial_frame": "✂️ Your body is partially cut off — step back and retake.",
            }
            msg = quality_messages.get(
                analysis.image_quality,
                "⚠️ Image quality issue detected."
            )
            st.warning(f"{msg} Please retake the photo.")
            st.caption(f"Gemini said: _{analysis.summary}_")
            st.stop()

        # ── KPI cards row ─────────────────────────────────────────────────
        delta = get_score_delta(st.session_state)
        delta_str = f"{delta:+d}" if delta is not None else None

        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1:
            st.metric(
                label="Overall Score",
                value=f"{analysis.overall_score}/100",
                delta=delta_str,
                delta_color="normal",
            )
        with kpi2:
            colour = grade_colour(analysis.grade)
            st.markdown(
                f"<div style='text-align:center'>"
                f"<p style='font-size:0.85rem; color:#999; margin-bottom:4px'>Grade</p>"
                f"<p class='grade-badge' style='color:{colour}'>{analysis.grade}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with kpi3:
            flaw_count = len(analysis.flaws)
            high_count = sum(1 for f in analysis.flaws if f.severity == "high")
            st.metric(
                label="Flaws Found",
                value=flaw_count,
                delta=f"{high_count} high severity" if high_count else "0 high severity",
                delta_color="inverse" if high_count else "off",
            )

        st.caption(f"**Exercise:** {exercise_label}  |  **Summary:** {analysis.summary}")
        st.divider()

        # ── Flaw breakdown table ──────────────────────────────────────────
        if analysis.flaws:
            st.markdown("#### 🩻 Form Flaws")
            flaw_data = [
                {
                    "Severity": f"{severity_emoji(f.severity)} {f.severity.capitalize()}",
                    "Body Area": f.area,
                    "Issue": f.issue,
                }
                for f in sorted(
                    analysis.flaws,
                    key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.severity, 3),
                )
            ]
            df = pd.DataFrame(flaw_data)
            st.data_editor(
                df,
                use_container_width=True,
                hide_index=True,
                disabled=True,
                column_config={
                    "Severity": st.column_config.TextColumn(width="small"),
                    "Body Area": st.column_config.TextColumn(width="small"),
                    "Issue": st.column_config.TextColumn(width="large"),
                },
            )
        else:
            st.success("✅ No significant form flaws detected — great form!")

        # ── Fix tips expander ─────────────────────────────────────────────
        if analysis.fix_tips:
            with st.expander("🛠️ Coaching Notes & Fix Tips", expanded=True):
                for i, tip in enumerate(analysis.fix_tips, start=1):
                    st.markdown(f"**{i}.** {tip}")

# ---------------------------------------------------------------------------
# Attempt History — shown below both columns
# ---------------------------------------------------------------------------

st.divider()
history = st.session_state.attempt_history

if history:
    st.subheader("📈 Recent Attempts (last 3)")
    cols = st.columns(len(history))
    for col, attempt in zip(cols, reversed(history)):
        with col:
            colour = grade_colour(attempt["grade"])
            st.markdown(
                f"<div style='border:1px solid #333; border-radius:8px; padding:0.8rem; text-align:center'>"
                f"<p style='font-size:0.75rem; color:#888; margin:0'>{attempt['timestamp']}</p>"
                f"<p style='font-size:0.9rem; margin:4px 0; font-weight:600'>{attempt['exercise']}</p>"
                f"<p style='font-size:1.8rem; font-weight:900; color:{colour}; margin:0'>{attempt['score']}</p>"
                f"<p style='font-size:0.85rem; color:{colour}; margin:0'>Grade {attempt['grade']}</p>"
                f"</div>",
                unsafe_allow_html=True,
            )
else:
    st.caption("Your last 3 attempts will appear here after you submit your first analysis.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.markdown(
    "<p style='text-align:center; color:#555; font-size:0.8rem'>"
    "Roast My Form · Powered by Gemini Vision · Built with Streamlit · "
    "<em>Not a substitute for professional physiotherapy advice.</em>"
    "</p>",
    unsafe_allow_html=True,
)
