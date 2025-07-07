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
st.set_page_config(page_title="PIM TDS parser")
st.title("PIM TDS parser - V0.1-alpha")
st.write("Only allow pdf files")

# Initialize session state
if 'STEP' not in st.session_state:
    st.session_state['STEP'] = 'USER_UPLOAD_AND_PARSE'
if 'file_dict' not in st.session_state:
    st.session_state['file_dict'] = {}
if 'dfPROD' not in st.session_state:
    st.session_state['dfPROD'] = pd.DataFrame()



#######################
# USER UPLOAD & PARSE #
#######################
if st.session_state['STEP']=='USER_UPLOAD_AND_PARSE':
    uploaded_files = st.file_uploader("Upload your PIM TDS file", accept_multiple_files=True, type=["pdf"])
    if uploaded_files and st.button("Process"):
        ### UPLOAD TO TEMP PATH
        st.write("⏳ Processing uploaded files...")
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
        ### PARSE FILES
        file_dict = st.session_state['file_dict']
        for filename, fileinfo in file_dict.items():
            st.write(f"⏳ **{filename}** Preparing...")
            ### S1_PARSE_TO_TEXT
            file_dict[filename]['S1_PARSE'] = {}
            try:
                with open(fileinfo['serverPath'], 'rb') as f:
                    mime = 'application/pdf' if filename.endswith('.pdf') else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    files = [('files', (filename, f, mime))]
                    data = {"apikey": os.getenv('LLAMA_CLOUD_API_KEY')}
                    response = requests.post(
                        "https://ancient-almeda-personal-personal-22e19704.koyeb.app/llama_parse_batch",
                        data=data,
                        files=files,
                        verify=False)
                    if response.status_code == 200:
                        file_dict[filename]['S1_PARSE']['status'] = '✅ Success'
                        file_dict[filename]['S1_PARSE']['result'] = response.json()['results']
                    else:
                        file_dict[filename]['S1_PARSE']['status'] = f'❌ Error: (HTTP {response.status_code})'
            except Exception as e:
                file_dict[filename]['S1_PARSE']['status'] = f'❌ Error: {str(e)}'
            ### S2_READ_PDF_TO_BASE64
            file_dict[filename]['S2_READ_PDF_TO_BASE64'] = {}
            try:
                doc = fitz.open(fileinfo['serverPath'])          
                base64_pages = []
                for page_number in range(len(doc)):
                    page = doc.load_page(page_number)
                    pix = page.get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    buffered = io.BytesIO()
                    img.save(buffered, format="PNG")
                    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    base64_pages.append(img_base64)
                file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] = '✅ Success'
                file_dict[filename]['S2_READ_PDF_TO_BASE64']['pages'] = base64_pages
            except Exception as e:
                file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] = f'❌ Error: {str(e)}'
                file_dict[filename]['S2_READ_PDF_TO_BASE64']['pages'] = []
            ### S3_GET_PROD_NAME_AND_SUPP
            file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP'] = {}
            if file_dict[filename]['S1_PARSE']['status'] == '✅ Success' and file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] == '✅ Success':
                try:
                    parsed_output = str(file_dict[filename]['S1_PARSE']['result'][0])
                    question = buildQuestionGetProductNameAndSupplierFromParsedText(parsed_output)
                    # BUILD BODY
                    body = {
                        "model": "gpt-4o",
                        "messages": [{'role': 'user', 'content': question}],
                        "max_tokens": 1000,
                        "temperature": 0.2}
                    # CALL API
                    response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
                                            json=body, 
                                            params={"apikey": os.getenv('OPENAI_API_KEY')},
                                            verify=False)
                    if response.status_code == 200:
                        file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = '✅ Success'
                        rescontent = response.json()['choices'][0]['message']['content']
                        rescontent = rescontent.replace('```','')
                        rescontent = rescontent.replace('json','')         
                        rescontent = json.loads(rescontent)         
                        file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['result'] = rescontent
                        st.write(f"⏳ **{filename}** found {len(rescontent)} products.")
                        for product in rescontent:
                            st.write(f"⏳ **{filename}** Product: {product['PRODUCT_NAME']}, Supplier: {product['SUPPLIER_NAME']}")   
                    else:
                        file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: (HTTP {response.status_code})'
                except Exception as e:
                    file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: {str(e)}'
            else:
                file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: S1 or S2 error'

        # DEBUG
        st.session_state['file_dict'] = file_dict
        with st.expander("Parsed Results", expanded=False):
            st.json(st.session_state['file_dict'])
        with st.expander("dfPROD", expanded=False):
            st.dataframe(st.session_state['dfPROD'])

        # BUILD SUMMARY DATAFRAME
        st.write(f"⏳ **BUILDING SUMMARY TABLE**")
        lsdf = []
        for filename in file_dict.keys():
            if file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] == '✅ Success':
                for product in file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['result']:
                    lsdf.append(
                        pd.DataFrame({'FILE_NAME':[filename],
                        'PRODUCT_NAME': [product['PRODUCT_NAME']],
                        'SUPPLIER_NAME': [product['SUPPLIER_NAME']]}))
            else:
                lsdf.append(
                    pd.DataFrame({'FILE_NAME':[filename],
                    'PRODUCT_NAME': [file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status']],
                    'SUPPLIER_NAME': [file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status']]}))
        dfPROD = pd.concat(lsdf, ignore_index=True)
        st.session_state['file_dict'] = file_dict
        st.session_state['dfPROD'] = dfPROD.copy()
        st.session_state['STEP'] = 'GET_FIELDS'
        st.rerun()

##############
# GET FIELDS #
############## 
elif st.session_state['STEP']=='GET_FIELDS':
    file_dict = st.session_state['file_dict']
    dfPROD = st.session_state['dfPROD'].copy()
    st.dataframe(dfPROD)
    if st.button("Get Structured Data From PDF"):
        dfPROD['RAW_FIELDS_JSON'] = None
        dfPROD['RAW_FIELDS'] = None
        dfPROD['RAW_COMPOSITION_JSON'] = None
        dfPROD['RAW_COMPOSITION'] = None
        # LOOP EACH ROW
        for i in range(len(dfPROD)):
            # GET ROW DATA
            file_name = dfPROD.iloc[i]['FILE_NAME']
            product_name = dfPROD.iloc[i]['PRODUCT_NAME']
            manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
            # CHECK IF NOT ERROR
            if 'Error' in product_name:
                st.write(f"❌ **{file_name}** Error, will skip...")
                continue
            # PROCESS      
            st.write(f"⏳ Searching **{file_name}** for **{product_name}** from **{manufacturer_name}**...")
            # GET INPUT DATA FOR LLM
            parsed_text = str(file_dict[file_name]['S1_PARSE']['result'][0])
            ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
            ########################
            # SEARCH INFO FROM PDF #
            ########################
            # BUILD BODY
            body = buildStructuredOutputBody(parsed_text, product_name, manufacturer_name, ls_base64)
            # CALL API
            try:
                response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
                                        json=body, 
                                        params={"apikey": os.getenv('OPENAI_API_KEY')},
                                        verify=False)
                response_json = response.json()
                dfPROD['RAW_FIELDS_JSON'].iat[i] = response_json
                if response.status_code == 200:
                    obj = response_json['choices'][0]['message']['content']
                    parsed = json.loads(obj)
                    dfPROD['RAW_FIELDS'].iat[i] = parsed
                else:
                    dfPROD['RAW_FIELDS'].iat[i] = f'❌ Error: (HTTP {response.status_code})'
            except Exception as e:
                dfPROD['RAW_FIELDS'].iat[i] = f'❌ Error: {str(e)}'
                st.write(f"❌ Error Searching Fields **{file_name}** for **{product_name}** from **{manufacturer_name}**: {str(e)}")
            ######################
            # SEARCH INGREDIENTS #
            ######################
            # BUILD BODY
            body = buildCompositionOutputBody(parsed_text, product_name, manufacturer_name, ls_base64)
            # CALL API
            try:
                response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
                                        json=body, 
                                        params={"apikey": os.getenv('OPENAI_API_KEY')},
                                        verify=False)
                response_json = response.json()
                dfPROD['RAW_COMPOSITION_JSON'].iat[i] = response_json
                if response.status_code == 200:
                    obj = response_json['choices'][0]['message']['content']
                    parsed = json.loads(obj)
                    dfPROD['RAW_COMPOSITION'].iat[i] = parsed
                else:
                    dfPROD['RAW_COMPOSITION'].iat[i] = f'❌ Error: (HTTP {response.status_code})'
            except Exception as e:
                dfPROD['RAW_COMPOSITION'].iat[i] = f'❌ Error: {str(e)}'
                st.write(f"❌ Error Searching Composition **{file_name}** for **{product_name}** from **{manufacturer_name}**: {str(e)}")
        # PREPARE DF
        dfPROD['CNT_COMPOSITION'] = [None if 'Error' in x else len(x['composition']) for x in dfPROD['RAW_COMPOSITION']]
        # SAVE TO SESSION
        st.session_state['file_dict'] = file_dict
        st.session_state['dfPROD'] = dfPROD.copy()
        st.session_state['STEP'] = 'EXPORT'       
        st.rerun()

##########
# EXPORT #
########## 
elif st.session_state['STEP']=='EXPORT':
    file_dict = st.session_state['file_dict']
    dfPROD = st.session_state['dfPROD'].copy()
    st.dataframe(dfPROD)


##########
# EXPORT #
########## 
# with st.expander("Parsed Results", expanded=False):
#     st.json(st.session_state['file_dict'])
# with st.expander("dfPROD", expanded=False):
#     st.dataframe(st.session_state['dfPROD'])
