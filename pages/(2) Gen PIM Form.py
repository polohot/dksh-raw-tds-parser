import os
import io
import pandas as pd
import numpy as np
import streamlit as st
import requests
import tempfile
import json
import base64
import fitz
import pycountry
from PIL import Image

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

from customutils import *

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# App Configuration
st.set_page_config(page_title="Generate Product Form", layout="wide")
st.title("(2) PIM Form Generation from PDF")

# Initialize session state
if 'STEP' not in st.session_state:
    st.session_state['STEP'] = 'USER_UPLOAD_AND_PARSE'
if 'input_dict' not in st.session_state:
    st.session_state['input_dict'] = {}
if 'file_dict' not in st.session_state:
    st.session_state['file_dict'] = {}
if 'dfPROD' not in st.session_state:
    st.session_state['dfPROD'] = pd.DataFrame()
    
#######################
# USER UPLOAD & PARSE #
#######################
if st.session_state['STEP']=='USER_UPLOAD_AND_PARSE':
    st.header('Setup & Upload PDF Files')

    col1, col2, col3 = st.columns(3)
    # PERP COUNTRY SELECTION
    with col1:
        countries = [f"{country.name} ({country.alpha_2})" for country in pycountry.countries]
        selected_country = st.selectbox("Select Country", sorted(countries))
    # PREP BUSINESS LINE SELECTION
    with col2:
        business_line = st.selectbox("Business Line", ["FBI", "PCI", "PHI", "SCI"])
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
            ### SAVE TO INPUT DICT
            st.session_state['input_dict'] = {
                'country': selected_country,
                'business_line': business_line,
                'company_code': company_code}
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
                        'result': None}
            st.session_state['file_dict'] = file_dict            
            ### PARSE FILES
            file_dict = st.session_state['file_dict']
            for filename, fileinfo in file_dict.items():
                st.write(f"⏳ **{filename}** Preparing...")
                ####################
                # S1_PARSE_TO_TEXT #
                ####################
                file_dict[filename]['S1_PARSE'] = {}
                try:
                    ### USING LLAMA PARSE
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
                    #         file_dict[filename]['S1_PARSE']['status'] = '✅ Success'
                    #         file_dict[filename]['S1_PARSE']['result'] = response.json()['results']
                    #     else:
                    #         file_dict[filename]['S1_PARSE']['status'] = f'❌ Error: (HTTP {response.status_code})'

                    ### USING AZURE DOCUMENT INTELLIGENCE
                    markdownText = azureDocumentIntelligenceParsePDF(fileinfo['serverPath'], os.getenv('AZURE_DOCUMENT_INTELLIGENCE_API_KEY'))
                    file_dict[filename]['S1_PARSE']['status'] = '✅ Success'
                    file_dict[filename]['S1_PARSE']['result'] = [markdownText]
                except Exception as e:
                    file_dict[filename]['S1_PARSE']['status'] = f'❌ Error: {str(e)}'

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
                except Exception as e:
                    file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] = f'❌ Error: {str(e)}'
                    file_dict[filename]['S2_READ_PDF_TO_BASE64']['pages'] = []

                #############################
                # S3_GET_PROD_NAME_AND_SUPP #
                #############################
                file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP'] = {}
                if file_dict[filename]['S1_PARSE']['status'] == '✅ Success' and file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] == '✅ Success':
                    try:
                        parsed_text = str(file_dict[filename]['S1_PARSE']['result'][0])
                        ls_base64 = file_dict[filename]['S2_READ_PDF_TO_BASE64']['pages']
                        #############################################
                        # SEARCH PRODUCT NAME AND SUPPLIER FROM PDF #
                        #############################################
                        body = buildBodyGetProductNameAndSupplierFromTextAndImage(parsed_text, ls_base64) 
                        file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['body'] = body

                        ### CALL API - USING TUNNEL
                        # response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
                        #                         json=body, 
                        #                         params={"apikey": os.getenv('OPENAI_API_KEY')},
                        #                         verify=False)

                        ### CALL API - USING AZURE AI FOUNDARY
                        url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-main01-gpt-4o-main01/chat/completions?api-version=2024-12-01-preview"
                        response = requests.post(url,                                    
                                                headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                                data=json.dumps(body),
                                                verify=False)  
                                        
                        # RESULT
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
                            file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['error'] = response.json()
                    except Exception as e:
                        file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: {str(e)}'
                else:
                    file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] = f'❌ Error: S1 or S2 error'

            # BUILD SUMMARY DATAFRAME BY PRODUCT
            st.write(f"⏳ **BUILDING SUMMARY TABLE**")
            lsdf = []
            for filename in file_dict.keys():
                if file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['status'] == '✅ Success':
                    for product in file_dict[filename]['S3_GET_PROD_NAME_AND_SUPP']['result']:
                        lsdf.append(
                            pd.DataFrame({'FILE_NAME':[filename],
                            'COUNTRY': [st.session_state['input_dict']['country']],
                            'BUSINESS_LINE': [st.session_state['input_dict']['business_line']],
                            'COMPANY_CODE': [st.session_state['input_dict']['company_code']],
                            'PRODUCT_NAME': [product['PRODUCT_NAME']],
                            'SUPPLIER_NAME': [product['SUPPLIER_NAME']]}))
                else:
                    lsdf.append(
                        pd.DataFrame({'FILE_NAME':[filename],
                        'COUNTRY': [st.session_state['input_dict']['country']],
                        'BUSINESS_LINE': [st.session_state['input_dict']['business_line']],
                        'COMPANY_CODE': [st.session_state['input_dict']['company_code']],                        
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
    st.header('List Of Products Found in Each File')
    file_dict = st.session_state['file_dict']
    dfPROD = st.session_state['dfPROD'].copy()
    st.dataframe(dfPROD)


    # # DEBUG
    # with st.expander("input_dict", expanded=False):
    #     st.json(st.session_state['input_dict'])
    # with st.expander("file_dict", expanded=False):
    #     st.json(st.session_state['file_dict'])
    # with st.expander("dfPROD", expanded=False):
    #     st.dataframe(st.session_state['dfPROD'])


    if st.button("Get Structured Data From PDF"):
        dfPROD['INDUSTRY_CLUSTER'] = None
        dfPROD['COMPOSITIONS'] = None

        # LOOP EACH ROW
        for i in range(len(dfPROD)):
            # GET ROW DATA
            file_name = dfPROD.iloc[i]['FILE_NAME']
            business_line = dfPROD.iloc[i]['BUSINESS_LINE']
            product_name = dfPROD.iloc[i]['PRODUCT_NAME']
            manufacturer_name = dfPROD.iloc[i]['SUPPLIER_NAME']
            # CHECK IF NOT ERROR
            if 'Error' in product_name:
                st.write(f"❌ **{file_name}** Error, will skip...")
                continue
            # PROCESS      
            st.write(f"⏳ Working **{business_line}** | **{product_name}** from **{manufacturer_name}**...")
            # GET INPUT DATA FOR LLM
            parsed_text = str(file_dict[file_name]['S1_PARSE']['result'][0])
            ls_base64 = file_dict[file_name]['S2_READ_PDF_TO_BASE64']['pages']

            ####################
            # INDUSTRY_CLUSTER #
            ####################
            # body = PIM_buildBodySelectIndustryCluster(parsed_text, product_name, manufacturer_name, ls_base64, business_line)
            # ### CALL API - USING AZURE AI FOUNDARY
            # try:
            #     url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-main01-gpt-4o-main01/chat/completions?api-version=2024-12-01-preview"
            #     response = requests.post(url,                                    
            #                             headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
            #                             data=json.dumps(body),
            #                             verify=False)  
            #     if response.status_code == 200:
            #         rescontent = response.json()['choices'][0]['message']['content']
            #         dfPROD['INDUSTRY_CLUSTER'].iat[i] = json.loads(rescontent)['industry_cluster']
            #     else:
            #         st.write(f"❌ **{file_name}** - Industry Cluster - Error: (HTTP {response.status_code})")
            #         dfPROD['INDUSTRY_CLUSTER'].iat[i] = response.json()
            # except Exception as e:
            #     st.write(f"❌ **{file_name}** - Industry Cluster - Error: {str(e)}")
            #     dfPROD['INDUSTRY_CLUSTER'].iat[i] = str(e)


            ###############
            # COMPOSITION #
            ###############
            if business_line == 'PCI':
                body = PIM_buildBodySelectComposition(parsed_text, product_name, manufacturer_name, ls_base64)
                ### CALL API - USING AZURE AI FOUNDARY
                try:
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-main01-gpt-4o-main01/chat/completions?api-version=2024-12-01-preview"
                    response = requests.post(url,                                    
                                            headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                            data=json.dumps(body),
                                            verify=False)  
                    if response.status_code == 200:
                        rescontent = response.json()['choices'][0]['message']['content']
                        dfPROD['COMPOSITIONS'].iat[i] = json.loads(rescontent)['compositions']
                    else:
                        st.write(f"❌ **{file_name}** - Compositions - Error: (HTTP {response.status_code})")
                        dfPROD['COMPOSITIONS'].iat[i] = response.json()
                except Exception as e:
                    st.write(f"❌ **{file_name}** - Compositions - Error: {str(e)}")
                    dfPROD['COMPOSITIONS'].iat[i] = str(e)
            else:
                dfPROD['COMPOSITIONS'].iat[i] = 'MANUAL' 

                  
        # DEBUG
        with st.expander("input_dict", expanded=False):
            st.json(st.session_state['input_dict'])
        with st.expander("file_dict", expanded=False):
            st.json(st.session_state['file_dict'])
        st.session_state['dfPROD'] = dfPROD.copy()
        with st.expander("dfPROD", expanded=False):
            st.dataframe(st.session_state['dfPROD'])
