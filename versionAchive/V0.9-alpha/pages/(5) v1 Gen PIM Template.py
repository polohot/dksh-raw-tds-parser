# Standard library imports
import base64
import datetime
import io
import json
import os
import tempfile
import time
import uuid
# Third‑party imports
import fitz
import numpy as np
import pandas as pd
from PIL import Image
import pycountry
import requests
import streamlit as st
from streamlit_js_eval import streamlit_js_eval
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# Azure AI Document Intelligence
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
# Custom Utils
from customutils import *
# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# App Configuration
st.set_page_config(page_title="Generate Product Form", layout="wide")
st.title("(5) v1 Gen PIM Template")

# Initialize session state
if 'TIME_DIFF_MS' not in st.session_state:
    st.session_state['TIME_DIFF_MS'] = get_time_difference()
if 'STEP1' not in st.session_state:
    st.session_state['STEP1'] = True
if 'STEP2' not in st.session_state:
    st.session_state['STEP2'] = False
if 'STEP3' not in st.session_state:
    st.session_state['STEP3'] = False

if 'HTML_LOG' not in st.session_state:
    st.session_state['HTML_LOG'] = []

if 'mainDict' not in st.session_state:
    st.session_state['mainDict'] = {}
# if 'file_dict' not in st.session_state:
#     st.session_state['file_dict'] = {}
if 'dfPROD' not in st.session_state:
    st.session_state['dfPROD'] = pd.DataFrame()
if 'dfTPL' not in st.session_state:
    st.session_state['dfTPL'] = pd.DataFrame()

# def addToLog(text: str, indent=0):
#     # generate current timestamp
#     timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     st.markdown(
#         f'<div>'
#         f'  <span>[{timestamp}]</span>'
#         f'  <span style="margin-left: {indent}rem;">{text}</span>'
#         f'</div>',
#         unsafe_allow_html=True)

def addToLog(text: str, indent=0):
    # generate current timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = (
        f'<div>'
        f'  <span>[{timestamp}]</span>'
        f'  <span style="margin-left: {indent}rem;">{text}</span>'
        f'</div>')
    st.markdown(html, unsafe_allow_html=True)
    st.session_state['HTML_LOG'].append(html)

#######################
# USER UPLOAD & PARSE #
#######################
if st.session_state['STEP1']==True:
    st.header('Setup & Upload PDF Files')

    col1, col2, col3 = st.columns(3)
    # PERP COUNTRY SELECTION
    with col1:
        inputBusinessLine = st.radio("Business Line", ["FBI", "PCI", "PHI", "SCI"], horizontal=True)  
    # PREP BUSINESS LINE SELECTION
    with col2:
        inputWebSearch = st.radio("Web Search", ["False", "True"], horizontal=True)      
    # PREP COMPANY CODE INPUT
    with col3:
        st.write('HAHA')
    # FILE UPLOADER    
    uploaded_files = st.file_uploader("Upload your PIM TDS file", accept_multiple_files=True, type=["pdf"])

    if uploaded_files and st.button("Process"):
        st.header('Logs')
        def convert_streamlit_files(uploaded_files):
            objs = []
            for uf in uploaded_files or []:
                content = uf.getvalue()
                # create a dummy object with attributes
                fobj = types.SimpleNamespace(
                    filename=uf.name,
                    file=io.BytesIO(content),
                    size=len(content),
                    headers={
                        "content-disposition": f'form-data; name="inputListDocumentation"; filename="{uf.name}"',
                        "content-type": uf.type or "application/pdf",
                    },
                    _max_mem_size=1024 * 1024,
                )
                objs.append(fobj)
            return objs
        inputListDocumentation = convert_streamlit_files(uploaded_files)        
        # SAVE UPLOADED FIELS TEMPORARILY
        stg_lsTempFile = v1_saveUploadFilesTemporarly(inputListDocumentation)
        # BUSINESS LINE
        if inputBusinessLine == 'FBI': stg_businessLineStr = "Food & Beverage"
        elif inputBusinessLine == 'PCI': stg_businessLineStr = "Personal Care"
        elif inputBusinessLine == 'PHI': stg_businessLineStr = "Pharma & Healthcare"
        elif inputBusinessLine == 'SCI': stg_businessLineStr = "Specialty Chemicals"
        # INIT DICT
        mainDict = {
            #'inputProductName': inputProductName,
            'inputBusinessLine': inputBusinessLine,
            'inputListDocumentation': inputListDocumentation,
            #'inputSecret': inputSecret,
            'inputWebSearch': inputWebSearch,
            #'inputParallel': inputParallel,
            'stg_businessLineStr': stg_businessLineStr,
            'stg_lsTempFile': stg_lsTempFile}
        # LOOP EACH FILE
        addToLog("⏳ <strong>STEP1: PROCESSING UPLOAD FILES...</strong>", 0)
        dictfiles = {}
        for file in stg_lsTempFile:    
            filename = file['filename']
            addToLog(f"⏳ <strong>{filename}</strong> parsing text", 2)
            file = [file]
            stg_lsParsedText = v1_parsePDF(file)
            stg_parsedText = "\n\n".join(stg_lsParsedText)
            addToLog(f"⏳ <strong>{filename}</strong> convert to b64", 2)
            stg_lsBase64 = v1_readPDFToBase64(file)
            dictfiles[filename] = {'stg_lsParsedText':stg_lsParsedText,
                                   'stg_parsedText':stg_parsedText,
                                   'stg_lsBase64':stg_lsBase64}
        # SEARCH PRODUCT NAME AND SUPPLIER FROM DOC
        addToLog("⏳ <strong>STEP2: GET PRODUCT NAME AND SUPPLIER...</strong>", 0)
        for filename in dictfiles.keys():
            file = dictfiles[filename]
            body = PIM_buildBodyGetProductNameAndSupplierFromTextAndImage(file['stg_parsedText'], file['stg_lsBase64'])
            # CALL API - USING AZURE AI FOUNDARY
            url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
            headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
            api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
            #
            dictfiles[filename]

            
            st.json(response)
            st.json(rescontent)



            # while True:
            #     try:
            #         ### CALL API - USING AZURE AI FOUNDARY
            #         url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
            #         response = requests.post(url,                                    
            #                                 headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
            #                                 data=json.dumps(body),
            #                                 verify=False)  
            #         # RESULT


            #         if response.status_code == 200:
            #             rescontent = response.json()['choices'][0]['message']['content'] 
            #             dictfiles[filename]['stg_responseProdSupp'] = rescontent
            #             addToLog(f"✅ Get Products - Found {len(rescontent)} product(s)", 2)                
            #             for product in rescontent:
            #                 addToLog(f"✅ Get Products - Found: <strong>{product['PRODUCT_NAME']}</strong>, Supplier: <strong>{product['SUPPLIER_NAME']}</strong>", 2)
            #             break
            #         elif response.status_code in [499,500,503]: 
            #             addToLog(f"🔄 Get Products - Service Unavailable - Error: (HTTP {response.status_code}) - Retrying...", 2)
            #             continue
            #         elif response.status_code == 400:
            #             addToLog(f"❌ Get Products - Error: (HTTP 400) - Probably File is too big or too may pages", 2)
            #             st.json(response)
            #             break
            #         else:
            #             addToLog(f"❌ Get Products - Error: (HTTP {response.status_code})", 2)
            #             st.json(response)
            #             break
            #     except Exception as e:
            #         addToLog(f"❌ Get Products - Error: {str(e)}", 2)
            #         st.json(response)
            #         break



        #                     #############################################
        #                     # SEARCH PRODUCT NAME AND SUPPLIER FROM PDF #
        #                     #############################################
        #                     body = PIM_buildBodyGetProductNameAndSupplierFromTextAndImage(parsed_text, ls_base64) 
        #                     file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['body'] = body

        #                     ### CALL API - USING TUNNEL
        #                     # response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
        #                     #                         json=body, 
        #                     #                         params={"apikey": os.getenv('OPENAI_API_KEY')},
        #                     #                         verify=False)

        #                     ### CALL API - USING AZURE AI FOUNDARY
        #                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
        #                     response = requests.post(url,                                    
        #                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
        #                                             data=json.dumps(body),
        #                                             verify=False)  
        #                     file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['response'] = response.json()          
        #                     # RESULT
        #                     if response.status_code == 200:
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = '✅ Success'
        #                         rescontent = response.json()['choices'][0]['message']['content']      
        #                         rescontent = json.loads(rescontent)['products_and_suppliers']
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['result'] = rescontent
        #                         addToLog(f"✅ Get Products - Found {len(rescontent)} product(s)", 2)
        #                         for product in rescontent:
        #                             addToLog(f"✅ Get Products - Found: <strong>{product['PRODUCT_NAME']}</strong>, Supplier: <strong>{product['SUPPLIER_NAME']}</strong>", 2)
        #                         break
        #                     elif response.status_code in [499,500,503]: 
        #                         addToLog(f"🔄 Get Products - Service Unavailable - Error: (HTTP {response.status_code}) - Retrying...", 2)
        #                         continue
        #                     elif response.status_code == 400:
        #                         addToLog(f"❌ Get Products - Error: (HTTP 400) - Probably File is too big or too may pages", 2)
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: (HTTP {response.status_code})'
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['error'] = response.json()    
        #                         break
        #                     else:
        #                         addToLog(f"❌ Get Products - Error: (HTTP {response.status_code})", 2)
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: (HTTP {response.status_code})'
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['error'] = response.json()
        #                         break
        #                 except Exception as e:
        #                     addToLog(f"❌ Get Products - Error: {str(e)}", 2)
        #                     file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: {str(e)}'
        #                     break



        #st.json(mainDict)
        #st.json(dictfiles)


            # ### SAVE TO INPUT DICT
            # st.session_state['input_dict'] = {
            #     'country': selected_country,
            #     'business_line': business_line,
            #     'company_code': company_code}
            # ### UPLOAD TO TEMP PATH
            # addToLog("### ⏳ <strong>STEP1: PROCESSING UPLOAD FILES...</strong> ###", 0)
            # file_dict = {}
            # for uploaded_file in uploaded_files:
            #     suffix = os.path.splitext(uploaded_file.name)[1]
            #     with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            #         tmp_file.write(uploaded_file.read())
            #         file_dict[uploaded_file.name] = {
            #             'serverPath': tmp_file.name,
            #             'status': 'Uploaded'}
            # st.session_state['file_dict'] = file_dict            
        #     ### PARSE FILES
        #     file_dict = st.session_state['file_dict']
        #     for filename, fileinfo in file_dict.items():
        #         addToLog(f"⏳ <strong>{filename}</strong>", 0)
        #         ####################
        #         # S1_PARSE_TO_TEXT #
        #         ####################
        #         file_dict[filename]['S1_PARSE'] = {}
        #         try:
        #             ### USING LLAMA PARSE
        #             # addToLog(f"⏳ Parse PDF - Parsing using LLaMA Parse...", 2)
        #             # with open(fileinfo['serverPath'], 'rb') as f:
        #             #     mime = 'application/pdf' if filename.endswith('.pdf') else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        #             #     files = [('files', (filename, f, mime))]
        #             #     data = {"apikey": os.getenv('LLAMA_CLOUD_API_KEY')}
        #             #     response = requests.post(
        #             #         "https://ancient-almeda-personal-personal-22e19704.koyeb.app/llama_parse_batch",
        #             #         data=data,
        #             #         files=files,
        #             #         verify=False)
        #             #     if response.status_code == 200:
        #             #         addToLog(f"✅ Parse PDF - Success", 2)     
        #             #         file_dict[filename]['S1_PARSE']['status'] = '✅ Success'
        #             #         file_dict[filename]['S1_PARSE']['result'] = response.json()['results']
        #             #     else:
        #             #         addToLog(f"❌ Parse PDF - Error: (HTTP {response.status_code})", 2)
        #             #         file_dict[filename]['S1_PARSE']['status'] = f'❌ Error: (HTTP {response.status_code})'

        #             ### USING AZURE DOCUMENT INTELLIGENCE
        #             addToLog(f"⏳ Parse PDF - Parsing using Azure Document Intelligence...", 2)
        #             markdownText = azureDocumentIntelligenceParsePDF(fileinfo['serverPath'], os.getenv('AZURE_DOCUMENT_INTELLIGENCE_API_KEY'))
        #             file_dict[filename]['S1_PARSE']['status'] = '✅ Success'
        #             file_dict[filename]['S1_PARSE']['result'] = [markdownText]
        #             addToLog(f"✅ Parse PDF - Success", 2)                    

        #         except Exception as e:
        #             addToLog(f"❌ Parse PDF - Error: {str(e)}", 2)
        #             file_dict[filename]['S1_PARSE']['status'] = f'❌ Error: {str(e)}'
        #             file_dict[filename]['S1_PARSE']['result'] = ['']

        #         #########################
        #         # S2_READ_PDF_TO_BASE64 #
        #         #########################
        #         file_dict[filename]['S2_READ_PDF_TO_BASE64'] = {}
        #         try:
        #             doc = fitz.open(fileinfo['serverPath'])          
        #             base64_pages = []
        #             for page_number in range(len(doc)):
        #                 page = doc.load_page(page_number)
        #                 pix = page.get_pixmap(dpi=150)
        #                 img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        #                 buffered = io.BytesIO()
        #                 img.save(buffered, format="PNG")
        #                 img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        #                 base64_pages.append(img_base64)
        #             file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] = '✅ Success'
        #             file_dict[filename]['S2_READ_PDF_TO_BASE64']['pages'] = base64_pages
        #             addToLog(f"✅ Generate b64 Image - Success", 2)
        #         except Exception as e:
        #             addToLog(f"❌ Generate b64 Image - Error: {str(e)}", 2)
        #             file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] = f'❌ Error: {str(e)}'
        #             file_dict[filename]['S2_READ_PDF_TO_BASE64']['pages'] = []

        #         #############################
        #         # S3_GET_PROD_NAME_AND_SUPP #
        #         #############################
        #         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP'] = {}
        #         # if file_dict[filename]['S1_PARSE']['status'] == '✅ Success' and file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] == '✅ Success':
        #         if file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] == '✅ Success':  
        #             # SHOW ERROR
        #             if 'Error' in file_dict[filename]['S1_PARSE']['status']:    
        #                 if 'The input image is too large' in file_dict[filename]['S1_PARSE']['status']:
        #                     # USE WARNING EMOJI
        #                     addToLog(f"⚠️ Get Products - Warning: File size is too large, Only Image will be used", 2)
        #                 else:
        #                     addToLog(f"⚠️ Get Products - Warning: Only Image will be used", 2)
        #             # PROCESS             
        #             addToLog(f"⏳ Get Products - Using Azure AI services gpt4.1-mini...", 2)       
        #             while True:
        #                 try:
        #                     parsed_text = str(file_dict[filename]['S1_PARSE']['result'][0])
        #                     ls_base64 = file_dict[filename]['S2_READ_PDF_TO_BASE64']['pages']
        #                     #############################################
        #                     # SEARCH PRODUCT NAME AND SUPPLIER FROM PDF #
        #                     #############################################
        #                     body = PIM_buildBodyGetProductNameAndSupplierFromTextAndImage(parsed_text, ls_base64) 
        #                     file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['body'] = body

        #                     ### CALL API - USING TUNNEL
        #                     # response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
        #                     #                         json=body, 
        #                     #                         params={"apikey": os.getenv('OPENAI_API_KEY')},
        #                     #                         verify=False)

        #                     ### CALL API - USING AZURE AI FOUNDARY
        #                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
        #                     response = requests.post(url,                                    
        #                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
        #                                             data=json.dumps(body),
        #                                             verify=False)  
        #                     file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['response'] = response.json()          
        #                     # RESULT
        #                     if response.status_code == 200:
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = '✅ Success'
        #                         rescontent = response.json()['choices'][0]['message']['content']      
        #                         rescontent = json.loads(rescontent)['products_and_suppliers']
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['result'] = rescontent
        #                         addToLog(f"✅ Get Products - Found {len(rescontent)} product(s)", 2)
        #                         for product in rescontent:
        #                             addToLog(f"✅ Get Products - Found: <strong>{product['PRODUCT_NAME']}</strong>, Supplier: <strong>{product['SUPPLIER_NAME']}</strong>", 2)
        #                         break
        #                     elif response.status_code in [499,500,503]: 
        #                         addToLog(f"🔄 Get Products - Service Unavailable - Error: (HTTP {response.status_code}) - Retrying...", 2)
        #                         continue
        #                     elif response.status_code == 400:
        #                         addToLog(f"❌ Get Products - Error: (HTTP 400) - Probably File is too big or too may pages", 2)
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: (HTTP {response.status_code})'
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['error'] = response.json()    
        #                         break
        #                     else:
        #                         addToLog(f"❌ Get Products - Error: (HTTP {response.status_code})", 2)
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: (HTTP {response.status_code})'
        #                         file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['error'] = response.json()
        #                         break
        #                 except Exception as e:
        #                     addToLog(f"❌ Get Products - Error: {str(e)}", 2)
        #                     file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: {str(e)}'
        #                     break
        #         else:
        #             addToLog(f"❌ Error: No data avaliable to read", 2)
        #             file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: Some Problem with PDF File'

                    

        #     # BUILD SUMMARY DATAFRAME BY PRODUCT
        #     addToLog("⏳ Building Summary Table...", 0)
        #     lsdf = []
        #     for filename in file_dict.keys():
        #         if file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] == '✅ Success':
        #             for product in file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['result']:
        #                 lsdf.append(
        #                     pd.DataFrame({'FILE_NAME':[filename],
        #                     # 'COUNTRY': [st.session_state['input_dict']['country']],
        #                     # 'BUSINESS_LINE': [st.session_state['input_dict']['business_line']],
        #                     # 'COMPANY_CODE': [st.session_state['input_dict']['company_code']],
        #                     'PRODUCT_NAME': [product['PRODUCT_NAME']],
        #                     'SUPPLIER_NAME': [product['SUPPLIER_NAME']]}))
        #         else:
        #             lsdf.append(
        #                 pd.DataFrame({'FILE_NAME':[filename],
        #                 # 'COUNTRY': [st.session_state['input_dict']['country']],
        #                 # 'BUSINESS_LINE': [st.session_state['input_dict']['business_line']],
        #                 # 'COMPANY_CODE': [st.session_state['input_dict']['company_code']],                        
        #                 'PRODUCT_NAME': [file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status']],
        #                 'SUPPLIER_NAME': [file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status']]}))
        #     dfPROD = pd.concat(lsdf, ignore_index=True)
        #     # PROCEED
        #     st.session_state['file_dict'] = file_dict
        #     st.session_state['dfPROD'] = dfPROD.copy()
        #     # st.session_state['STEP'] = 'GET_FIELDS'
        #     st.session_state['STEP1'] = False
        #     st.session_state['STEP2'] = True
        #     st.rerun()

# ##############
# # GET FIELDS #
# ############## 
# if st.session_state['STEP2']==True:
#     # PRINT LOG
#     st.header('Logs')
#     for html_log in st.session_state['HTML_LOG']:
#         st.markdown(html_log, unsafe_allow_html=True)
#     # HEADER
#     st.header('List Of Products Found in Each File')
#     # LOAD STATE
#     file_dict = st.session_state['file_dict']
#     input_dict = st.session_state['input_dict']
#     dfPROD = st.session_state['dfPROD'].copy()
#     # SHOW INPUT DICT
#     st.write(f"Country: **{input_dict['country']}**")
#     st.write(f"Business Line: **{input_dict['business_line']}**")
#     st.write(f"Company Code: **{input_dict['company_code']}**")
#     # DATAFRAME
#     st.dataframe(dfPROD.astype(str))

#     # DEBUG
#     # with st.expander("input_dict", expanded=False):
#     #     st.json(st.session_state['input_dict'])
#     # with st.expander("file_dict", expanded=False):
#     #     st.json(st.session_state['file_dict'])
#     # with st.expander("dfPROD", expanded=False):
#     #     st.dataframe(st.session_state['dfPROD'].astype(str))

#     if st.button("Get Structured Data From PDF"):
#         st.header('Logs')
#         addToLog("### ⏳ <strong>STEP2: GET STRUCTURED FIELDS...</strong> ###", 0)
#         dfPROD['ERRORS'] = 0
#         dfPROD['INDUSTRY_CLUSTER'] = ''     
#         dfPROD['INDUSTRY_CLUSTER_REASON'] = ''   
#         dfPROD['COMPOSITIONS_WEB_SEARCH_RESPONSE'] = ''  
#         dfPROD['COMPOSITIONS_WEB_SEARCH'] = ''  
#         dfPROD['APPLICATIONS_WEB_SEARCH_RESPONSE'] = ''
#         dfPROD['APPLICATIONS_WEB_SEARCH'] = ''
#         dfPROD['FUNCTIONS_WEB_SEARCH_RESPONSE'] = ''
#         dfPROD['FUNCTIONS_WEB_SEARCH'] = ''        
#         dfPROD['COMBINED_WEB_SEARCH'] = '' 
#         dfPROD['THIS_PRODUCT_ONLY'] = ''
#         dfPROD['COMPOSITIONS_RESPONSE'] = ''
#         dfPROD['COMPOSITIONS'] = ''
#         dfPROD['APPLICATIONS_RESPONSE'] = ''
#         dfPROD['APPLICATIONS'] = ''
#         dfPROD['FUNCTIONS_RESPONSE'] = ''
#         dfPROD['FUNCTIONS'] = ''
#         dfPROD['CAS_FROM_DOC'] = ''
#         # dfPROD['CAS_WEB_SEARCH'] = ''           # NOT NEEDED NOW
#         # dfPROD['CAS_FROM_WEB'] = ''             # NOT NEEDED NOW
#         # dfPROD['PHYSICAL_FORM_WEB_SEARCH'] = '' # NOT NEEDED NOWWW
#         dfPROD['PHYSICAL_FORM'] = ''
#         dfPROD['PRODUCT_DESCRIPTION'] = ''
#         dfPROD['RECOMMENDED_DOSAGE_RESPONSE'] = ''
#         dfPROD['RECOMMENDED_DOSAGE'] = ''
#         dfPROD['REGULATORY_REQUIREMENTS'] = '(MANUAL_INPUT)'
#         dfPROD['CERTIFICATIONS'] = ''
#         dfPROD['CLAIMS_BODY'] = ''
#         dfPROD['CLAIMS_RESPONSE_CODE'] = ''
#         dfPROD['CLAIMS_RESPONSE'] = ''
#         dfPROD['CLAIMS'] = ''
#         dfPROD['PDP_VDO'] = '(MANUAL_INPUT)'
#         dfPROD['LIGHT_VERSION'] = '(MANUAL_INPUT)'
#         dfPROD['RECOMMENDED_HEALTH_BENEFITS'] = ''
#         dfPROD['SUSTAINABLE_DOC'] = ''

#         # LOOP EACH ROW
#         for i in range(len(dfPROD)):
#             # GET ROW DATA
#             file_name = dfPROD.iloc[i]['FILE_NAME']
#             business_line = input_dict['business_line']
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             if business_line == 'FBI': business_line_str = "Food & Beverage"
#             elif business_line == 'PCI': business_line_str = "Personal Care"
#             elif business_line == 'PHI': business_line_str = "Pharma & Healthcare"
#             elif business_line == 'SCI': business_line_str = "Specialty Chemicals"
#             # CHECK IF NOT ERROR
#             if 'Error' in product_name:
#                 addToLog(f"❌ {file_name} Error, will skip...", 0)
#                 continue
#             # PROCESS
#             addToLog(f"⏳ Working on <strong>{product_name}</strong> from <strong>{manufacturer_name}</strong>...", 0)

#             #############################
#             # COMPOSITIONS - WEB SEARCH #
#             #############################
#             # question = f"""
#             #             What are the COMPOSITIONS of [{product_name}] from manufacturer [{manufacturer_name}], like what is it made from? or the raw material used?
#             #             If there is no information available, Just return "No information available on Internet", do not list any composition, ingredient, or raw material.
#             #             If there is information avaliable, list the composition,ingredient, or raw material used in the product.
#             #             Use exact product name [{product_name}] and manufacturer name [{manufacturer_name}] in the search.
#             #             """
#             # body = {"model": "gpt-4o-mini-search-preview",
#             #         'web_search_options': {'search_context_size': 'low'},
#             #         "messages": [{'role': 'user', 
#             #                     'content': question}],
#             #         "max_tokens": 4096*2}
#             # ### CALL API - USING TUNNEL
#             # while True:
#             #     try:
#             #         response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
#             #                                 json=body, 
#             #                                 params={"apikey": os.getenv('OPENAI_API_KEY')},
#             #                                 verify=False)    
#             #         dfPROD['COMPOSITIONS_WEB_SEARCH_RESPONSE'].iat[i] = response.json()                
#             #         if response.status_code == 200:                        
#             #             dfPROD['COMPOSITIONS_WEB_SEARCH'].iat[i] = response.json()['choices'][0]['message']['content']
#             #             addToLog(f"✅ GPT Search Compositions - Search for <strong>Compositions</strong> of <strong>{product_name}</strong> from <strong>{manufacturer_name}</strong> on web", 2)
#             #             break
#             #         elif response.status_code in [499, 500, 503]:
#             #             addToLog(f"🔄 GPT Search Compositions - Error: (HTTP {response.status_code}) - Retrying...", 2)     
#             #             continue
#             #         else:
#             #             addToLog(f"❌ GPT Search Compositions - Error: (HTTP {response.status_code})", 2)
#             #             dfPROD['COMPOSITIONS_WEB_SEARCH_RESPONSE'].iat[i] = response.json()
#             #             dfPROD['COMPOSITIONS_WEB_SEARCH'].iat[i] = response.json()
#             #             dfPROD['ERRORS'].iat[i] += 1
#             #             break
#             #     except Exception as e:
#             #         if 'Unterminated string' in str(e):
#             #             addToLog(f"🔄 GPT Search Compositions - Error: Unterminated string - Retrying...", 2) 
#             #             continue
#             #         elif 'Expecting value' in str(e):
#             #             addToLog(f"🔄 GPT Search Compositions - Error: Expecting value - Retrying...", 2) 
#             #             continue
#             #         else:
#             #             addToLog(f"❌ GPT Search Compositions - Error: {str(e)}", 2)
#             #             dfPROD['COMPOSITIONS_WEB_SEARCH'].iat[i] = str(e)
#             #             dfPROD['ERRORS'].iat[i] += 1
#             #             break

#             ############################
#             # APPLICATION - WEB SEARCH #
#             ############################
#             # question = f"""
#             #             Give me as much information as possible about the APPLICATIONS of [{product_name}] utilization in the [{business_line_str}] industries
#             #             If there is no information available, Just return "No information available on Internet"
#             #             If there is information avaliable, then output data.
#             #             Use exact product name [{product_name}] in the search.
#             #             """            
#             # body = {"model": "gpt-4o-mini-search-preview",
#             #         'web_search_options': {'search_context_size': 'low'},
#             #         "messages": [{'role': 'user', 
#             #                       'content': question}],
#             #         "max_tokens": 4096*2}
#             # ### CALL API - USING TUNNEL
#             # while True:
#             #     try:
#             #         response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
#             #                                 json=body, 
#             #                                 params={"apikey": os.getenv('OPENAI_API_KEY')},
#             #                                 verify=False)
#             #         dfPROD['APPLICATIONS_WEB_SEARCH_RESPONSE'].iat[i] = response.json()               
#             #         if response.status_code == 200:
#             #             dfPROD['APPLICATIONS_WEB_SEARCH'].iat[i] = response.json()['choices'][0]['message']['content']
#             #             addToLog(f"✅ GPT Search Applications - Search for <strong>Applications</strong> of <strong>{product_name}</strong> on web", 2)
#             #             break
#             #         elif response.status_code in [499, 500, 503]:
#             #             addToLog(f"🔄 GPT Search Applications - Error: (HTTP {response.status_code}) - Retrying...", 2) 
#             #             continue
#             #         else:
#             #             addToLog(f"❌ GPT Search Applications - Error: (HTTP {response.status_code})", 2)
#             #             dfPROD['APPLICATIONS_WEB_SEARCH_RESPONSE'].iat[i] = response.json()
#             #             dfPROD['APPLICATIONS_WEB_SEARCH'].iat[i] = response.json()
#             #             dfPROD['ERRORS'].iat[i] += 1
#             #             break
#             #     except Exception as e:
#             #         if 'Unterminated string' in str(e):
#             #             addToLog(f"🔄 GPT Search Applications - Error: Unterminated string - Retrying...", 2) 
#             #             continue
#             #         elif 'Expecting value' in str(e):
#             #             addToLog(f"🔄 GPT Search Applications - Error: Expecting value - Retrying...", 2) 
#             #             continue
#             #         else:
#             #             addToLog(f"❌ GPT Search Applications - Error: {str(e)}", 2)
#             #             dfPROD['APPLICATIONS_WEB_SEARCH'].iat[i] = str(e)
#             #             dfPROD['ERRORS'].iat[i] += 1
#             #             break 

#             ##########################
#             # FUNCTIONS - WEB SEARCH ##
#             ##########################
#             # question = f"""
#             #             Give me as much information as possible about the FUNCTIONS of [{product_name}] utilization in the [{business_line_str}] industries
#             #             If there is no information available, Just return "No information available on Internet"
#             #             If there is information avaliable, then output data.
#             #             Use exact product name [{product_name}] in the search.
#             #             """            
#             # body = {"model": "gpt-4o-mini-search-preview",
#             #         'web_search_options': {'search_context_size': 'low'},
#             #         "messages": [{'role': 'user',
#             #                       'content': question}],
#             #         "max_tokens": 4096*2}
#             # ### CALL API - USING TUNNEL
#             # while True:
#             #     try:
#             #         response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
#             #                                 json=body, 
#             #                                 params={"apikey": os.getenv('OPENAI_API_KEY')},
#             #                                 verify=False)         
#             #         dfPROD['FUNCTIONS_WEB_SEARCH_RESPONSE'].iat[i] = response.json()    
#             #         if response.status_code == 200:
#             #             dfPROD['FUNCTIONS_WEB_SEARCH'].iat[i] = response.json()['choices'][0]['message']['content']
#             #             addToLog(f"✅ GPT Search Functions - Search for <strong>Functions</strong> of <strong>{product_name}</strong> on web", 2)
#             #             break
#             #         elif response.status_code in [499, 500, 503]:
#             #             addToLog(f"🔄 GPT Search Functions - Error: (HTTP {response.status_code}) - Retrying...", 2) 
#             #             continue
#             #         else:
#             #             addToLog(f"❌ GPT Search Functions - Error: (HTTP {response.status_code})", 2)
#             #             dfPROD['FUNCTIONS_WEB_SEARCH_RESPONSE'].iat[i] = response.json()
#             #             dfPROD['FUNCTIONS_WEB_SEARCH'].iat[i] = response.json()
#             #             dfPROD['ERRORS'].iat[i] += 1
#             #             break
#             #     except Exception as e:
#             #         if 'Unterminated string' in str(e):
#             #             addToLog(f"🔄 GPT Search Functions - Error: Unterminated string - Retrying...", 2) 
#             #             continue
#             #         elif 'Expecting value' in str(e):
#             #             addToLog(f"🔄 GPT Search Functions - Error: Expecting value - Retrying...", 2) 
#             #             continue
#             #         else:
#             #             addToLog(f"❌ GPT Search Functions - Error: {str(e)}", 2)
#             #             dfPROD['FUNCTIONS_WEB_SEARCH'].iat[i] = str(e)
#             #             dfPROD['ERRORS'].iat[i] += 1
#             #             break     

#             ######################
#             # COMBINE WEB SEARCH #
#             ######################
#             searched_text = ''
#             # searched_text += '### COMPOSITIONS WEB SEARCH RESULTS ###\n'
#             # searched_text += dfPROD['COMPOSITIONS_WEB_SEARCH'].astype(str).iat[i] + '\n\n\n'
#             # searched_text += '### APPLICATIONS WEB SEARCH RESULTS ###\n'
#             # searched_text += dfPROD['APPLICATIONS_WEB_SEARCH'].astype(str).iat[i] + '\n\n\n'
#             # searched_text += '### FUNCTIONS WEB SEARCH RESULTS ###\n'
#             # searched_text += dfPROD['FUNCTIONS_WEB_SEARCH'].astype(str).iat[i] + '\n\n\n'
#             dfPROD['COMBINED_WEB_SEARCH'].iat[i] = searched_text

#             #####################
#             # THIS PRODUCT ONLY #
#             #####################
#             parsed_text = str(file_dict[file_name]['S1_PARSE']['result'][0])
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             searched_text = ''
#             body = PIM_buildBodyGetProductInfo(parsed_text, product_name, manufacturer_name, ls_base64, searched_text)
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     if response.status_code == 200:
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         dfPROD['THIS_PRODUCT_ONLY'].iat[i] = rescontent
#                         addToLog(f"✅ Get This Product Only - Success", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         addToLog(f"🔄 Get This Product Only - Error: (HTTP {response.status_code}) - Retrying...", 2)       
#                         continue
#                     else:
#                         addToLog(f"❌ Get This Product Only - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['THIS_PRODUCT_ONLY'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get This Product Only - Error: {str(e)}", 2)
#                     dfPROD['THIS_PRODUCT_ONLY'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break

#             ####################
#             # INDUSTRY_CLUSTER #
#             ####################
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             business_line = input_dict['business_line']          
#             body = PIM_buildBodySelectIndustryCluster(parsed_text, product_name, manufacturer_name, ls_base64, business_line)
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     if response.status_code == 200:
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         dfPROD['INDUSTRY_CLUSTER'].iat[i] = json.loads(rescontent)['industry_cluster']
#                         dfPROD['INDUSTRY_CLUSTER_REASON'].iat[i] = json.loads(rescontent)['reason']
#                         addToLog(f"✅ Get Industry Cluster - {dfPROD['INDUSTRY_CLUSTER'].iat[i]}", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         addToLog(f"🔄 Get Industry Cluster - Error: (HTTP {response.status_code}) - Retrying...", 2)       
#                         continue
#                     else:
#                         addToLog(f"❌ Get Industry Cluster - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['INDUSTRY_CLUSTER'].iat[i] = response.json()
#                         dfPROD['INDUSTRY_CLUSTER_REASON'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get Industry Cluster - Error: {str(e)}", 2)
#                     dfPROD['INDUSTRY_CLUSTER'].iat[i] = str(e)
#                     dfPROD['INDUSTRY_CLUSTER_REASON'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break

#             ################
#             # COMPOSITIONS #
#             ################
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             business_line = input_dict['business_line']
#             searched_text = ''
#             body = PIM_buildBodySelectComposition(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     dfPROD['COMPOSITIONS_RESPONSE'].iat[i] = response.json()
#                     if response.status_code == 200:
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         rescontent = json.loads(rescontent)
#                         if business_line == 'PCI':
#                             dfPROD['COMPOSITIONS'].iat[i] = [k for k, v in rescontent.items() if v]
#                         else:
#                             dfPROD['COMPOSITIONS'].iat[i] = rescontent['compositions']
#                         addToLog(f"✅ Get Compositions - {dfPROD['COMPOSITIONS'].iat[i]}", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         addToLog(f"🔄 Get Compositions - Error: (HTTP {response.status_code}) - Retrying...", 2) 
#                         continue
#                     else:
#                         addToLog(f"❌ Get Compositions - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['COMPOSITIONS'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get Compositions - Error: {str(e)}", 2)
#                     dfPROD['COMPOSITIONS'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break

#             ###############
#             # APPLICATION #
#             ###############
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             business_line = input_dict['business_line']
#             searched_text = ''
#             body = PIM_buildBodySelectApplication(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     dfPROD['APPLICATIONS_RESPONSE'].iat[i] = response.json()
#                     if response.status_code == 200:
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         rescontent = json.loads(rescontent)
#                         dfPROD['APPLICATIONS'].iat[i] = [k for k, v in rescontent.items() if v]
#                         addToLog(f"✅ Get Applications - {dfPROD['APPLICATIONS'].iat[i]}", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         addToLog(f"🔄 Get Applications - Error: (HTTP {response.status_code}) - Retrying...", 2) 
#                         continue
#                     else:
#                         addToLog(f"❌ Get Applications - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['APPLICATIONS'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get Applications - Error: {str(e)}", 2)
#                     dfPROD['APPLICATIONS'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break

#             #############
#             # FUNCTIONS #
#             #############
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             business_line = input_dict['business_line']
#             searched_text = ''            
#             body = PIM_buildBodySelectFunction(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     dfPROD['FUNCTIONS_RESPONSE'].iat[i] = response.json()
#                     if response.status_code == 200:
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         rescontent = json.loads(rescontent)
#                         dfPROD['FUNCTIONS'].iat[i] = [k for k, v in rescontent.items() if v]
#                         addToLog(f"✅ Get Functions - {dfPROD['FUNCTIONS'].iat[i]}", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         addToLog(f"🔄 Get Functions - Error: (HTTP {response.status_code}) - Retrying...", 2) 
#                         continue
#                     else:
#                         addToLog(f"❌ Get Functions - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['FUNCTIONS'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get Functions - Error: {str(e)}", 2)
#                     dfPROD['FUNCTIONS'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break

#             ##############################
#             # CAS NUMBER - FROM DOCUMENT #
#             ##############################
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             body = PIM_buildBodyFindCASNumber(parsed_text, product_name, manufacturer_name, ls_base64)
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     if response.status_code == 200:
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         dfPROD['CAS_FROM_DOC'].iat[i] = json.loads(rescontent)['cas_number']
#                         addToLog(f"✅ Get CAS from Document - {dfPROD['CAS_FROM_DOC'].iat[i]}", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         addToLog(f"🔄 Get CAS from Document - Error: (HTTP {response.status_code}) - Retrying...", 2) 
#                         continue
#                     else:
#                         addToLog(f"❌ Get CAS from Document - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['CAS_FROM_DOC'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get CAS from Document - Error: {str(e)}", 2)
#                     dfPROD['CAS_FROM_DOC'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break  

#             #################
#             # PHYSICAL_FORM #
#             #################
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             business_line = input_dict['business_line']
#             searched_text = ''
#             body = PIM_buildBodyFindPhysicalForm(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     if response.status_code == 200:
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         dfPROD['PHYSICAL_FORM'].iat[i] = json.loads(rescontent)['physical_form']
#                         addToLog(f"✅ Get Physical Form - {dfPROD['PHYSICAL_FORM'].iat[i]}", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         addToLog(f"🔄 Get Physical Form - Error: (HTTP {response.status_code}) - Retrying...", 2) 
#                         continue
#                     else:
#                         addToLog(f"❌ Get Physical Form - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['PHYSICAL_FORM'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get Physical Form - Error: {str(e)}", 2)
#                     dfPROD['PHYSICAL_FORM'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break

#             #######################
#             # PRODUCT_DESCRIPTION #
#             #######################
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             searched_text = ''
#             body = PIM_buildBodyGetProductDescription(parsed_text, product_name, manufacturer_name, ls_base64, searched_text)
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     if response.status_code == 200:
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         dfPROD['PRODUCT_DESCRIPTION'].iat[i] = json.loads(rescontent)['product_description']
#                         addToLog(f"✅ Get Product Description - {dfPROD['PRODUCT_DESCRIPTION'].iat[i]}", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         addToLog(f"🔄 Get Product Description - Error: (HTTP {response.status_code}) - Retrying...", 2) 
#                         continue
#                     else:
#                         addToLog(f"❌ Get Product Description - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['PRODUCT_DESCRIPTION'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get Product Description - Error: {str(e)}", 2)
#                     dfPROD['PRODUCT_DESCRIPTION'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break

#             ######################
#             # RECOMMENDED_DOSAGE #
#             ######################
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             searched_text = ''
#             body = PIM_buildBodyGetRecommendedDosage(parsed_text, product_name, manufacturer_name, ls_base64, searched_text)
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     if response.status_code == 200:                        
#                         dfPROD['RECOMMENDED_DOSAGE_RESPONSE'].iat[i] = response.json()
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         dfPROD['RECOMMENDED_DOSAGE'].iat[i] = json.loads(rescontent)['recommended_dosage']
#                         addToLog(f"✅ Get Recommended Dosage - {dfPROD['RECOMMENDED_DOSAGE'].iat[i]}", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         addToLog(f"🔄 Get Recommended Dosage - Error: (HTTP {response.status_code}) - Retrying...", 2)
#                         continue
#                     else:
#                         addToLog(f"❌ Get Recommended Dosage - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['RECOMMENDED_DOSAGE'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get Recommended Dosage - Error: {str(e)}", 2)
#                     dfPROD['RECOMMENDED_DOSAGE'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break

#             ##################
#             # CERTIFICATIONS #
#             ##################
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             business_line = input_dict['business_line']
#             searched_text = ''
#             body = PIM_buildBodySelectCertifications(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text='')
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     if response.status_code == 200:
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         dfPROD['CERTIFICATIONS'].iat[i] = json.loads(rescontent)['certifications']
#                         addToLog(f"✅ Get Certifications - {dfPROD['CERTIFICATIONS'].iat[i]}", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         addToLog(f"🔄 Get Certifications - Error: (HTTP {response.status_code}) - Retrying...", 2)
#                         continue
#                     else:
#                         addToLog(f"❌ Get Certifications - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['CERTIFICATIONS'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get Certifications - Error: {str(e)}", 2)
#                     dfPROD['CERTIFICATIONS'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break

#             ##########
#             # CLAIMS #
#             ##########
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             business_line = input_dict['business_line']
#             searched_text = ''
#             body = PIM_buildBodySelectClaims(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
#             dfPROD['CLAIMS_BODY'].iat[i] = body
#             ### CALL API - USING AZURE AI FOUNDARY
#             while True:
#                 try:
#                     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                     response = requests.post(url,                                    
#                                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                             data=json.dumps(body),
#                                             verify=False)  
#                     dfPROD['CLAIMS_RESPONSE_CODE'].iat[i] = response.status_code
#                     dfPROD['CLAIMS_RESPONSE'].iat[i] = response.json()
#                     if response.status_code == 200:              
#                         rescontent = response.json()['choices'][0]['message']['content']
#                         rescontent = json.loads(rescontent)
#                         dfPROD['CLAIMS'].iat[i] = [k for k, v in rescontent.items() if v]      
#                         addToLog(f"✅ Get Claims - {dfPROD['CLAIMS'].iat[i]}", 2)
#                         break
#                     elif response.status_code in [499, 500, 503]:
#                         dfPROD['CLAIMS_RESPONSE'].iat[i] = response.json()
#                         addToLog(f"🔄 Get Claims - Error: (HTTP {response.status_code}) - Retrying...", 2)
#                         continue
#                     else:
#                         dfPROD['CLAIMS_RESPONSE'].iat[i] = response.json()
#                         addToLog(f"❌ Get Claims - Error: (HTTP {response.status_code})", 2)
#                         dfPROD['CLAIMS'].iat[i] = response.json()
#                         dfPROD['ERRORS'].iat[i] += 1
#                         break
#                 except Exception as e:
#                     addToLog(f"❌ Get Claims - Error: {str(e)}", 2)
#                     dfPROD['CLAIMS'].iat[i] = str(e)
#                     dfPROD['ERRORS'].iat[i] += 1
#                     break 

#             ###############################
#             # RECOMMENDED_HEALTH_BENEFITS #
#             ###############################
#             parsed_text = dfPROD['THIS_PRODUCT_ONLY'].iat[i]
#             product_name = dfPROD.iloc[i]['PRODUCT_NAME']
#             manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
#             ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']
#             searched_text = ''
#             if business_line == 'FBI':
#                 selection_list = ["Dietary Fiber",
#                                   "Food Culture",
#                                   "Fortification/Nutraceutical",
#                                   "Probiotic/Postbiotic",
#                                   "Protein"]
#                 lsFunctionsStr = str(dfPROD['FUNCTIONS'].iat[i])
#                 if any(item in lsFunctionsStr for item in selection_list):
#                     body = PIM_buildBodySelectHealthBenefits(parsed_text, product_name, manufacturer_name, ls_base64, searched_text)
#                     ### CALL API - USING AZURE AI FOUNDARY
#                     while True:
#                         try:
#                             url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
#                             response = requests.post(url,                                    
#                                                     headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
#                                                     data=json.dumps(body),
#                                                     verify=False)  
#                             if response.status_code == 200:
#                                 rescontent = response.json()['choices'][0]['message']['content']
#                                 dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i] = json.loads(rescontent)['rec_health_benefits']
#                                 addToLog(f"✅ Get Health Benefits - {dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i]}", 2)
#                                 break
#                             elif response.status_code in [499, 500, 503]:
#                                 addToLog(f"🔄 Get Health Benefits - Error: (HTTP {response.status_code}) - Retrying...", 2)
#                                 continue
#                             else:
#                                 addToLog(f"❌ Get Health Benefits - Error: (HTTP {response.status_code})", 2)
#                                 dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i] = response.json()
#                                 dfPROD['ERRORS'].iat[i] += 1
#                                 break
#                         except Exception as e:
#                             addToLog(f"❌ Get Health Benefits - Error: {str(e)}", 2)
#                             dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i] = str(e)
#                             dfPROD['ERRORS'].iat[i] += 1
#                             break
#                 else:
#                     addToLog(f"⏭️ Get Health Benefits - Skip - Functions not in list", 2)
#                     dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i] = []
#             else:
#                 addToLog(f"⏭️ Get Health Benefits - Skip - Only do for FBI", 2)
#                 dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i] = []

#             ###################
#             # SUSTAINABLE_DOC #
#             ###################
#             if business_line == 'PCI':                
#                 selection_list = [
#                     "COSMOS Standard",
#                     "Fair Trade / Fair For Life",
#                     "ISCC",
#                     "NATRUE Standard",
#                     "Natural Cosmetic",
#                     "Nordic Swan Ecolabel",
#                     "Organic",
#                     "Sustainable Palm Oil",
#                     "U.S. EPA"]
#                 lsClaimsStr = str(dfPROD['CLAIMS'].iat[i])
#                 if any(item in lsClaimsStr for item in selection_list):
#                     addToLog(f"✅ Get Sustainable Document - {business_line} - Claims in list, Must Input", 2)
#                     dfPROD['SUSTAINABLE_DOC'].iat[i] = '(MUST_INPUT)'                
#                 else:
#                     addToLog(f"⏭️ Get Sustainable Document - {business_line} - Claims not in list, No Need Input", 2)
#                     dfPROD['SUSTAINABLE_DOC'].iat[i] = '(OPTIONAL)'
#             else:
#                 lsClaimsStr = str(dfPROD['CLAIMS'].iat[i])
#                 if lsClaimsStr != '[]':
#                     addToLog(f"✅ Get Sustainable Document - {business_line} - Claims not blank, Must Input", 2)
#                     dfPROD['SUSTAINABLE_DOC'].iat[i] = '(MUST_INPUT)'
#                 else:
#                     addToLog(f"⏭️ Get Sustainable Document - {business_line} - Claims is blank, No Need Input", 2)
#                     dfPROD['SUSTAINABLE_DOC'].iat[i] = '(OPTIONAL)'

#             # SAVE EVERY LOOP
#             st.session_state['dfPROD'] = dfPROD.copy()

#         # # FINISH        
#         st.session_state['STEP2'] = False
#         st.session_state['STEP3'] = True
#         st.rerun()

# ##########
# # EXPORT ##
# ##########
# if st.session_state['STEP3'] == True:
#     # PRINT LOG
#     st.header('Logs')
#     for html_log in st.session_state['HTML_LOG']:
#         st.markdown(html_log, unsafe_allow_html=True)

#     # DEBUG
#     # with st.expander("input_dict", expanded=False):
#     #     st.json(st.session_state['input_dict'])
#     # with st.expander("file_dict", expanded=False):
#     #     st.json(st.session_state['file_dict'])
#     # with st.expander("dfPROD", expanded=False):
#     #     st.dataframe(st.session_state['dfPROD'].astype(str))


#     # EXPORT
#     st.header('FULL DATA')
#     st.dataframe(st.session_state['dfPROD'].astype(str))

#     # EXPORT
#     st.header('TEMPLATE')
#     dfTPL = st.session_state['dfPROD'].copy()
#     dfTPL['COUNTRY'] = st.session_state['input_dict']['country']
#     dfTPL['BUSINESS_LINE'] = st.session_state['input_dict']['business_line']
#     dfTPL['COMPANY_CD'] = st.session_state['input_dict']['company_code']        
#     dfTPL = dfTPL[['COUNTRY','BUSINESS_LINE',
#                     'INDUSTRY_CLUSTER','SUPPLIER_NAME',
#                     'COMPOSITIONS','APPLICATIONS','FUNCTIONS',
#                     'PRODUCT_NAME','CAS_FROM_DOC','PHYSICAL_FORM','PRODUCT_DESCRIPTION',
#                     'RECOMMENDED_DOSAGE','REGULATORY_REQUIREMENTS','CERTIFICATIONS',
#                     'FILE_NAME','COMPANY_CD','CLAIMS','PDP_VDO',
#                     'LIGHT_VERSION','RECOMMENDED_HEALTH_BENEFITS','SUSTAINABLE_DOC']]
#     st.session_state['dfTPL'] = dfTPL.copy()      
#     st.dataframe(dfTPL.astype(str))

#     # DEBUG
#     # with st.expander("input_dict", expanded=False):
#     #     st.json(st.session_state['input_dict'])
#     # with st.expander("file_dict", expanded=False):
#     #     st.json(st.session_state['file_dict'])
#     # with st.expander("dfPROD", expanded=False):
#     #     st.dataframe(st.session_state['dfPROD'].astype(str))

# # # PRINT LOG
# # st.header('Logs')
# # for html_log in st.session_state['HTML_LOG']:
# #     st.markdown(html_log, unsafe_allow_html=True)


