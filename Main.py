# import datetime
# import streamlit as st

# # Initialize once
# if "log" not in st.session_state:
#     st.session_state.log = []
# if 'STEP1' not in st.session_state:
#     st.session_state['STEP1'] = True
# if 'STEP2' not in st.session_state:
#     st.session_state['STEP2'] = False




# def add_to_log(text: str, indent: float = 0):
#     timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     html = (
#         f'<div>'
#         f'  <span>[{timestamp}]</span>'
#         f'  <span style="margin-left: {indent}rem;">{text}</span>'
#         f'</div>'
#     )
#     st.session_state.log.append(html)   # persist

# def render_log():
#     for line in st.session_state.log:
#         st.markdown(line, unsafe_allow_html=True)

# # --- Example usage ---
# st.button("Do something", on_click=lambda: add_to_log("Clicked the button"))
# st.button("Force rerun", on_click=st.rerun)

# st.write("### Log")
# render_log()











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

