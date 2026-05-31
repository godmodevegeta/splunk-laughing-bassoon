# streamlit/app.py
import streamlit as st
import time
import os
import sys
import io
import tarfile
import logging

# Silence noisy third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth.splunk_client import SplunkRestClient
from auth.mcp_validator import SplunkMCPValidator
from agent.schemaops_agent import SchemaOpsAgent
from rag.cim_oracle import CIMOracle

# --- SECURITY & ENV VARS ---
mcp_token = os.getenv("TALON_MCP_TOKEN")
splunk_pass = os.getenv("SPLUNK_PASSWORD", "YourNewSecurePassword123!")

st.set_page_config(page_title="TALON | SchemaOps", page_icon="⚡", layout="wide")

if not mcp_token:
    st.error("🔒 SECURITY HALT: MCP Token not configured.")
    st.info("Please set the TALON_MCP_TOKEN environment variable before launching The Forge.")
    st.stop()

# --- HEALTH CHECK ---
try:
    client = SplunkRestClient("localhost", 8089, "admin", splunk_pass)
    client.ping()
except Exception as e:
    st.error(f"❌ Cannot connect to Splunk Sandbox at localhost:8089. Is Docker running?")
    st.code(f"docker run -d -p 8000:8000 -p 8089:8089 -e SPLUNK_START_ARGS='--accept-license' -e SPLUNK_PASSWORD='{splunk_pass}' splunk/splunk:latest")
    st.stop()

# --- UI CONFIGURATION & CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0F0F0F; color: #E0E0E0; font-family: 'Courier New', Courier, monospace; }
    h1, h2, h3 { color: #E60073 !important; font-weight: 700; font-family: 'Helvetica Neue', sans-serif; }
    #MainMenu, footer, header {visibility: hidden;}
    .stButton>button { background-color: #E60073; color: white; border: none; border-radius: 2px; padding: 0.5rem 2rem; font-weight: bold; text-transform: uppercase; transition: all 0.2s; }
    .stButton>button:hover { background-color: #FF0080; color: white; }
    .terminal-box { background-color: #1A1A1A; border-left: 4px solid #E60073; padding: 15px; border-radius: 4px; font-family: monospace; color: #00FF00; margin-bottom: 20px; }
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
if 'forge_start_time' not in st.session_state:
    st.session_state.forge_start_time = 0

# --- HEADER: PROGRESS BAR ---
modes = ['DROP', 'ITERATE', 'VALIDATE', 'PACKAGE']
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
# MODE 1: DROP
# ==========================================
if st.session_state.mode == 'DROP':
    st.markdown("## DROP THE CHAOS")
    
    col1, col2, _ = st.columns(3)
    if col1.button("🔥 The Java Stacktrace"):
        st.session_state.raw_log = "2026-05-31 10:00:01 ERROR [main] App - Crash\njava.lang.NullPointerException\n\tat com.app.Main.run(Main.java:14)"
        st.session_state.mode = 'ITERATE'
        st.session_state.forge_start_time = time.time()
        st.rerun()
    if col2.button("🧱 Custom Firewall (IP:)"):
        st.session_state.raw_log = "2026-05-31 11:50:00 user=jdoe action=login client_address:192.168.1.50"
        st.session_state.mode = 'ITERATE'
        st.session_state.forge_start_time = time.time()
        st.rerun()
        
    st.session_state.raw_log = st.text_area("Or Paste Raw Log Sample:", height=150, value=st.session_state.raw_log)
    
    if st.button("🚀 FORGE THIS LOG") and st.session_state.raw_log:
        st.session_state.mode = 'ITERATE'
        st.session_state.forge_start_time = time.time()
        st.rerun()

# ==========================================
# MODE 2: ITERATE
# ==========================================
elif st.session_state.mode == 'ITERATE':
    st.markdown("## THE FORGE IS WORKING...")
    progress_container = st.container()
    
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
                
                # --- PATCH 1: DOCKER CONNECTION RESILIENCE ---
                try:
                    client.set_props_config(current_stanza, props_config)
                    client.reload_parsing_configs()
                    iteration_source = f"talon_demo/run_{int(time.time())}.log"
                    client.ingest_logs(st.session_state.raw_log, current_stanza, iteration_source, index="main")
                except Exception as e:
                    status.update(label="❌ SANDBOX CONNECTION LOST", state="error")
                    st.error(f"Sandbox connection lost: {e}")
                    st.info("Restart Docker and refresh the page.")
                    st.stop()
                
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
                    
                    placeholder = st.empty()
                    for i in range(2, 0, -1):
                        placeholder.markdown(f"*Retrying in {i}...*")
                        time.sleep(1)
                    placeholder.empty()
                    
    if success:
        with st.spinner("🔮 Initiating RAG CIM Alignment..."):
            for field in expected_fields:
                match = oracle.get_cim_mapping(field)
                if match and match['cim_field'] != field:
                    alias_key = f"FIELDALIAS-{field}_to_cim"
                    st.session_state.final_config[alias_key] = f"{field} AS {match['cim_field']}"
                    st.session_state.mapped_fields[field] = match['cim_field']
                    # --- PATCH 3: RAG VISUAL PROGRESS ---
                    st.toast(f"Mapped {field} → {match['cim_field']} ✅")
        
        st.session_state.mode = 'VALIDATE'
        st.rerun()
    else:
        st.error("Fatal: The Forge could not extract the required fields after 3 attempts.")
        if st.button("⬅️ START OVER"):
            st.session_state.mode = 'DROP'
            st.rerun()

# ==========================================
# MODE 3: VALIDATE
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
        st.info("Query: `index=main source=talon_demo/* | table _time, _raw, *`")

    with col2:
        st.markdown("#### ⚙️ Generated Config (Editable)")
        raw_props_str = f"[talon_demo_app]\n"
        for k, v in st.session_state.final_config.items():
            raw_props_str += f"{k} = {v}\n"
        edited_props = st.text_area("props.conf", value=raw_props_str, height=250)

    st.markdown("<br><hr>", unsafe_allow_html=True)
    nav_col1, _, nav_col3 = st.columns([1, 2, 1])
    with nav_col1:
        if st.button("⬅️ ABORT & RESTART"):
            st.session_state.mode = 'DROP'
            st.rerun()
    with nav_col3:
        if st.button("✅ APPROVE & PACKAGE ➡️"):
            st.session_state.final_config_str = edited_props
            st.session_state.mode = 'PACKAGE'
            st.rerun()

# ==========================================
# MODE 4: PACKAGE
# ==========================================
elif st.session_state.mode == 'PACKAGE':
    st.markdown("## ⚡ TALON FORGED — READY FOR BATTLE")
    
    elapsed = time.time() - st.session_state.forge_start_time
    roi_multiplier = int((6 * 3600) / elapsed) if elapsed > 0 else 0
    
    st.markdown(f"""
    <div style='background-color: #1A1A1A; padding: 20px; border-radius: 5px; margin-bottom: 20px;'>
        <h4 style='color: #E60073; margin-top: 0;'>🚀 MISSION IMPACT</h4>
        <p><b>Time Taken:</b> {elapsed:.1f} seconds</p>
        <p><b>Human Equivalent:</b> ~6 hours</p>
        <p><b>ROI:</b> ~{roi_multiplier}x Faster Time-To-Value</p>
    </div>
    """, unsafe_allow_html=True)
    
    def create_splunk_app_tarball(props_conf_content, app_name="talon_custom_app"):
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            
            props_bytes = props_conf_content.encode('utf-8')
            props_info = tarfile.TarInfo(name=f"{app_name}/default/props.conf")
            props_info.size = len(props_bytes)
            tar.addfile(props_info, io.BytesIO(props_bytes))
            
            app_conf = f"[install]\nis_configured = false\nstate = enabled\nbuild = 1\n\n[launcher]\nauthor = TALON\nversion = 1.0.0\ndescription = Auto-generated by TALON SchemaOps\n\n[ui]\nis_visible = false\nlabel = {app_name}\n"
            app_conf_bytes = app_conf.encode('utf-8')
            app_conf_info = tarfile.TarInfo(name=f"{app_name}/default/app.conf")
            app_conf_info.size = len(app_conf_bytes)
            tar.addfile(app_conf_info, io.BytesIO(app_conf_bytes))
            
            meta = "[]\naccess = read : [ * ], write : [ admin ]\n"
            meta_bytes = meta.encode('utf-8')
            meta_info = tarfile.TarInfo(name=f"{app_name}/metadata/default.meta")
            meta_info.size = len(meta_bytes)
            tar.addfile(meta_info, io.BytesIO(meta_bytes))
        
        tar_buffer.seek(0)
        return tar_buffer.getvalue()

    tarball_bytes = create_splunk_app_tarball(st.session_state.final_config_str)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="⬇️ DOWNLOAD .TAR.GZ",
            data=tarball_bytes,
            file_name="talon_custom_app.tar.gz",
            mime="application/gzip"
        )
    with col2:
        with st.expander("🚀 DEPLOY TO SPLUNK INSTANCE"):
            st.info("Direct push via REST API. Enter target Splunk credentials.")
            deploy_host = st.text_input("Host", value="localhost")
            deploy_user = st.text_input("Username", value="admin")
            deploy_pass = st.text_input("Password", type="password")
            
            if st.button("AUTHENTICATE & PUSH"):
                try:
                    deploy_client = SplunkRestClient(deploy_host, 8089, deploy_user, deploy_pass)
                    
                    # --- PATCH 2: BULLETPROOF CONFIG PARSER ---
                    lines = st.session_state.final_config_str.strip().split('\n')
                    edited_dict = {}
                    current_stanza = None
                    
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if line.startswith('[') and line.endswith(']'):
                            current_stanza = line[1:-1]
                            continue
                        if '=' in line and current_stanza:
                            k, v = line.split('=', 1)
                            edited_dict[k.strip()] = v.strip()
                            
                    deploy_client.set_props_config(current_stanza or "talon_deployed_app", edited_dict)
                    deploy_client.reload_parsing_configs()
                    st.success(f"✅ Successfully deployed configs to {deploy_host}:8089!")
                except Exception as e:
                    st.error(f"Deployment failed: {e}")

    st.markdown("<br><hr>", unsafe_allow_html=True)
    nav_col1, _, nav_col3 = st.columns([1, 1, 1])
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