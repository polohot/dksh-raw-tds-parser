import tempfile
import os
import shutil
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import requests
import json
from fastapi import HTTPException, Form
from typing import Annotated

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

def azureDocumentIntelligenceParsePDF(file_path, key):
    document_intelligence_client = DocumentIntelligenceClient(
        endpoint="https://document-intelligence-standard-s0-dksh-raw-tds-parser.cognitiveservices.azure.com/", credential=AzureKeyCredential(key))
    with open(file_path, "rb") as f:
        poller = document_intelligence_client.begin_analyze_document(
            "prebuilt-read", 
            f,
            content_type="application/pdf")
        result = poller.result()
    # Build Markdown content from lines
    markdown_lines = []
    for page_num, page in enumerate(result.pages):
        markdown_lines.append(f"\n## Page {page_num + 1}\n")
        for line in page.lines:
            markdown_lines.append(line.content)
    markdown_output = "\n".join(markdown_lines)
    #print("Markdown Output:\n")
    #print(markdown_output)
    return markdown_output

###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################

def PIM_buildBodyGetManufacturerOrSupplier(parsed_text, product_name, ls_base64):
    # SYSTEM PROMPT
    system_prompt = f"""
    You are a data extraction agent that processes technical documents and extracts information.
    Based on the provided text and images, focus only on product [{product_name}] to find its manufacturer or supplier name.
    Some time the given data will have multiple manufacturer or supplier, but you only need to focus on product [{product_name}].
    """
    # BUILD THE MESSAGE FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": parsed_text}]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]})
    # CONSTRUCT BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "manufacturer_or_supplier_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "manufacturer_or_supplier": {
                            "type": "string",
                            "description": f"Give the manufacturer or supplier name. Focus on product [{product_name}]. No explanation"},
                        'reason': {
                            "type": "string",
                            "description": f"Reason why you select this manufacturer or supplier for this product [{product_name}]"
                        }
                    },
                    "required": ["manufacturer_or_supplier", "reason"],
                    "additionalProperties": False
                }
            }
        }
    }
    return body

###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################

def v1_customCallAPI(url, body, headers={}, params={}):
    while True:
        try:
            response = requests.post(
                url, 
                headers=headers, 
                data=json.dumps(body),
                params=params,
                verify=False)
            if response.status_code == 200:                
                response = response.json()
                try:
                    rescontent = response['choices'][0]['message']['content']
                    rescontent = json.loads(rescontent)
                    return 0, response, rescontent
                except:
                    try:
                        rescontent = response['choices'][0]['message']['content']
                        return 0, response, rescontent
                    except Exception as e1:
                        return 1, response, {'error':str(e1)}     
            elif response.status_code in [499, 500, 503]:
                continue
            else:
                return 1, response, response
        except Exception as e2:
            return 1, {'error':str(e2)}, {'error':str(e2)}
        
def v1_saveUploadFilesTemporarly(inputListDocumentation):
    # Save uploaded files temporarily
    lsTempFile = []
    for file in inputListDocumentation:
        suffix = os.path.splitext(file.filename)[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmpdict = {"filename": file.filename, "temp_path": tmp.name}
            lsTempFile.append(tmpdict)
    return lsTempFile

def v1_parsePDF(stg_lsTempFile):
    stg_lsParsedText = []
    for tempFile in stg_lsTempFile:
        try:
            markdownText = azureDocumentIntelligenceParsePDF(tempFile['temp_path'], os.getenv('AZURE_DOCUMENT_INTELLIGENCE_API_KEY'))
            markdownText = f"TEXT_FROM_FILE_NAME:{tempFile['filename']} \n\n" + markdownText
            stg_lsParsedText.append(markdownText)
        except:
            pass
    return stg_lsParsedText

def v1_readPDFToBase64(stg_lsTempFile):
    stg_lsBase64 = []
    for tempFile in stg_lsTempFile:
        try:
            doc = fitz.open(tempFile['temp_path'])
            for page_number in range(len(doc)):
                try:
                    page = doc.load_page(page_number)
                    pix = page.get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    buffered = io.BytesIO()
                    img.save(buffered, format="PNG")
                    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    stg_lsBase64.append(img_base64)
                except:
                    pass
        except:
            pass
    return stg_lsBase64

def v1_addFieldsMainDict(mainDict):
    mainDict['gpt_manufacturer_or_supplier_answer'] = None
    mainDict['gpt_manufacturer_or_supplier_reason'] = None
    mainDict['gpt_composition_search_answer'] = None
    mainDict['gpt_function_search_answer'] = None
    mainDict['gpt_application_search_answer'] = None
    mainDict['gpt_combined_web_search'] = None
    mainDict['gpt_text_of_this_product_only_answer'] = None
    mainDict['gpt_select_industry_cluster_answer'] = None
    mainDict['gpt_select_industry_cluster_reason'] = None
    mainDict['gpt_select_compositions_answer'] = None
    mainDict['gpt_select_compositions_reason'] = None
    mainDict['gpt_select_functions_answer'] = None
    mainDict['gpt_select_functions_reason'] = None
    mainDict['gpt_select_applications_answer'] = None
    mainDict['gpt_select_applications_reason'] = None
    mainDict['gpt_cas_from_doc_answer'] = None
    mainDict['gpt_physical_form_answer'] = None
    mainDict['gpt_physical_form_reason'] = None
    mainDict['gpt_gen_product_description'] = None
    mainDict['gpt_recommended_dosage_answer'] = None
    mainDict['gpt_recommended_dosage_reason'] = None
    mainDict['gpt_certifications_answer'] = None
    mainDict['gpt_certifications_reason'] = None
    mainDict['gpt_claims_answer'] = None
    mainDict['gpt_claims_reason'] = None
    mainDict['gpt_health_benefits_answer'] = None
    mainDict['gpt_health_benefits_reason'] = None
    return mainDict

def v1_getManufacturerOrSupplier(mainDict):
    stg_parsedText = mainDict['stg_parsedText']
    inputProductName = mainDict['inputProductName']
    stg_lsBase64 = []
    # CALL API
    body = PIM_buildBodyGetManufacturerOrSupplier(stg_parsedText, inputProductName, stg_lsBase64)  
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0: return rescontent['manufacturer_or_supplier'], rescontent['reason']
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_getManufacturerOrSupplier')