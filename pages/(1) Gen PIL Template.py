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
from PIL import Image

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

from customutils import *

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# App Configuration
st.set_page_config(page_title="Generate Product Form", layout="wide")
st.title("(1) Product Form Generation from PDF")

# Initialize session state
if 'STEP' not in st.session_state:
    st.session_state['STEP'] = 'USER_UPLOAD_AND_PARSE'
if 'file_dict' not in st.session_state:
    st.session_state['file_dict'] = {}
if 'dfPROD' not in st.session_state:
    st.session_state['dfPROD'] = pd.DataFrame()
if 'dfSUBS' not in st.session_state:
    st.session_state['dfSUBS'] = pd.DataFrame()


#######################
# USER UPLOAD & PARSE #
#######################
if st.session_state['STEP']=='USER_UPLOAD_AND_PARSE':
    st.header('Upload PDF Files')
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
                }
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
                file_dict[filename]['S1_PARSE']['result'] = None

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
            #if file_dict[filename]['S1_PARSE']['status'] == '✅ Success' and file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] == '✅ Success':
            if file_dict[filename]['S2_READ_PDF_TO_BASE64']['status'] == '✅ Success':    
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
                    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
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
    st.header('List Of Products Found in Each File')
    file_dict = st.session_state['file_dict']
    dfPROD = st.session_state['dfPROD'].copy()
    st.dataframe(dfPROD)

    # DEBUG
    # st.session_state['file_dict'] = file_dict
    # with st.expander("Parsed Results", expanded=False):
    #     st.json(st.session_state['file_dict'])
    # with st.expander("dfPROD", expanded=False):
    #     st.dataframe(st.session_state['dfPROD'])

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

                ### USING TUNNEL
                # response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
                #                         json=body, 
                #                         params={"apikey": os.getenv('OPENAI_API_KEY')},
                #                         verify=False)

                ### USING AZURE AI FOUNDARY
                url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                response = requests.post(url,                                    
                                         headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                         data=json.dumps(body),
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

                ### USING TUNNEL
                # response = requests.post("https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai",                                         
                #                         json=body, 
                #                         params={"apikey": os.getenv('OPENAI_API_KEY')},
                #                         verify=False)

                ### USING AZURE AI FOUNDARY
                url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4o-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
                response = requests.post(url,                                    
                                         headers={"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')},
                                         data=json.dumps(body),
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

        # DEBUG
        # st.session_state['file_dict'] = file_dict
        # with st.expander("Parsed Results", expanded=False):
        #     st.json(st.session_state['file_dict'])
        # with st.expander("dfPROD", expanded=False):
        #     st.dataframe(st.session_state['dfPROD'])

        # BUILD SUMMARY DATAFRAME BY COMPOSITION
        st.write(f"⏳ **BUILDING SUMMARY TABLE**")
        lsdf = []
        for i in range(len(dfPROD)):
            raw_composition = dfPROD['RAW_COMPOSITION'].iat[i]['composition']
            raw_fields = dfPROD['RAW_FIELDS'].iat[i]
            for comp in raw_composition:
                lsdf.append(
                    pd.DataFrame({'FILE_NAME':[dfPROD['FILE_NAME'].iat[i]],
                    'PRODUCT_NAME': [dfPROD['PRODUCT_NAME'].iat[i]],
                    'SUPPLIER_NAME': [dfPROD['SUPPLIER_NAME'].iat[i]],
                    'MANUFACTURING_SITE_ADDRESS': [raw_fields['manufacturing_site_address']],
                    'MANUFACTURER_ARTICLE_NUMBER': [raw_fields['manufacturer_article_number']],
                    'PHYSICAL_LOCATION': [raw_fields['physical_location_of_goods']],

                    'SUBSTANCE_NAME': [comp['substance_name']],
                    'SUBSTANCE_ROLE': [comp['role_of_substance']],
                    'SUBSTANCE_EC': [comp['ec_number']],
                    'SUBSTANCE_PERCENTAGE': [comp['percentage']],    

                    'CONTAIN_ANIMAL_ORIGIN': [raw_fields['contains_animal_origin']],  
                    'CONTAIN_VEGETAL_ORIGIN': [raw_fields['contains_vegetal_origin']],
                    'CONTAIN_PALM_ORIGIN': [raw_fields['contains_palm']],
                    'CONTAIN_MINERAL_ORIGIN': [raw_fields['contains_mineral_origin']],
                    'CONTAIN_CONFLICT_MINERALS': [raw_fields['contains_conflict_minerals']],
                    'CONTAIN_SYNTHETIC_ORIGIN': [raw_fields['contains_synthetic_origin']],
                    'CONTAIN_OTHER_SPECIFIC_ORIGIN': [raw_fields['other_specified_origin']],

                    'OUTER_PACKAGING_UNIT': [raw_fields['outer_packaging_unit']],
                    'OUTER_PACKAGING_MATERIAL': [raw_fields['outer_packaging_material']],
                    'OUTER_PACKAGING_UN_HOMOLOGATED': [raw_fields['un_homologated_outer_packaging']],
                    'INNER_PACKAGING_UNIT': [raw_fields['inner_packaging_unit']],                  
                    'INNER_MATERIAL': [raw_fields['inner_packaging_material']],
                    'WEIGHT_GROSS_KG': [raw_fields['gross_weight_kg']],             
                    'WEIGHT_NET_KG': [raw_fields['net_weight_kg']],    
                    'DIMENSIONS_LWH': [raw_fields['dimensions_lwh']],      
                    'VOLUME_OF_PACKAGING_UNIT_M3': [raw_fields['volume_m3']],
                    'PALLET_TYPE_AND_MATERIAL': [raw_fields['pallet_type_material']],
                    'STORAGE_CONDITIONS': [raw_fields['storage_conditions']],
                    'TRANSPORT_CONDITIONS': [raw_fields['transport_conditions']],
                    'SHELF_LIFE': [raw_fields['shelf_life']],
                    'LOT_BATCH_STRUCTURE': [raw_fields['lot_batch_structure']],

                    'TARIFF_CODE': [raw_fields['tariff_code']],
                    'ORIGIN_COUNTRY': [raw_fields['origin_country']],
                    'CUSTOMS_STATUS': [raw_fields['customs_status']],
                    'PREFER_ORIGIN_EU': [raw_fields['preferential_origin_eu']],
                    'PREFER_ORIGIN_UK': [raw_fields['preferential_origin_uk']],
                    'PREFER_ORIGIN_CH': [raw_fields['preferential_origin_ch']],
                    'PREFER_EU_SUPPLIER': [raw_fields['preferred_eu_supplier']],

                    'ESTIMATED_COST_LOCAL_CURRENCY': [raw_fields['estimated_cost_local']],
                    'QUANTITY_IN_1ST_PO': [raw_fields['quantity_in_1st_po']],
                    'ESTIMATED_CURRENT_YEAR_QTY': [raw_fields['estimated_year_quantity']],
                    'CUSTOM_CLEARANCE_DONE_BY': [raw_fields['custom_clearance_by']],
                    'COUNTRY_SOLDTO': [raw_fields['country_sold_to']],
                    'LOCATION_AT_TIME_OF_PO': [raw_fields['location_at_time_of_po']],
                    'CUSTOM_CLEARANCE_COUNTRY': [raw_fields['custom_clearance_country']],
                    }))
        dfSUBS = pd.concat(lsdf, ignore_index=True)
        # SAVE TO SESSION
        st.session_state['file_dict'] = file_dict
        st.session_state['dfPROD'] = dfPROD.copy()
        st.session_state['dfSUBS'] = dfSUBS.copy()
        st.session_state['STEP'] = 'EXPORT'       
        st.rerun()

##########
# EXPORT #
########## 
elif st.session_state['STEP']=='EXPORT':
    st.header('Export Results')
    file_dict = st.session_state['file_dict']
    dfPROD = st.session_state['dfPROD'].copy()
    dfSUBS = st.session_state['dfSUBS'].copy()
    st.write("Exported Data:")
    st.dataframe(dfPROD)



    st.dataframe(dfSUBS)
    #st.json(st.session_state['file_dict'])


##########
# EXPORT #
########## 
# with st.expander("Parsed Results", expanded=False):
#     st.json(st.session_state['file_dict'])
# with st.expander("dfPROD", expanded=False):
#     st.dataframe(st.session_state['dfPROD'])
