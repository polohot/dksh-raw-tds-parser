import streamlit as st
from streamlit_js_eval import streamlit_js_eval
import datetime
###############################################################################################################################################################################
###############################################################################################################################################################################
# Server time
server_time = datetime.datetime.now()
# Try to grab client time (in ms since epoch)
client_ts_ms = streamlit_js_eval(
    js_expressions="Date.now()", 
    key="client_ts")
# Guard against the initial None
if client_ts_ms is None:
    st.info("Waiting for browser timestamp…")   # show a friendly message
    st.stop()                                   # stop execution here
# Only from here on do we know client_ts_ms is a number
client_time = datetime.datetime.fromtimestamp(client_ts_ms / 1000.0)
delta = server_time - client_time
###############################################################################################################################################################################
###############################################################################################################################################################################
# App Configuration
st.set_page_config(page_title="PIM TDS parser", layout="wide")
st.title("PIM TDS parser - V0.2-alpha")

st.write("**Server time:**", server_time.strftime("%Y-%m-%d %H:%M:%S.%f"))
st.write("**Client time:**", client_time.strftime("%Y-%m-%d %H:%M:%S.%f"))
st.write(f"**Difference:** {delta.total_seconds()*1000:.0f} ms")

strShow = '''
[V0.8-alpha] - 2025-08-25
- Adding MainAPI.py for API UAT

[V0.7-alpha] - 2025-08-20
- Adding page "(3) Gen PIM Template - No Search.py" - remove search function

[V0.6-alpha] - 2025-08-03
- Change Selection from list method to use Flag, instead of multi select for 
    COMPOSITIONS, APPLICATIONS, FUNCTIONS, CLAIMS

[V0.5-alpha] - 2025-07-30
- Fix bug for CLAIMS
- New resource map to this project
    AZURE AI FOUNDARY DEPLOYMENT : azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser
    AZURE DOCUMENT INTELLIGENCE : document-intelligence-standard-s0-dksh-raw-tds-parser
    OPENAI PROJECT : dksh-raw-tds-parser

[V0.4-alpha] - 2025-07-24
- New resource map to this project
    AZURE AI FOUNDARY DEPLOYMENT : dksh-raw-tds-parser
    AZURE DOCUMENT INTELLIGENCE : document-intelligence-standard-s0-dksh-raw-tds-parser
    OPENAI PROJECT : dksh-raw-tds-parser
- Add Generation "Product Description"
- Current cost around 10 THB per product

[V0.3-alpha] - 2025-07-23
- Change Subscription of Azure Document Intelligence from Free to standard-s0 resource
- (2) Gen PIM Template - Change location of run Log to show on top
- (2) Gen PIM Template - COMPOSITION, Allow all BL to do web search and list COMPOSITION,
                       - Except PCI, must select COMPOSITION from given list
- (2) Gen PIM Template - PHYSICAL_FORM if not found in document put N/A

[V0.2-alpha] - 2025-07-22
- Change Parsing PDF, from using LlamaParse, to use Internal Azure AI Document Intelligence for compliance
- Change from using OpenAI API to Azure AI Foundary API for compliance
- Create Page "Gen PIM Form"

[V0.1-alpha] - 2025-07-08
- First Deployment for "Gen Product Form"
'''

st.code(strShow)
###############################################################################################################################################################################
###############################################################################################################################################################################
