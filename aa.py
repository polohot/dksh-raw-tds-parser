import os
import pandas as pd
import streamlit as st
import requests
import tempfile
import json

from customutils import *

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# App Configuration
st.set_page_config(page_title="PIM TDS parser")
st.title("PIM TDS parser - V0.1-alpha")
st.write("Only allow pdf files")

# Initialize step
if 'STEP' not in st.session_state:
    st.session_state['STEP'] = 'USER_UPLOAD'
# File dictionary to keep track of uploads and results
if 'file_dict' not in st.session_state:
    st.session_state['file_dict'] = {}
if 'dfPROD' not in st.session_state:
    st.session_state['dfPROD'] = pd.DataFrame()

###############
# USER UPLOAD #
###############

if st.session_state['STEP'] == 'USER_UPLOAD':
    uploaded_files = st.file_uploader("Upload your PIM TDS file", accept_multiple_files=True, type=["pdf"])
   
    if uploaded_files and st.button("Upload"):
        file_dict = {}
        for uploaded_file in uploaded_files:
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(uploaded_file.read())
                file_dict[uploaded_file.name] = {
                    'serverPath': tmp_file.name,
                    'status': 'Uploaded',
                    'result': None
                }
        st.session_state['file_dict'] = file_dict
        st.session_state['STEP'] = 'PARSE_FILE'
        st.rerun()

##############
# PARSE_FILE #
##############

elif st.session_state['STEP'] == 'PARSE_FILE':

    # ACTION - PARSE_FILE
    st.write("Parsing files...")

    # BUTTON TO PROCESS
    if st.button("Get Fields"):
        st.session_state['STEP'] = 'GET_FIELDS'
        st.rerun()

##############
# GET FIELDS #
############## 

elif st.session_state['STEP'] == 'GET_FIELDS':

    # ACTION - GET_FIELDS
    st.write("Extracting fields from uploaded files...")

    # BUTTON TO PROCESS
    if st.button("OK"):
        st.session_state['STEP'] = 'EXPORT'
        st.rerun()

####################
# EXPORT DATAFRAME #
####################


elif st.session_state['STEP'] == 'EXPORT':
    st.write("Exporting results...")





with st.expander("Parsed Results", expanded=False):
    st.json(st.session_state['file_dict'])
with st.expander("dfPROD", expanded=False):
    st.dataframe(st.session_state['dfPROD'])