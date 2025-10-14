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
st.title("(3) Gen PIM SFDC API")

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

if 'uip_dict' not in st.session_state:
    st.session_state['uip_dict'] = {}



# if 'input_dict' not in st.session_state:
#     st.session_state['input_dict'] = {}
# if 'file_dict' not in st.session_state:
#     st.session_state['file_dict'] = {}
# if 'dfPROD' not in st.session_state:
#     st.session_state['dfPROD'] = pd.DataFrame()
# if 'dfTPL' not in st.session_state:
#     st.session_state['dfTPL'] = pd.DataFrame()





#######################
# USER UPLOAD & PARSE #
#######################
if st.session_state['STEP1']==True:
    st.header('Setup & Upload PDF Files')

    col1, col2, col3 = st.columns(3)
    # USER INPUT (UIP) - PRODUCT NAME (FREE TEXT), NOT ALLOW BLANK
    with col1:
        uip_product_name = st.text_input("Product Name", value="", max_chars=100)
    # USER INPUT (UIP) - BUSINESS LINE SELECTION
    with col2:
        uip_business_line = st.radio("Business Line", ["FBI", "PCI", "PHI", "SCI"], horizontal=True)        
    # USER INPUT (UIP) - WEB SEARCH (TRUE/FALSE), RADIO BOX
    with col3:
        uip_web_search = st.radio("Allow Web Search", ["False", "True"], horizontal=True)
    # USER INPUT (UIP) - FILE UPLOADER    
    uip_uploaded_files = st.file_uploader("Upload your PIM TDS file", accept_multiple_files=True, type=["pdf"])

    if st.button('Process'):
        if not uip_product_name.strip():
            st.error('Product Name cannot be blank')
        if not uip_uploaded_files:
            st.error('You must upload atleast one PDF')
        else:
            # SAVE TO INPUT DICT
            st.session_state['uip_dict'] = {
                'uip_product_name': uip_product_name,
                'uip_business_line': uip_business_line,
                'uip_web_search': uip_web_search,
                'uip_uploaded_files': uip_uploaded_files}    
            # BUSINESS LINE
            if uip_business_line == 'FBI': st.session_state['uip_dict']['business_line_str'] = "Food & Beverage"
            elif uip_business_line == 'PCI': st.session_state['uip_dict']['business_line_str'] = "Personal Care"
            elif uip_business_line == 'PHI': st.session_state['uip_dict']['business_line_str'] = "Pharma & Healthcare"
            elif uip_business_line == 'SCI': st.session_state['uip_dict']['business_line_str'] = "Specialty Chemicals"
            # STATE
            st.session_state['STEP1'] = False
            st.session_state['STEP2'] = True
            st.rerun()

##################
# PROCESS RECORD #
##################
if st.session_state['STEP2']==True:
    # HEADER
    st.header('Logs')      
    ### UPLOAD TO TEMP PATH
    addToLog("### ⏳ <strong>STEP1: PROCESSING UPLOAD FILES...</strong> ###", 0)
    file_dict = {}
    for uploaded_file in st.session_state['uip_dict']['uip_uploaded_files']:
        suffix = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.read())
            file_dict[uploaded_file.name] = {
                'serverPath': tmp_file.name,
                'status': 'Uploaded'}
    st.session_state['uip_dict']['file_dict'] = file_dict
    ########################################
    # PARSE FILES - LOOP FOR EACH PDF FILE #
    ########################################
    file_dict = st.session_state['uip_dict']['file_dict'].copy()
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
    # SAVE
    st.session_state['uip_dict']['file_dict'] = file_dict.copy()
    # COMBINE TEXT AND BASE64
    combined_ls_text = []
    combined_ls_b64 = []
    for file in file_dict.keys():
        # TEXT
        if file_dict[file]['S1_PARSE']['status'] == '✅ Success':
            txt = file_dict[file]['S1_PARSE']['result'][0]
            txt = f"TEXT_FROM_FILE_NAME:{file} \n\n" + txt
            combined_ls_text.append(txt)
        # B64
        if file_dict[file]['S2_READ_PDF_TO_BASE64']['status'] == '✅ Success':
            ls_b64 = file_dict[file]['S2_READ_PDF_TO_BASE64']['pages']
            combined_ls_b64 = combined_ls_b64 + ls_b64
    st.session_state['uip_dict']['combined_ls_text'] = combined_ls_text
    st.session_state['uip_dict']['combined_text'] = {}
    st.session_state['uip_dict']['combined_text']['text'] = '\n\n'.join(combined_ls_text)
    st.session_state['uip_dict']['combined_ls_b64'] = combined_ls_b64

    ##############
    # GET FIELDS #
    ############## 
    addToLog("### ⏳ <strong>STEP2: GET STRUCTURED FIELDS...</strong> ###", 0)
    # PRE DEFINED FIELDS
    uip_dict = st.session_state['uip_dict']
    uip_dict['any_errors'] = 0
    # manufacturer_or_supplier
    uip_dict['manufacturer_or_supplier'] = {}
    uip_dict['manufacturer_or_supplier']['body'] = {}
    uip_dict['manufacturer_or_supplier']['api_error'] = None
    uip_dict['manufacturer_or_supplier']['response'] = {}
    uip_dict['manufacturer_or_supplier']['rescontent'] = {}
    uip_dict['manufacturer_or_supplier']['answer'] = None
    uip_dict['manufacturer_or_supplier']['reason'] = None
    # compositions_search
    uip_dict['composition_search'] = {}
    uip_dict['composition_search']['body'] = {}
    uip_dict['composition_search']['api_error'] = None
    uip_dict['composition_search']['response'] = {}
    uip_dict['composition_search']['answer'] = ''
    uip_dict['composition_search']['reason'] = None
    # functions_search
    uip_dict['function_search'] = {}
    uip_dict['function_search']['body'] = {}
    uip_dict['function_search']['api_error'] = None
    uip_dict['function_search']['response'] = {}
    uip_dict['function_search']['answer'] = ''
    uip_dict['function_search']['reason'] = None
    # applications_search
    uip_dict['application_search'] = {}
    uip_dict['application_search']['body'] = {}
    uip_dict['application_search']['api_error'] = None
    uip_dict['application_search']['response'] = {}
    uip_dict['application_search']['answer'] = ''
    uip_dict['application_search']['reason'] = None
    # combined_web_search
    uip_dict['combined_web_search'] = {}
    uip_dict['combined_web_search']['text'] = ''
    # this_product_only
    uip_dict['this_product_only'] = {}
    uip_dict['this_product_only']['body'] = {}
    uip_dict['this_product_only']['api_error'] = None
    uip_dict['this_product_only']['response'] = {}
    uip_dict['this_product_only']['rescontent'] = None
    uip_dict['this_product_only']['answer'] = None
    uip_dict['this_product_only']['reason'] = None
    # industry_cluster
    uip_dict['industry_cluster'] = {}
    uip_dict['industry_cluster']['body'] = {}
    uip_dict['industry_cluster']['api_error'] = None
    uip_dict['industry_cluster']['response'] = {}
    uip_dict['industry_cluster']['rescontent'] = None
    uip_dict['industry_cluster']['answer'] = None
    uip_dict['industry_cluster']['reason'] = None
    # compositions
    uip_dict['compositions'] = {}
    uip_dict['compositions']['body'] = {}
    uip_dict['compositions']['api_error'] = None
    uip_dict['compositions']['response'] = {}
    uip_dict['compositions']['rescontent'] = None
    uip_dict['compositions']['answer'] = None
    uip_dict['compositions']['reason'] = None
    # applications
    uip_dict['applications'] = {}
    uip_dict['applications']['body'] = {}
    uip_dict['applications']['api_error'] = None
    uip_dict['applications']['response'] = {}
    uip_dict['applications']['rescontent'] = None
    uip_dict['applications']['answer'] = None
    uip_dict['applications']['reason'] = None
    # functions
    uip_dict['functions'] = {}
    uip_dict['functions']['body'] = {}
    uip_dict['functions']['api_error'] = None
    uip_dict['functions']['response'] = {}
    uip_dict['functions']['rescontent'] = None
    uip_dict['functions']['answer'] = None
    uip_dict['functions']['reason'] = None
    # cas_from_doc
    uip_dict['cas_from_doc'] = {}
    uip_dict['cas_from_doc']['body'] = {}
    uip_dict['cas_from_doc']['api_error'] = None
    uip_dict['cas_from_doc']['response'] = {}
    uip_dict['cas_from_doc']['rescontent'] = None
    uip_dict['cas_from_doc']['answer'] = None
    uip_dict['cas_from_doc']['reason'] = None
    # physical_form
    uip_dict['physical_form'] = {}
    uip_dict['physical_form']['body'] = {}
    uip_dict['physical_form']['api_error'] = None
    uip_dict['physical_form']['response'] = {}
    uip_dict['physical_form']['rescontent'] = None
    uip_dict['physical_form']['answer'] = None
    uip_dict['physical_form']['reason'] = None
    # product_description
    uip_dict['product_description'] = {}
    uip_dict['product_description']['body'] = {}
    uip_dict['product_description']['api_error'] = None
    uip_dict['product_description']['response'] = {}
    uip_dict['product_description']['rescontent'] = None
    uip_dict['product_description']['answer'] = None
    uip_dict['product_description']['reason'] = None
    # recommended_dosage
    uip_dict['recommended_dosage'] = {}
    uip_dict['recommended_dosage']['body'] = {}
    uip_dict['recommended_dosage']['api_error'] = None
    uip_dict['recommended_dosage']['response'] = {}
    uip_dict['recommended_dosage']['rescontent'] = None
    uip_dict['recommended_dosage']['answer'] = None
    uip_dict['recommended_dosage']['reason'] = None
    # certifications
    uip_dict['certifications'] = {}
    uip_dict['certifications']['body'] = {}
    uip_dict['certifications']['api_error'] = None
    uip_dict['certifications']['response'] = {}
    uip_dict['certifications']['rescontent'] = None
    uip_dict['certifications']['answer'] = None
    uip_dict['certifications']['reason'] = None
    # claims
    uip_dict['claims'] = {}
    uip_dict['claims']['body'] = {}
    uip_dict['claims']['api_error'] = None
    uip_dict['claims']['response'] = {}
    uip_dict['claims']['rescontent'] = None
    uip_dict['claims']['answer'] = None
    uip_dict['claims']['reason'] = None
    # rec_health_benefits
    uip_dict['rec_health_benefits'] = {}
    uip_dict['rec_health_benefits']['body'] = {}
    uip_dict['rec_health_benefits']['api_error'] = None
    uip_dict['rec_health_benefits']['response'] = {}
    uip_dict['rec_health_benefits']['rescontent'] = None
    uip_dict['rec_health_benefits']['answer'] = None
    uip_dict['rec_health_benefits']['reason'] = None


    ############################
    # MANUFACTURER OR SUPPLIER #
    ############################
    # PREP BODY
    parsed_text = uip_dict['combined_text']['text']
    product_name = uip_dict['uip_product_name']
    ls_base64 = uip_dict['combined_ls_b64']
    body = PIM_buildBodyGetManufacturerOrSupplier(parsed_text, product_name, ls_base64)  
    uip_dict['manufacturer_or_supplier']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Manufacturer or Supplier', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['manufacturer_or_supplier']['api_error'] = api_error
    uip_dict['manufacturer_or_supplier']['response'] = response
    uip_dict['manufacturer_or_supplier']['rescontent'] = rescontent
    # CALL API - GET ANSWER
    if uip_dict['manufacturer_or_supplier']['api_error'] == 0:
        uip_dict['manufacturer_or_supplier']['answer'] = rescontent['manufacturer_or_supplier']
        uip_dict['manufacturer_or_supplier']['reason'] = rescontent['reason']
    else:
        raise Exception('CANNOT GET MANUFACTURER OR SUPPLIER NAME')
    # # DEBUG
    # with st.expander('manufacturer_or_supplier'):
    #     st.json(uip_dict['manufacturer_or_supplier'])

    ############################
    # COMPOSITION - WEB SEARCH #
    ############################
    if uip_dict['uip_web_search'] == 'True':
        # PREP BODY
        uip_product_name = uip_dict['uip_product_name']
        manufacturer_or_supplier = uip_dict['manufacturer_or_supplier']['answer']
        question = f"""
        What are the COMPOSITIONS of [{uip_product_name}] from manufacturer [{manufacturer_or_supplier}], like what is it made from? or the raw material used?
        If there is no information available, Just return "No information available on Internet", do not list any composition, ingredient, or raw material.
        If there is information avaliable, list the composition,ingredient, or raw material used in the product.
        Use exact product name [{uip_product_name}] and manufacturer name [{manufacturer_or_supplier}] in the search.
        """
        body = {"model": "gpt-4o-mini-search-preview",
                'web_search_options': {'search_context_size': 'low'},
                "messages": [{'role': 'user', 
                            'content': question}],
                "max_tokens": 4096*2}
        uip_dict['composition_search']['body'] = body
        # CALL API - USING TUNNEL
        url = "https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai"
        params = {"apikey": os.getenv('OPENAI_API_KEY')}
        api_error, response, rescontent = customCallAPI(url, body, headers={}, params=params, log_prefix='GPT Search Compositions')
        # CALL API - SAVE RESULT
        uip_dict['composition_search']['api_error'] = api_error
        uip_dict['composition_search']['response'] = response
        uip_dict['composition_search']['answer'] = rescontent
    
    ############################
    # APPLICATION - WEB SEARCH #
    ############################
    if uip_dict['uip_web_search'] == 'True':
        # PREP BODY
        uip_product_name = uip_dict['uip_product_name']
        business_line_str = uip_dict['business_line_str']
        question = f"""
        Give me as much information as possible about the APPLICATIONS of [{uip_product_name}] utilization in the [{business_line_str}] industries
        If there is no information available, Just return "No information available on Internet"
        If there is information avaliable, then output data.
        Use exact product name [{uip_product_name}] in the search.
        """
        body = {"model": "gpt-4o-mini-search-preview",
                'web_search_options': {'search_context_size': 'low'},
                "messages": [{'role': 'user', 
                            'content': question}],
                "max_tokens": 4096*2}
        uip_dict['application_search']['body'] = body
        # CALL API - USING TUNNEL
        url = "https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai"
        params = {"apikey": os.getenv('OPENAI_API_KEY')}
        api_error, response, rescontent = customCallAPI(url, body, headers={}, params=params, log_prefix='GPT Search Applications')
        # CALL API - SAVE RESULT
        uip_dict['application_search']['api_error'] = api_error
        uip_dict['application_search']['response'] = response
        uip_dict['application_search']['answer'] = rescontent

    #########################
    # FUNCTION - WEB SEARCH #
    #########################
    if uip_dict['uip_web_search'] == 'True':
        # PREP BODY
        uip_product_name = uip_dict['uip_product_name']
        business_line_str = uip_dict['business_line_str']
        question = f"""
        Give me as much information as possible about the FUNCTIONS of [{uip_product_name}] utilization in the [{business_line_str}] industries
        If there is no information available, Just return "No information available on Internet"
        If there is information avaliable, then output data.
        Use exact product name [{uip_product_name}] in the search.
        """
        body = {"model": "gpt-4o-mini-search-preview",
                'web_search_options': {'search_context_size': 'low'},
                "messages": [{'role': 'user', 
                            'content': question}],
                "max_tokens": 4096*2}
        uip_dict['function_search']['body'] = body
        # CALL API - USING TUNNEL
        url = "https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai"
        params = {"apikey": os.getenv('OPENAI_API_KEY')}
        api_error, response, rescontent = customCallAPI(url, body, headers={}, params=params, log_prefix='GPT Search Functions')
        # CALL API - SAVE RESULT
        uip_dict['function_search']['api_error'] = api_error
        uip_dict['function_search']['response'] = response
        uip_dict['function_search']['answer'] = rescontent

    ######################
    # COMBINE WEB SEARCH #
    ######################
    if uip_dict['uip_web_search'] == 'True':
        searched_text = ''
        searched_text += '### COMPOSITIONS WEB SEARCH RESULTS ###\n'
        searched_text += uip_dict['composition_search']['answer'] + '\n\n\n'        
        searched_text += '### FUNCTIONS WEB SEARCH RESULTS ###\n'
        searched_text += uip_dict['function_search']['answer'] + '\n\n\n'
        searched_text += '### APPLICATIONS WEB SEARCH RESULTS ###\n'
        searched_text += uip_dict['application_search']['answer'] + '\n\n\n'
        uip_dict['combined_web_search']['text'] = searched_text

    #####################
    # THIS PRODUCT ONLY #
    #####################
    # PREP BODY
    parsed_text = uip_dict['combined_text']['text']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = uip_dict['combined_ls_b64']
    searched_text = uip_dict['combined_web_search']['text']
    body = PIM_buildBodyGetProductInfo(parsed_text, product_name, manufacturer_name, ls_base64, searched_text)
    uip_dict['this_product_only']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Info of this product')
    # CALL API - SAVE RESULT
    uip_dict['this_product_only']['api_error'] = api_error
    uip_dict['this_product_only']['response'] = response
    uip_dict['this_product_only']['rescontent'] = rescontent
    uip_dict['this_product_only']['answer'] = str(rescontent)

    ####################
    # INDUSTRY_CLUSTER #
    ####################
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = []
    business_line = uip_dict['uip_business_line']
    searched_text = uip_dict['combined_web_search']['text']
    body = PIM_buildBodySelectIndustryCluster(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
    uip_dict['industry_cluster']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Industry Cluster', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['industry_cluster']['api_error'] = api_error
    uip_dict['industry_cluster']['response'] = response
    uip_dict['industry_cluster']['rescontent'] = rescontent
    uip_dict['industry_cluster']['answer'] = rescontent['industry_cluster']
    uip_dict['industry_cluster']['reason'] = rescontent['reason']

    ################
    # COMPOSITIONS #
    ################
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = []
    business_line = uip_dict['uip_business_line']
    searched_text = uip_dict['combined_web_search']['text']
    body = PIM_buildBodySelectComposition(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
    uip_dict['compositions']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Compositions', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['compositions']['api_error'] = api_error
    uip_dict['compositions']['response'] = response
    uip_dict['compositions']['rescontent'] = rescontent
    if business_line == 'PCI':
        uip_dict['compositions']['answer'] = [k for k, v in rescontent.items() if v]
    else: 
        uip_dict['compositions']['answer'] = rescontent['compositions']
    uip_dict['compositions']['reason'] = None

    ################
    # APPLICATIONS #
    ################
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = []
    business_line = uip_dict['uip_business_line']
    searched_text = uip_dict['combined_web_search']['text']
    body = PIM_buildBodySelectApplication(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
    uip_dict['applications']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Applications', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['applications']['api_error'] = api_error
    uip_dict['applications']['response'] = response
    uip_dict['applications']['rescontent'] = rescontent
    uip_dict['applications']['answer'] = [k for k, v in rescontent.items() if v]
    uip_dict['applications']['reason'] = None

    #############
    # FUNCTIONS #
    #############
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = []
    business_line = uip_dict['uip_business_line']
    searched_text = uip_dict['combined_web_search']['text']
    body = PIM_buildBodySelectFunction(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
    uip_dict['functions']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Functions', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['functions']['api_error'] = api_error
    uip_dict['functions']['response'] = response
    uip_dict['functions']['rescontent'] = rescontent
    uip_dict['functions']['answer'] = [k for k, v in rescontent.items() if v]
    uip_dict['functions']['reason'] = None

    ##############################
    # CAS NUMBER - FROM DOCUMENT #
    ##############################
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = uip_dict['combined_ls_b64']
    searched_text = ''
    body = PIM_buildBodyFindCASNumber(parsed_text, product_name, manufacturer_name, ls_base64, searched_text)
    uip_dict['cas_from_doc']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get CAS Number', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['cas_from_doc']['api_error'] = api_error
    uip_dict['cas_from_doc']['response'] = response
    uip_dict['cas_from_doc']['rescontent'] = rescontent
    uip_dict['cas_from_doc']['answer'] = rescontent['cas_number']
    uip_dict['cas_from_doc']['reason'] = None

    #################
    # PHYSICAL_FORM #
    #################
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = uip_dict['combined_ls_b64']
    business_line = uip_dict['uip_business_line']
    searched_text = uip_dict['combined_web_search']['text']
    body = PIM_buildBodyFindPhysicalForm(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
    uip_dict['physical_form']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Physical Form', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['physical_form']['api_error'] = api_error
    uip_dict['physical_form']['response'] = response
    uip_dict['physical_form']['rescontent'] = rescontent
    uip_dict['physical_form']['answer'] = rescontent['physical_form']
    uip_dict['physical_form']['reason'] = rescontent['reason']

    #######################
    # PRODUCT_DESCRIPTION #
    #######################
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = uip_dict['combined_ls_b64']
    searched_text = uip_dict['combined_web_search']['text']
    body = PIM_buildBodyGetProductDescription(parsed_text, product_name, manufacturer_name, ls_base64, searched_text)
    uip_dict['product_description']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Product Description', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['product_description']['api_error'] = api_error
    uip_dict['product_description']['response'] = response
    uip_dict['product_description']['rescontent'] = rescontent
    uip_dict['product_description']['answer'] = rescontent['product_description']
    uip_dict['product_description']['reason'] = None

    ######################
    # RECOMMENDED_DOSAGE #
    ######################
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = uip_dict['combined_ls_b64']
    searched_text = uip_dict['combined_web_search']['text']
    body = PIM_buildBodyGetRecommendedDosage(parsed_text, product_name, manufacturer_name, ls_base64, searched_text)
    uip_dict['recommended_dosage']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Recommended Dosage', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['recommended_dosage']['api_error'] = api_error
    uip_dict['recommended_dosage']['response'] = response
    uip_dict['recommended_dosage']['rescontent'] = rescontent
    uip_dict['recommended_dosage']['answer'] = rescontent['recommended_dosage']
    uip_dict['recommended_dosage']['reason'] = rescontent['reason']

    ##################
    # CERTIFICATIONS #
    ##################
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = uip_dict['combined_ls_b64']
    business_line = uip_dict['uip_business_line']
    searched_text = uip_dict['combined_web_search']['text']
    body = PIM_buildBodySelectCertifications(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
    uip_dict['certifications']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Certifications', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['certifications']['api_error'] = api_error
    uip_dict['certifications']['response'] = response
    uip_dict['certifications']['rescontent'] = rescontent
    uip_dict['certifications']['answer'] = rescontent['certifications']
    uip_dict['certifications']['reason'] = rescontent['reason']

    ##########
    # CLAIMS #
    ##########
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = uip_dict['combined_ls_b64']
    business_line = uip_dict['uip_business_line']
    searched_text = uip_dict['combined_web_search']['text']
    body = PIM_buildBodySelectClaims(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text)
    uip_dict['claims']['body'] = body
    # CALL API - USING AZURE AI FOUNDARY
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Claims', show_answer=True)
    # CALL API - SAVE RESULT
    uip_dict['claims']['api_error'] = api_error
    uip_dict['claims']['response'] = response
    uip_dict['claims']['rescontent'] = rescontent
    uip_dict['claims']['answer'] = [k for k, v in rescontent.items() if v]
    uip_dict['claims']['reason'] = None

    ###############################
    # RECOMMENDED_HEALTH_BENEFITS #
    ###############################
    # PREP BODY
    parsed_text = uip_dict['this_product_only']['answer']
    product_name = uip_dict['uip_product_name']
    manufacturer_name = uip_dict['manufacturer_or_supplier']['answer']
    ls_base64 = uip_dict['combined_ls_b64']
    searched_text = uip_dict['combined_web_search']['text']
    if uip_dict['uip_business_line'] == 'FBI':
        selection_list = ["Dietary Fiber",
                          "Food Culture",
                          "Fortification/Nutraceutical",
                          "Probiotic/Postbiotic",
                          "Protein"]
        lsFunctionsStr = str(uip_dict['functions']['answer'])
        if any(item in lsFunctionsStr for item in selection_list):
            body = PIM_buildBodySelectHealthBenefits(parsed_text, product_name, manufacturer_name, ls_base64, searched_text)
            uip_dict['rec_health_benefits']['body'] = body
            # CALL API - USING AZURE AI FOUNDARY
            url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
            headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
            api_error, response, rescontent = customCallAPI(url, body, headers=headers, log_prefix='Get Recommend Health Benefits', show_answer=True)
            # CALL API - SAVE RESULT
            uip_dict['rec_health_benefits']['api_error'] = api_error
            uip_dict['rec_health_benefits']['response'] = response
            uip_dict['rec_health_benefits']['rescontent'] = rescontent
            uip_dict['rec_health_benefits']['answer'] = rescontent['rec_health_benefits']
            uip_dict['rec_health_benefits']['reason'] = rescontent['reason']

    # DEBUG
    with st.expander('uip_dict'):
        st.json(uip_dict)





