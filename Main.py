import os
import io
import pandas as pd
import streamlit as st
import requests
import tempfile
import json
import base64
import fitz
from PIL import Image

from customutils import *

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# App Configuration
st.set_page_config(page_title="PIM TDS parser", layout="wide")
st.title("PIM TDS parser - V0.1-alpha")

strShow = '''
[V0.1-alpha] - 2025-07-08
- First Deployment for "Gen Product Form"
'''

st.code(strShow)