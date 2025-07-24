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
st.title("(2) PIM Form Generation from PDF")

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

if 'input_dict' not in st.session_state:
    st.session_state['input_dict'] = {}
if 'file_dict' not in st.session_state:
    st.session_state['file_dict'] = {}
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
        # countries = [f"{country.name} ({country.alpha_2})" for country in pycountry.countries] 
        countries = [f"{country.name}" for country in pycountry.countries] # 2025-07-23 | Saint: want only country name
        selected_country = st.selectbox("Select Country", sorted(countries))
    # PREP BUSINESS LINE SELECTION
    with col2:
        #business_line = st.selectbox("Business Line", ["FBI", "PCI", "PHI", "SCI"])
        business_line = st.radio(
        "Business Line",
        ["FBI", "PCI", "PHI", "SCI"],
        horizontal=True  # set to False (or omit) if you prefer a vertical list
        )
        
    # PREP COMPANY CODE INPUT
    with col3:
        raw_company_code = st.text_input("Company Code (Max 4 A-Z/0-9)", value="", max_chars=4)
        company_code = raw_company_code.upper()
        st.text_input("Auto-Formatted Code", company_code, disabled=True, max_chars=4)
        if len(company_code) > 4 or not company_code.isalnum():
            st.warning("Company Code must be up to 4 uppercase letters or numbers.")
    # FILE UPLOADER    
    uploaded_files = st.file_uploader("Upload your PIM TDS file", accept_multiple_files=True, type=["pdf"])

    if uploaded_files and st.button("Process"):
        ### VALIDATION
        if not company_code:
            st.error("Company Code cannot be blank.")
        elif len(company_code) != 4:
            st.error("Company Code must be up to 4 letters or numbers.")
        else:
            st.header('Logs')
            ### SAVE TO INPUT DICT
            st.session_state['input_dict'] = {
                'country': selected_country,
                'business_line': business_line,
                'company_code': company_code}
            ### UPLOAD TO TEMP PATH
            addToLog("### ⏳ <strong>STEP1: PROCESSING UPLOAD FILES...</strong> ###", 0)
            file_dict = {}
            for uploaded_file in uploaded_files:
                suffix = os.path.splitext(uploaded_file.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_file.write(uploaded_file.read())
                    file_dict[uploaded_file.name] = {
                        'serverPath': tmp_file.name,
                        'status': 'Uploaded'}
            st.session_state['file_dict'] = file_dict            
            ### PARSE FILES
            file_dict = st.session_state['file_dict']
            for filename, fileinfo in file_dict.items():
                addToLog(f"⏳ <strong>{filename}</strong>", 0)
                ####################
                # S1_PARSE_TO_TEXT #
                ####################
                file_dict[filename]['S1_PARSE'] = {}
                try:
                    ### USING LLAMA PARSE
                    # addToLog(f"⏳ Parse PDF - Parsing using LLaMA Parse...", 2)
                    # with open(fileinfo['serverPath'], 'rb') as f:
                    #     mime = 'application/pdf' if filename.endswith('.pdf') else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    #     files = [('files', (filename, f, mime))]
                    #     data = {"apikey": os.getenv('LLAMA_CLOUD_API_KEY')}
                    #     response = requests.post(
                    #         "https://ancient-almeda-personal-personal-22e19704.koyeb.app/llama_parse_batch",
                    #         data=data,
                    #         files=files,
                    #         verify=False)
                    #     if response.status_code == 200:
                    #         addToLog(f"✅ Parse PDF - Success", 2)     
                    #         file_dict[filename]['S1_PARSE']['status'] = '✅ Success'
                    #         file_dict[filename]['S1_PARSE']['result'] = response.json()['results']
                    #     else:
                    #         addToLog(f"❌ Parse PDF - Error: (HTTP {response.status_code})", 2)
                    #         file_dict[filename]['S1_PARSE']['status'] = f'❌ Error: (HTTP {response.status_code})'

                    ### USING AZURE DOCUMENT INTELLIGENCE
                    addToLog(f"⏳ Parse PDF - Parsing using Azure Document Intelligence...", 2)
                    markdownText = azureDocumentIntelligenceParsePDF(fileinfo['serverPath'], os.getenv('AZURE_DOCUMENT_INTELLIGENCE_API_KEY'))
                    file_dict[filename]['S1_PARSE']['status'] = '✅ Success'
                    file_dict[filename]['S1_PARSE']['result'] = [markdownText]
                    addToLog(f"✅ Parse PDF - Success", 2)                    

                except Exception as e:
                    addToLog(f"❌ Parse PDF - Error: {str(e)}", 2)
                    file_dict[filename]['S1_PARSE']['status'] = f'❌ Error: {str(e)}'
                    file_dict[filename]['S1_PARSE']['result'] = ['']

                #########################
                # S2_READ_PDF_TO_BASE64 #
                #########################
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
                    addToLog(f"✅ Generate b64 Image - Success", 2)
                except Exception as e:
                    addToLog(f"❌ Generate b64 Image - Error: {str(e)}", 2)
                    file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] = f'❌ Error: {str(e)}'
                    file_dict[filename]['S2_READ_PDF_TO_BASE64']['pages'] = []

                #############################
                # S3_GET_PROD_NAME_AND_SUPP #
                #############################
                file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP'] = {}
                # if file_dict[filename]['S1_PARSE']['status'] == '✅ Success' and file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] == '✅ Success':
                if file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] == '✅ Success':  
                    # SHOW ERROR
                    if 'Error' in file_dict[filename]['S1_PARSE']['status']:    
                        if 'The input image is too large' in file_dict[filename]['S1_PARSE']['status']:
                            # USE WARNING EMOJI
                            addToLog(f"⚠️ Get Products - Warning: File size is too large, Only Image will be used", 2)
                        else:
                            addToLog(f"⚠️ Get Products - Warning: Only Image will be used", 2)
                    # PROCESS             
                    addToLog(f"⏳ Get Products - Using Azure AI services gpt4o...", 2)       
                    while True:
                        try:
                            parsed_text = str(file_dict[filename]['S1_PARSE']['result'][0])
                            ls_base64 = file_dict[filename]['S2_READ_PDF_TO_BASE64']['pages']
                            #############################################
                            # SEARCH PRODUCT NAME AND SUPPLIER FROM PDF #
                            #############################################
                            body = PIM_buildBodyGetProductNameAndSupplierFromTextAndImage(parsed_text, ls_base64) 
                            file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['body'] = body

                            ### CALL API - USING TUNNEL
                            # response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
                            #                         json=body, 
                            #                         params={"apikey": os.getenv('OPENAI_API_KEY')},
                            #                         verify=False)

                            ### CALL API - USING AZURE AI FOUNDARY
                            url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                            response = requests.post(url,                                    
                                                    headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                                    data=json.dumps(body),
                                                    verify=False)  
                            file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['response'] = response.json()          
                            # RESULT
                            if response.status_code == 200:
                                file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = '✅ Success'
                                rescontent = response.json()['choices'][0]['message']['content']      
                                rescontent = json.loads(rescontent)['products_and_suppliers']
                                file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['result'] = rescontent
                                addToLog(f"✅ Get Products - Found {len(rescontent)} product(s)", 2)
                                for product in rescontent:
                                    addToLog(f"✅ Get Products - Found: <strong>{product['PRODUCT_NAME']}</strong>, Supplier: <strong>{product['SUPPLIER_NAME']}</strong>", 2)
                                break
                            elif response.status_code in [499,500,503]: 
                                addToLog(f"🔄 Get Products - Service Unavailable - Error: (HTTP {response.status_code}) - Retrying...", 2)
                                continue
                            elif response.status_code == 400:
                                addToLog(f"❌ Get Products - Error: (HTTP 400) - Probably File is too big or too may pages", 2)
                                file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: (HTTP {response.status_code})'
                                file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['error'] = response.json()    
                                break
                            else:
                                addToLog(f"❌ Get Products - Error: (HTTP {response.status_code})", 2)
                                file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: (HTTP {response.status_code})'
                                file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['error'] = response.json()
                                break
                        except Exception as e:
                            addToLog(f"❌ Get Products - Error: {str(e)}", 2)
                            file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: {str(e)}'
                            break
                else:
                    addToLog(f"❌ Error: No data avaliable to read", 2)
                    file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: Some Problem with PDF File'

                    

            # BUILD SUMMARY DATAFRAME BY PRODUCT
            addToLog("⏳ Building Summary Table...", 0)
            lsdf = []
            for filename in file_dict.keys():
                if file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] == '✅ Success':
                    for product in file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['result']:
                        lsdf.append(
                            pd.DataFrame({'FILE_NAME':[filename],
                            # 'COUNTRY': [st.session_state['input_dict']['country']],
                            # 'BUSINESS_LINE': [st.session_state['input_dict']['business_line']],
                            # 'COMPANY_CODE': [st.session_state['input_dict']['company_code']],
                            'PRODUCT_NAME': [product['PRODUCT_NAME']],
                            'SUPPLIER_NAME': [product['SUPPLIER_NAME']]}))
                else:
                    lsdf.append(
                        pd.DataFrame({'FILE_NAME':[filename],
                        # 'COUNTRY': [st.session_state['input_dict']['country']],
                        # 'BUSINESS_LINE': [st.session_state['input_dict']['business_line']],
                        # 'COMPANY_CODE': [st.session_state['input_dict']['company_code']],                        
                        'PRODUCT_NAME': [file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status']],
                        'SUPPLIER_NAME': [file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status']]}))
            dfPROD = pd.concat(lsdf, ignore_index=True)
            # PROCEED
            st.session_state['file_dict'] = file_dict
            st.session_state['dfPROD'] = dfPROD.copy()
            # st.session_state['STEP'] = 'GET_FIELDS'
            st.session_state['STEP1'] = False
            st.session_state['STEP2'] = True
            st.rerun()

##############
# GET FIELDS #
############## 
if st.session_state['STEP2']==True:
    # PRINT LOG
    st.header('Logs')
    for html_log in st.session_state['HTML_LOG']:
        st.markdown(html_log, unsafe_allow_html=True)
    # HEADER
    st.header('List Of Products Found in Each File')
    # LOAD STATE
    file_dict = st.session_state['file_dict']
    input_dict = st.session_state['input_dict']
    dfPROD = st.session_state['dfPROD'].copy()
    # SHOW INPUT DICT
    st.write(f"Country: **{input_dict['country']}**")
    st.write(f"Business Line: **{input_dict['business_line']}**")
    st.write(f"Company Code: **{input_dict['company_code']}**")
    # DATAFRAME
    st.dataframe(dfPROD.astype(str))

    # DEBUG
    with st.expander("input_dict", expanded=False):
        st.json(st.session_state['input_dict'])
    with st.expander("file_dict", expanded=False):
        st.json(st.session_state['file_dict'])
    with st.expander("dfPROD", expanded=False):
        st.dataframe(st.session_state['dfPROD'].astype(str))

    if st.button("Get Structured Data From PDF"):
        st.header('Logs')
        addToLog("### ⏳ <strong>STEP2: GET STRUCTURED FIELDS...</strong> ###", 0)
        dfPROD['INDUSTRY_CLUSTER'] = ''
        dfPROD['COMPOSITIONS_RESPONSE'] = ''
        dfPROD['COMPOSITIONS_WEB_SEARCH'] = ''  
        dfPROD['COMPOSITIONS'] = ''
        dfPROD['APPLICATIONS_WEB_SEARCH'] = ''
        dfPROD['APPLICATIONS'] = ''
        dfPROD['FUNCTIONS_WEB_SEARCH'] = ''
        dfPROD['FUNCTIONS'] = ''
        dfPROD['CAS_FROM_DOC'] = ''
        # dfPROD['CAS_WEB_SEARCH'] = ''           # NOT NEEDED NOW
        # dfPROD['CAS_FROM_WEB'] = ''             # NOT NEEDED NOW
        # dfPROD['PHYSICAL_FORM_WEB_SEARCH'] = '' # NOT NEEDED NOWWW
        dfPROD['PHYSICAL_FORM'] = ''
        dfPROD['PRODUCT_DESCRIPTION'] = ''
        dfPROD['RECOMMENDED_DOSAGE_RESPONSE'] = ''
        dfPROD['RECOMMENDED_DOSAGE'] = ''
        dfPROD['REGULATORY_REQUIREMENTS'] = '(MANUAL_INPUT)'
        dfPROD['CERTIFICATIONS'] = ''
        dfPROD['CLAIMS'] = ''
        dfPROD['PDP_VDO'] = '(MANUAL_INPUT)'
        dfPROD['LIGHT_VERSION'] = '(MANUAL_INPUT)'
        dfPROD['RECOMMENDED_HEALTH_BENEFITS'] = ''
        dfPROD['SUSTAINABLE_DOC'] = ''

        # LOOP EACH ROW
        for i in range(len(dfPROD)):
            # GET ROW DATA
            file_name = dfPROD.iloc[i]['FILE_NAME']
            business_line = input_dict['business_line']
            product_name = dfPROD.iloc[i]['PRODUCT_NAME']
            manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
            if business_line == 'FBI': business_line_str = "Food & Beverage"
            elif business_line == 'PCI': business_line_str = "Personal Care"
            elif business_line == 'PHI': business_line_str = "Pharma & Healthcare"
            elif business_line == 'SCI': business_line_str = "Specialty Chemicals"
            # CHECK IF NOT ERROR
            if 'Error' in product_name:
                addToLog(f"❌ {file_name} Error, will skip...", 0)
                continue
            # PROCESS
            addToLog(f"⏳ Working on <strong>{product_name}</strong> from <strong>{manufacturer_name}</strong>...", 0)
            # GET INPUT DATA FOR LLM
            parsed_text = str(file_dict[file_name]['S1_PARSE']['result'][0])
            ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']

            ####################
            # INDUSTRY_CLUSTER #
            ####################
            body = PIM_buildBodySelectIndustryCluster(parsed_text, product_name, manufacturer_name, ls_base64, business_line)
            ### CALL API - USING AZURE AI FOUNDARY
            while True:
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['INDUSTRY_CLUSTER'].iat[i] = json.loads(rescontent)['industry_cluster']
                        addToLog(f"✅ Get Industry Cluster - {dfPROD['INDUSTRY_CLUSTER'].iat[i]}", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 Get Industry Cluster - Error: (HTTP {response.status_code}) - Retrying...", 2)       
                        continue
                    else:
                        addToLog(f"❌ Get Industry Cluster - Error: (HTTP {response.status_code})", 2)
                        dfPROD['INDUSTRY_CLUSTER'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ Get Industry Cluster - Error: {str(e)}", 2)
                    dfPROD['INDUSTRY_CLUSTER'].iat[i] = str(e)
                    break

            #############################
            # COMPOSITIONS - WEB SEARCH #
            #############################
            question = f"""
                        What are the COMPOSITIONS of [{product_name}] from manufacturer [{manufacturer_name}], like what is it made from? or the raw material used?
                        If there is no information available, Just return "No information available on Internet", do not list any composition, ingredient, or raw material.
                        If there is information avaliable, list the composition,ingredient, or raw material used in the product.
                        """
            body = {"model": "gpt-4o-search-preview",
                    'web_search_options': {'search_context_size': 'high'},
                    "messages": [{'role': 'user', 
                                'content': question}],
                    "max_tokens": 4096}
            ### CALL API - USING TUNNEL
            while True:
                try:
                    response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
                                            json=body, 
                                            params={"apikey": os.getenv('OPENAI_API_KEY')},
                                            verify=False)                    
                    if response.status_code == 200:
                        rescontent = response.json()
                        dfPROD['COMPOSITIONS_WEB_SEARCH'].iat[i] = rescontent['choices'][0]['message']['content']
                        addToLog(f"✅ GPT Search Compositions - Search for <strong>Compositions</strong> of <strong>{product_name}</strong> from <strong>{manufacturer_name}</strong> on web", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 GPT Search Compositions - Error: (HTTP {response.status_code}) - Retrying...", 2)     
                        continue
                    else:
                        addToLog(f"❌ GPT Search Compositions - Error: (HTTP {response.status_code})", 2)
                        dfPROD['COMPOSITIONS_WEB_SEARCH'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ GPT Search Compositions - Error: {str(e)}", 2)
                    dfPROD['COMPOSITIONS_WEB_SEARCH'].iat[i] = str(e)
                    break

            ################
            # COMPOSITIONS #
            ################
            searched_text = dfPROD['COMPOSITIONS_WEB_SEARCH'].iat[i]
            body = PIM_buildBodySelectComposition(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
            ### CALL API - USING AZURE AI FOUNDARY
            while True:
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:
                        dfPROD['COMPOSITIONS_RESPONSE'].iat[i] = response.json()
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['COMPOSITIONS'].iat[i] = json.loads(rescontent)['compositions']
                        addToLog(f"✅ Get Compositions - {dfPROD['COMPOSITIONS'].iat[i]}", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 Get Compositions - Error: (HTTP {response.status_code}) - Retrying...", 2) 
                        continue
                    else:
                        addToLog(f"❌ Get Compositions - Error: (HTTP {response.status_code})", 2)
                        dfPROD['COMPOSITIONS'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ Get Compositions - Error: {str(e)}", 2)
                    dfPROD['COMPOSITIONS'].iat[i] = str(e)
                    break

            ############################
            # APPLICATION - WEB SEARCH #
            ############################
            question = f"Give me as much information as possible about the APPLICATIONS of [{product_name}] utilization in the [{business_line_str}] industries"
            body = {"model": "gpt-4o-search-preview",
                    'web_search_options': {'search_context_size': 'high'},
                    "messages": [{'role': 'user', 
                                  'content': question}],
                    "max_tokens": 4096}
            ### CALL API - USING TUNNEL
            while True:
                try:
                    response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
                                            json=body, 
                                            params={"apikey": os.getenv('OPENAI_API_KEY')},
                                            verify=False)                    
                    if response.status_code == 200:
                        rescontent = response.json()
                        dfPROD['APPLICATIONS_WEB_SEARCH'].iat[i] = rescontent['choices'][0]['message']['content']
                        addToLog(f"✅ GPT Search Applications - Search for <strong>Applications</strong> of <strong>{product_name}</strong> on web", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 GPT Search Applications - Error: (HTTP {response.status_code}) - Retrying...", 2) 
                        continue
                    else:
                        addToLog(f"❌ GPT Search Applications - Error: (HTTP {response.status_code})", 2)
                        dfPROD['APPLICATIONS_WEB_SEARCH'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ GPT Search Applications - Error: {str(e)}", 2)
                    dfPROD['APPLICATIONS_WEB_SEARCH'].iat[i] = str(e)
                    break              

            ###############
            # APPLICATION #
            ###############
            searched_text = dfPROD['APPLICATIONS_WEB_SEARCH'].iat[i]
            body = PIM_buildBodySelectApplication(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
            ### CALL API - USING AZURE AI FOUNDARY
            while True:
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['APPLICATIONS'].iat[i] = json.loads(rescontent)['applications']
                        addToLog(f"✅ Get Applications - {dfPROD['APPLICATIONS'].iat[i]}", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 Get Applications - Error: (HTTP {response.status_code}) - Retrying...", 2) 
                        continue
                    else:
                        addToLog(f"❌ Get Applications - Error: (HTTP {response.status_code})", 2)
                        dfPROD['APPLICATIONS'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ Get Applications - Error: {str(e)}", 2)
                    dfPROD['APPLICATIONS'].iat[i] = str(e)
                    break

            ##########################
            # FUNCTIONS - WEB SEARCH #
            ##########################
            question = f"Give me as much information as possible about the FUNCTIONS of [{product_name}] utilization in the [{business_line_str}] industries"
            body = {"model": "gpt-4o-search-preview",
                    'web_search_options': {'search_context_size': 'high'},
                    "messages": [{'role': 'user',
                                  'content': question}],
                    "max_tokens": 4096}
            ### CALL API - USING TUNNEL
            while True:
                try:
                    response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
                                            json=body, 
                                            params={"apikey": os.getenv('OPENAI_API_KEY')},
                                            verify=False)                    
                    if response.status_code == 200:
                        rescontent = response.json()
                        dfPROD['FUNCTIONS_WEB_SEARCH'].iat[i] = rescontent['choices'][0]['message']['content']
                        addToLog(f"✅ GPT Search Functions - Search for <strong>Functions</strong> of <strong>{product_name}</strong> on web", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 GPT Search Functions - Error: (HTTP {response.status_code}) - Retrying...", 2) 
                        continue
                    else:
                        addToLog(f"❌ GPT Search Functions - Error: (HTTP {response.status_code})", 2)
                        dfPROD['FUNCTIONS_WEB_SEARCH'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ GPT Search Functions - Error: {str(e)}", 2)
                    dfPROD['FUNCTIONS_WEB_SEARCH'].iat[i] = str(e)
                    break              

            #############
            # FUNCTIONS #
            #############
            searched_text = dfPROD['FUNCTIONS_WEB_SEARCH'].iat[i]
            body = PIM_buildBodySelectFunction(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
            ### CALL API - USING AZURE AI FOUNDARY
            while True:
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['FUNCTIONS'].iat[i] = json.loads(rescontent)['functions']
                        addToLog(f"✅ Get Functions - {dfPROD['FUNCTIONS'].iat[i]}", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 Get Functions - Error: (HTTP {response.status_code}) - Retrying...", 2) 
                        continue
                    else:
                        addToLog(f"❌ Get Functions - Error: (HTTP {response.status_code})", 2)
                        dfPROD['FUNCTIONS'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ Get Functions - Error: {str(e)}", 2)
                    dfPROD['FUNCTIONS'].iat[i] = str(e)
                    break

            ##############################
            # CAS NUMBER - FROM DOCUMENT #
            ##############################
            body = PIM_buildBodyFindCASNumber(parsed_text, product_name, manufacturer_name, ls_base64)
            ### CALL API - USING AZURE AI FOUNDARY
            while True:
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['CAS_FROM_DOC'].iat[i] = json.loads(rescontent)['cas_number']
                        addToLog(f"✅ Get CAS from Document - {dfPROD['CAS_FROM_DOC'].iat[i]}", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 Get CAS from Document - Error: (HTTP {response.status_code}) - Retrying...", 2) 
                        continue
                    else:
                        addToLog(f"❌ Get CAS from Document - Error: (HTTP {response.status_code})", 2)
                        dfPROD['CAS_FROM_DOC'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ Get CAS from Document - Error: {str(e)}", 2)
                    dfPROD['CAS_FROM_DOC'].iat[i] = str(e)
                    break  

            #################
            # PHYSICAL_FORM #
            #################
            body = PIM_buildBodyFindPhysicalForm(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text='')
            ### CALL API - USING AZURE AI FOUNDARY
            while True:
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['PHYSICAL_FORM'].iat[i] = json.loads(rescontent)['physical_form']
                        addToLog(f"✅ Get Physical Form - {dfPROD['PHYSICAL_FORM'].iat[i]}", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 Get Physical Form - Error: (HTTP {response.status_code}) - Retrying...", 2) 
                        continue
                    else:
                        addToLog(f"❌ Get Physical Form - Error: (HTTP {response.status_code})", 2)
                        dfPROD['PHYSICAL_FORM'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ Get Physical Form - Error: {str(e)}", 2)
                    dfPROD['PHYSICAL_FORM'].iat[i] = str(e)
                    break

            #######################
            # PRODUCT_DESCRIPTION #
            #######################
            body = PIM_buildBodyGetProductDescription(parsed_text, product_name, manufacturer_name, ls_base64, searched_text='')
            ### CALL API - USING AZURE AI FOUNDARY
            while True:
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['PRODUCT_DESCRIPTION'].iat[i] = json.loads(rescontent)['product_description']
                        addToLog(f"✅ Get Product Description - {dfPROD['PRODUCT_DESCRIPTION'].iat[i]}", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 Get Product Description - Error: (HTTP {response.status_code}) - Retrying...", 2) 
                        continue
                    else:
                        addToLog(f"❌ Get Product Description - Error: (HTTP {response.status_code})", 2)
                        dfPROD['PRODUCT_DESCRIPTION'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ Get Product Description - Error: {str(e)}", 2)
                    dfPROD['PRODUCT_DESCRIPTION'].iat[i] = str(e)
                    break

            ######################
            # RECOMMENDED_DOSAGE #
            ######################
            body = PIM_buildBodyGetRecommendedDosage(parsed_text, product_name, manufacturer_name, ls_base64, searched_text='')
            ### CALL API - USING AZURE AI FOUNDARY
            while True:
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:                        
                        dfPROD['RECOMMENDED_DOSAGE_RESPONSE'].iat[i] = response.json()
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['RECOMMENDED_DOSAGE'].iat[i] = json.loads(rescontent)['recommended_dosage']
                        addToLog(f"✅ Get Recommended Dosage - {dfPROD['RECOMMENDED_DOSAGE'].iat[i]}", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 Get Recommended Dosage - Error: (HTTP {response.status_code}) - Retrying...", 2)
                        continue
                    else:
                        addToLog(f"❌ Get Recommended Dosage - Error: (HTTP {response.status_code})", 2)
                        dfPROD['RECOMMENDED_DOSAGE'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ Get Recommended Dosage - Error: {str(e)}", 2)
                    dfPROD['RECOMMENDED_DOSAGE'].iat[i] = str(e)
                    break

            ##################
            # CERTIFICATIONS #
            ##################
            body = PIM_buildBodySelectCertifications(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text='')
            ### CALL API - USING AZURE AI FOUNDARY
            while True:
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['CERTIFICATIONS'].iat[i] = json.loads(rescontent)['certifications']
                        addToLog(f"✅ Get Certifications - {dfPROD['CERTIFICATIONS'].iat[i]}", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 Get Certifications - Error: (HTTP {response.status_code}) - Retrying...", 2)
                        continue
                    else:
                        addToLog(f"❌ Get Certifications - Error: (HTTP {response.status_code})", 2)
                        dfPROD['CERTIFICATIONS'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ Get Certifications - Error: {str(e)}", 2)
                    dfPROD['CERTIFICATIONS'].iat[i] = str(e)
                    break

            ##########
            # CLAIMS #
            ##########
            body = PIM_buildBodySelectClaims(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text='')
            ### CALL API - USING AZURE AI FOUNDARY
            while True:
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['CLAIMS'].iat[i] = json.loads(rescontent)['claims']
                        addToLog(f"✅ Get Claims - {dfPROD['CLAIMS'].iat[i]}", 2)
                        break
                    elif response.status_code in [499, 500, 503]:
                        addToLog(f"🔄 Get Claims - Error: (HTTP {response.status_code}) - Retrying...", 2)
                        continue
                    else:
                        addToLog(f"❌ Get Claims - Error: (HTTP {response.status_code})", 2)
                        dfPROD['CLAIMS'].iat[i] = response.json()
                        break
                except Exception as e:
                    addToLog(f"❌ Get Claims - Error: {str(e)}", 2)
                    dfPROD['CLAIMS'].iat[i] = str(e)
                    break

            ###############################
            # RECOMMENDED_HEALTH_BENEFITS #
            ###############################
            if business_line == 'FBI':
                selection_list = ["Dietary Fiber",
                                  "Food Culture",
                                  "Fortification/Nutraceutical",
                                  "Probiotic/Postbiotic",
                                  "Protein"]
                lsFunctionsStr = str(dfPROD['FUNCTIONS'].iat[i])
                if any(item in lsFunctionsStr for item in selection_list):
                    body = PIM_buildBodySelectHealthBenefits(parsed_text, product_name, manufacturer_name, ls_base64, searched_text='')
                    ### CALL API - USING AZURE AI FOUNDARY
                    while True:
                        try:
                            url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                            response = requests.post(url,                                    
                                                    headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                                    data=json.dumps(body),
                                                    verify=False)  
                            if response.status_code == 200:
                                rescontent = response.json()['choices'][0]['message']['content']
                                dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i] = json.loads(rescontent)['rec_health_benefits']
                                addToLog(f"✅ Get Health Benefits - {dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i]}", 2)
                                break
                            elif response.status_code in [499, 500, 503]:
                                addToLog(f"🔄 Get Health Benefits - Error: (HTTP {response.status_code}) - Retrying...", 2)
                                continue
                            else:
                                addToLog(f"❌ Get Health Benefits - Error: (HTTP {response.status_code})", 2)
                                dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i] = response.json()
                                break
                        except Exception as e:
                            addToLog(f"❌ Get Health Benefits - Error: {str(e)}", 2)
                            dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i] = str(e)
                            break
                else:
                    addToLog(f"⏭️ Get Health Benefits - Skip - Functions not in list", 2)
                    dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i] = []
            else:
                addToLog(f"⏭️ Get Health Benefits - Skip - Only do for FBI", 2)
                dfPROD['RECOMMENDED_HEALTH_BENEFITS'].iat[i] = []

            ###################
            # SUSTAINABLE_DOC #
            ###################
            if business_line == 'PCI':                
                selection_list = [
                    "COSMOS Standard",
                    "Fair Trade / Fair For Life",
                    "ISCC",
                    "NATRUE Standard",
                    "Natural Cosmetic",
                    "Nordic Swan Ecolabel",
                    "Organic",
                    "Sustainable Palm Oil",
                    "U.S. EPA"]
                lsClaimsStr = str(dfPROD['CLAIMS'].iat[i])
                if any(item in lsClaimsStr for item in selection_list):
                    addToLog(f"✅ Get Sustainable Document - {business_line} - Claims in list, Must Input", 2)
                    dfPROD['SUSTAINABLE_DOC'].iat[i] = '(MUST_INPUT)'                
                else:
                    addToLog(f"⏭️ Get Sustainable Document - {business_line} - Claims not in list, No Need Input", 2)
                    dfPROD['SUSTAINABLE_DOC'].iat[i] = '(OPTIONAL)'
            else:
                lsClaimsStr = str(dfPROD['CLAIMS'].iat[i])
                if lsClaimsStr != '[]':
                    addToLog(f"✅ Get Sustainable Document - {business_line} - Claims not blank, Must Input", 2)
                    dfPROD['SUSTAINABLE_DOC'].iat[i] = '(MUST_INPUT)'
                else:
                    addToLog(f"⏭️ Get Sustainable Document - {business_line} - Claims is blank, No Need Input", 2)
                    dfPROD['SUSTAINABLE_DOC'].iat[i] = '(OPTIONAL)'

            # SAVE EVERY LOOP
            st.session_state['dfPROD'] = dfPROD.copy()

        # FINISH        
        st.session_state['STEP2'] = False
        st.session_state['STEP3'] = True
        st.rerun()

##########
# EXPORT #
##########
if st.session_state['STEP3'] == True:
    # PRINT LOG
    st.header('Logs')
    for html_log in st.session_state['HTML_LOG']:
        st.markdown(html_log, unsafe_allow_html=True)

    # # DEBUG
    # with st.expander("input_dict", expanded=False):
    #     st.json(st.session_state['input_dict'])
    # with st.expander("file_dict", expanded=False):
    #     st.json(st.session_state['file_dict'])
    # with st.expander("dfPROD", expanded=False):
    #     st.dataframe(st.session_state['dfPROD'].astype(str))

    # EXPORT
    st.header('FULL DATA')
    st.dataframe(st.session_state['dfPROD'].astype(str))

    # EXPORT
    st.header('TEMPLATE')
    dfTPL = st.session_state['dfPROD'].copy()
    dfTPL['COUNTRY'] = st.session_state['input_dict']['country']
    dfTPL['BUSINESS_LINE'] = st.session_state['input_dict']['business_line']
    dfTPL['COMPANY_CD'] = st.session_state['input_dict']['company_code']        
    dfTPL = dfTPL[['COUNTRY','BUSINESS_LINE',
                    'INDUSTRY_CLUSTER','SUPPLIER_NAME',
                    'COMPOSITIONS','APPLICATIONS','FUNCTIONS',
                    'PRODUCT_NAME','CAS_FROM_DOC','PHYSICAL_FORM','PRODUCT_DESCRIPTION',
                    'RECOMMENDED_DOSAGE','REGULATORY_REQUIREMENTS','CERTIFICATIONS',
                    'FILE_NAME','COMPANY_CD','CLAIMS','PDP_VDO',
                    'LIGHT_VERSION','RECOMMENDED_HEALTH_BENEFITS','SUSTAINABLE_DOC']]
    st.session_state['dfTPL'] = dfTPL.copy()      
    st.dataframe(dfTPL.astype(str))

    # DEBUG
    # with st.expander("input_dict", expanded=False):
    #     st.json(st.session_state['input_dict'])
    # with st.expander("file_dict", expanded=False):
    #     st.json(st.session_state['file_dict'])
    # with st.expander("dfPROD", expanded=False):
    #     st.dataframe(st.session_state['dfPROD'].astype(str))

# # PRINT LOG
# st.header('Logs')
# for html_log in st.session_state['HTML_LOG']:
#     st.markdown(html_log, unsafe_allow_html=True)


