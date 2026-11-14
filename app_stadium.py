"""Stadium version of the War Room: serves the animated page inside Streamlit.
Deploy with this as the main file instead of app.py if you want the stadium look."""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="RR Pressure War Room", page_icon="🏏", layout="wide")
st.markdown("<style>.block-container{padding:0;max-width:100%}header,footer{visibility:hidden}</style>", unsafe_allow_html=True)
page = (Path(__file__).parent / "war_room_stadium.html").read_text(encoding="utf-8")
if hasattr(st, "iframe"):
    st.iframe(page, height=900)
else:
    components.html(page, height=900, scrolling=True)
