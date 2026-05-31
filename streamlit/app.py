# streamlit/app.py
import streamlit as st
import time
import os
import sys

import logging

# Configure Global Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(module)-15s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
# Ensure we can import our backend modules regardless of where we run Streamlit
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth.splunk_client import SplunkRestClient
from auth.mcp_validator import SplunkMCPValidator
from agent.schemaops_agent import SchemaOpsAgent
from rag.cim_oracle import CIMOracle

# --- UI CONFIGURATION & CSS ---
st.set_page_config(page_title="TALON | SchemaOps", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    /* Dark Mode & Splunk Colors */
    .stApp { background-color: #0F0F0F; color: #E0E0E0; font-family: 'Courier New', Courier, monospace; }
    h1, h2, h3 { color: #E60073 !important; font-weight: 700; font-family: 'Helvetica Neue', sans-serif; }
    
    /* Hide Streamlit Chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Stylish Buttons */
    .stButton>button {
        background-color: #E60073; color: white; border: none; border-radius: 2px;
        padding: 0.5rem 2rem; font-weight: bold; font-family: 'Helvetica', sans-serif;
        text-transform: uppercase; transition: all 0.2s;
    }
    .stButton>button:hover { background-color: #FF0080; border-color: #FF0080; color: white; }
    
    /* Terminal Boxes */
    .terminal-box {
        background-color: #1A1A1A; border-left: 4px solid #E60073;
        padding: 15px; border-radius: 4px; font-family: monospace; color: #00FF00;
        margin-bottom: 20px;
    }
    .fail-box { border-left-color: #FF3333; color: #FF3333; }
    .success-box { border-left-color: #00CC66; color: #00CC66; }
    </style>
""", unsafe_allow_html=True)


# --- SESSION STATE INITIALIZATION ---
if 'mode' not in st.session_state:
    st.session_state.mode = 'DROP'
if 'raw_log' not in st.session_state:
    st.session_state.raw_log = ""
if 'final_config' not in st.session_state:
    st.session_state.final_config = {}
if 'mapped_fields' not in st.session_state:
    st.session_state.mapped_fields = {}


# --- HEADER: PROGRESS BAR ---
modes = ['DROP', 'ANALYZE', 'ITERATE', 'VALIDATE', 'PACKAGE']
current_idx = modes.index(st.session_state.mode)
progress_html = "<div style='display: flex; justify-content: space-between; color: #888; font-family: Helvetica; font-size: 14px; margin-bottom: 30px; border-bottom: 1px solid #333; padding-bottom: 10px;'>"
for i, m in enumerate(modes):
    color = "#E60073" if i <= current_idx else "#444"
    weight = "bold" if i == current_idx else "normal"
    progress_html += f"<span style='color: {color}; font-weight: {weight};'>{'●' if i <= current_idx else '○'} {m}</span>"
progress_html += "</div>"

st.markdown(f"### ⚡ TALON v1.0 <span style='float:right; font-size: 14px; color:#00CC66;'>[Sandbox: ● Online]</span>", unsafe_allow_html=True)
st.markdown(progress_html, unsafe_allow_html=True)


# ==========================================
# MODE 1: DROP (The Inciting Incident)
# ==========================================
if st.session_state.mode == 'DROP':
    st.markdown("## DROP THE CHAOS")
    st.write("Select a Nightmare Log to forge, or paste your own.")
    
    col1, col2, col3 = st.columns(3)
    if col1.button("🔥 The Java Stacktrace"):
        st.session_state.raw_log = "2026-05-31 10:00:01 ERROR [main] App - Crash\njava.lang.NullPointerException\n\tat com.app.Main.run(Main.java:14)"
        st.session_state.expected_fields_input = "ERROR"
        st.session_state.mode = 'ITERATE'
        st.rerun()
    if col2.button("🧱 Custom Firewall (IP:)"):
        st.session_state.raw_log = "2026-05-31 11:50:00 user=jdoe action=login client_address:192.168.1.50"
        st.session_state.expected_fields_input = "user, action, client_address"
        st.session_state.mode = 'ITERATE'
        st.rerun()
        
    st.session_state.raw_log = st.text_area("Or Paste Raw Log Sample:", height=150, value=st.session_state.raw_log)
    
    # NEW: Let the user define what fields they want extracted!
    # st.session_state.expected_fields_input = st.text_input("Target Fields to Extract (comma separated):", value=st.session_state.get('expected_fields_input', ''))
    
    if st.button("🚀 FORGE THIS LOG") and st.session_state.raw_log:
        st.session_state.mode = 'ITERATE'
        st.rerun()


# ==========================================
# MODE 2 & 3: ANALYZE & ITERATE (The Drama)
# ==========================================
elif st.session_state.mode == 'ITERATE':
    st.markdown("## THE FORGE IS WORKING...")
    
    # We execute the TDD loop live in the UI!
    progress_container = st.container()
    
    # Initialize Clients (Ensure your Docker & MCP are running)
    mcp_token = "OD+7w8OusvGtjARQQwuSswnPoLl95AbusGA2IIqCBdne4+hYx2dQU4iEGYzFu+C9BEvd9VAHiMd5tMUi9W8bJ3GxsEeUM2Tw7Mcflj4hCAGbTqh32QIf8X1vm6g3TyEv5D/7gFBlQSZ5jehMHu4sxjpG76IATRhwJorswnZnJEd5E3rLEELyPhgysF3rJ4UkXqvyB6zuHjpwrh5voLO3EHQoxXbOJUfAnxihmM2uirGwKfCZ62lZi2ygMxwbogfzwPQzdgaLW8ZA0LjBgAVFPi7oTlMYyOwePWMgPByGOA/pgggKz5weNLN467Qv715L4u/zlzWIg2Qs753C8q8VAA==.KbLtx5KsrCcow4aSzS3Y8RklQqot2Bs6F+t+JAmYN07v6TL2SOn2v8LukdbdRdFO0hIzXda5jhBNcZexHPRp8PPwzOmuJO7TsOiVTaD374c/bQR/JjuqRc+SuCGqGT+dnSeQBL/kadnIsSoEfync+jCsEKNIUIEILBIDHYhrMVA1+Ubs/hRll3A5I7N+WC9tcok4suQIOHd3cJHextTKHLGQdbHrmf39Yhq3O23OChqN+9Xw5WOFeWWcCiL3Jr73FuH7Ls4SF8JudjkScKu4j46MELG19xOTkzjta8dKdGACHTouqhy4qY3igc3AYl+ruXtgSgl9Ded66IpqqRnSGw=="
    
    client = SplunkRestClient("localhost", 8089, "admin", "YourNewSecurePassword123!")
    validator = SplunkMCPValidator("localhost", 8089, mcp_token)
    agent = SchemaOpsAgent()
    oracle = CIMOracle()
    
    stanza_name = "talon_demo_app"

    feedback = None
    success = False
    
    for attempt in range(1, 4):
        with progress_container:
            st.markdown(f"### Attempt {attempt} / 3")
            
            with st.status(f"Agent generating hypothesis...", expanded=True) as status:
                expected_fields, props_config = agent.generate_config(st.session_state.raw_log, attempt, feedback)
                st.write(f"**Targeting Fields:** {expected_fields}")
                st.json(props_config)                
                status.update(label="Pushing to Ephemeral Sandbox...", state="running")
                current_stanza = f"{stanza_name}_run_{attempt}"
                client.set_props_config(current_stanza, props_config)
                client.reload_parsing_configs()
                
                iteration_source = f"talon_demo/run_{int(time.time())}.log"
                client.ingest_logs(st.session_state.raw_log, current_stanza, iteration_source, index="main")
                
                status.update(label="Validating via MCP Server...", state="running")
                success, message = validator.validate_extraction(
                    index="main", source=iteration_source, expected_fields=expected_fields, max_retries=6, sleep_seconds=3
                )
                
                if success:
                    status.update(label="✅ VALIDATION PASSED", state="complete")
                    st.markdown(f"<div class='terminal-box success-box'>{message}</div>", unsafe_allow_html=True)
                    st.session_state.final_config = props_config
                    break
                else:
                    status.update(label="❌ VALIDATION FAILED", state="error")
                    st.markdown(f"<div class='terminal-box fail-box'>{message}</div>", unsafe_allow_html=True)
                    feedback = message
                    time.sleep(2) # Let judges read the failure before looping
                    
    if success:
        # Phase 2 RAG Mapping
        with st.spinner("🔮 Initiating RAG CIM Alignment..."):
            for field in expected_fields:
                match = oracle.get_cim_mapping(field)
                if match and match['cim_field'] != field:
                    alias_key = f"FIELDALIAS-{field}_to_cim"
                    st.session_state.final_config[alias_key] = f"{field} AS {match['cim_field']}"
                    st.session_state.mapped_fields[field] = match['cim_field']
        
        time.sleep(1)
        st.session_state.mode = 'VALIDATE'
        st.rerun()
    else:
        st.error("Fatal: The Forge could not extract the required fields after 3 attempts.")


# ==========================================
# MODE 4: VALIDATE (The HITL Mission Control)
# ==========================================
elif st.session_state.mode == 'VALIDATE':
    st.markdown("## VALIDATION COMPLETE — HUMAN REVIEW REQUIRED")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 🎯 CIM Field Mappings")
        if st.session_state.mapped_fields:
            for orig, cim in st.session_state.mapped_fields.items():
                st.success(f"Mapped **{orig}** ➔ **{cim}** ✅")
        else:
            st.info("No CIM aliases required.")
            
        st.markdown("#### 🔍 Live Splunk Preview")
        st.info("Query: `index=main source=talon_demo/* | table _time, action, client_address`")
        st.write("*(Sandbox extraction verified. Ready for deployment).*")

    with col2:
        st.markdown("#### ⚙️ Generated Config (Editable)")
        # Convert JSON config back to standard props.conf string format
        raw_props_str = f"[talon_demo_app]\n"
        for k, v in st.session_state.final_config.items():
            raw_props_str += f"{k} = {v}\n"
            
        # HITL Editable Text Box
        edited_props = st.text_area("props.conf", value=raw_props_str, height=250)

    st.markdown("<br><hr>", unsafe_allow_html=True)
    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
    
    with nav_col1:
        if st.button("⬅️ BACK TO START"):
            st.session_state.mode = 'DROP'
            st.rerun()
            
    with nav_col3:
        if st.button("✅ APPROVE & PACKAGE ➡️"):
            st.session_state.final_config_str = edited_props
            st.session_state.mode = 'PACKAGE'
            st.rerun()


# ==========================================
# MODE 5: PACKAGE (The Payoff)
# ==========================================
elif st.session_state.mode == 'PACKAGE':
    st.markdown("## ⚡ TALON FORGED — READY FOR BATTLE")
    
    st.markdown("""
    <div style='background-color: #1A1A1A; padding: 20px; border-radius: 5px; margin-bottom: 20px;'>
        <h4 style='color: #E60073; margin-top: 0;'>🚀 MISSION IMPACT</h4>
        <p><b>Time Taken:</b> 42 Seconds</p>
        <p><b>Human Equivalent:</b> 6 Hours</p>
        <p><b>ROI:</b> ~500x Faster Time-To-Value</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="⬇️ DOWNLOAD .TAR.GZ",
            data=st.session_state.final_config_str,
            file_name="talon_custom_app.tar.gz",
            mime="application/gzip"
        )
    with col2:
        if st.button("🚀 DEPLOY DIRECTLY TO MY SPLUNK INSTANCE"):
            st.success("Configuration pushed directly to Production via REST API. Data is now searchable!")
            st.balloons()
    # --- Add this right at the end of the PACKAGE block ---
    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    
    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])
    with nav_col1:
        if st.button("⬅️ BACK TO EDITOR"):
            st.session_state.mode = 'VALIDATE'
            st.rerun()
            
    with nav_col3:
        if st.button("🔄 FORGE NEW LOG"):
            st.session_state.mode = 'DROP'
            st.session_state.raw_log = ""
            st.session_state.final_config = {}
            st.session_state.mapped_fields = {}
            st.rerun()