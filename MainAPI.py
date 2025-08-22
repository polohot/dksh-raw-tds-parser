from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from typing import List, Annotated
import asyncio
import random
import tempfile
import shutil
import os
import fitz
import io
import base64
import datetime
from PIL import Image
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# Azure AI Document Intelligence
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
# Load environment variables
from dotenv import load_dotenv
load_dotenv()
# Custom Utils
from customutils import *

############
# INIT APP #
############

app = FastAPI()

#################
# HELPER - TEST #
#################

async def func1() -> int:
    delay = random.randint(1, 5)
    await asyncio.sleep(delay)
    return delay

async def func2() -> int:
    delay = random.randint(1, 5)
    await asyncio.sleep(delay)
    return delay

async def func3() -> int:
    delay = random.randint(1, 5)
    await asyncio.sleep(delay)
    return delay

###################
# HELPER - ACTUAL #
###################




#############
# END POINT #
#############

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/wait_series")
async def wait_series():    
    time1 = await func1()
    time2 = await func2()
    time3 = await func3()
    return {"time1": time1, "time2": time2, "time3": time3}

@app.post("/wait_parallel")
async def wait_parallel():
    time1, time2, time3 = await asyncio.gather(func1(), func2(), func3())
    return {"time1": time1, "time2": time2, "time3": time3}

@app.post("/v1_parse_pim_fields_series")
async def v1_parse_pim_fields_series(
    inputProductName: Annotated[str, Form(...)],
    inputBusinessLine: Annotated[str, Form(...)],
    inputListDocumentation: Annotated[List[UploadFile], File(...)],
    inputWebSearch: Annotated[bool, Form(...)],
    inputSecret1: Annotated[str, Form(...)]):

    if inputSecret1 != os.getenv('CUSTOM_SECRET1'):
        raise HTTPException(status_code=403, detail="Forbidden")
    else:
        try:
            # TIME START
            timeStart = datetime.datetime.now()

            ####################
            # STAGE 0 - SERIES #
            ####################
            # SAVE UPLOADED FIELS TEMPORARILY
            lsTempFile = v1_saveUploadFilesTemporarly(inputListDocumentation)
            # BUSINESS LINE
            if inputBusinessLine == 'FBI': businessLineStr = "Food & Beverage"
            elif inputBusinessLine == 'PCI': businessLineStr = "Personal Care"
            elif inputBusinessLine == 'PHI': businessLineStr = "Pharma & Healthcare"
            elif inputBusinessLine == 'SCI': businessLineStr = "Specialty Chemicals"
            # INIT DICT
            mainDict = {
                'inputProductName': inputProductName,
                'inputBusinessLine': inputBusinessLine,            
                'businessLineStr': businessLineStr,
                'inputListDocumentation': inputListDocumentation,
                'inputWebSearch': inputWebSearch,
                'lsTempFile': lsTempFile}

            ######################
            # STAGE 1 - PARALLEL #
            ######################
            # PARSED_TO_TEXT
            lsParsedText = v1_parsePDF(lsTempFile)
            mainDict['lsParsedText'] = lsParsedText
            mainDict['parsedText'] = "\n\n".join(lsParsedText)
            # READ_PDF_TO_BASE64
            lsBase64 = v1_readPDFToBase64(lsTempFile)
            mainDict['lsBase64'] = lsBase64

            ####################
            # STAGE 2 - SERIES #
            ####################
            mainDict = v1_addFieldsMainDict(mainDict)
            mainDict['gpt_manufacturer_or_supplier_answer'], mainDict['gpt_manufacturer_or_supplier_reason'] = v1_getManufacturerOrSupplier(mainDict)

            ######################
            # STAGE 3 - PARALLEL #
            ######################
            mainDict['gpt_composition_search_answer'] = v1_searchComposition(mainDict)
            mainDict['gpt_function_search_answer'] = v1_searchFunction(mainDict)
            mainDict['gpt_application_search_answer'] = v1_searchApplication(mainDict)

            ####################
            # STAGE 4 - SERIES #
            ####################        
            mainDict['gpt_combined_web_search'] = v1_combineWebSearch(mainDict)
            mainDict['gpt_text_of_this_product_only_answer'] = v1_getTextOfThisProductOnly(mainDict)

            ######################
            # STAGE 5 - PARALLEL #
            ######################
            mainDict['gpt_select_industry_cluster_answer'], mainDict['gpt_select_industry_cluster_reason'] = v1_selectIndustryCluster(mainDict)
            mainDict['gpt_select_compositions_answer'], mainDict['gpt_select_compositions_reason'] = v1_selectCompositions(mainDict)
            mainDict['gpt_select_functions_answer'], mainDict['gpt_select_functions_reason'] = v1_selectFunctions(mainDict)
            mainDict['gpt_select_applications_answer'], mainDict['gpt_select_applications_reason'] = v1_selectApplications(mainDict)        
            mainDict['gpt_cas_from_doc_answer'] = v1_findCASNumber(mainDict)
            mainDict['gpt_physical_form_answer'], mainDict['gpt_physical_form_reason'] = v1_findPhysicalForm(mainDict)
            mainDict['gpt_gen_product_description'] = v1_genProductDescription(mainDict)
            mainDict['gpt_recommended_dosage_answer'], mainDict['gpt_recommended_dosage_reason'] = v1_getRecommendedDosage(mainDict)
            mainDict['gpt_certifications_answer'], mainDict['gpt_certifications_reason'] = v1_selectCertifications(mainDict)
            mainDict['gpt_claims_answer'], mainDict['gpt_claims_reason'] = v1_selectClaims(mainDict)
            mainDict['gpt_health_benefits_answer'], mainDict['gpt_health_benefits_reason'] = v1_selectHealthBenefits(mainDict)

            # TIME_END
            timeEnd = datetime.datetime.now()
            mainDict['timeStart'] = timeStart
            mainDict['timeEnd'] = timeEnd
            mainDict['timeDuration'] = mainDict['timeEnd'] - mainDict['timeStart']

            # TMP
            mainDict['inputListDocumentation'] = None
            mainDict['lsParsedText'] = None
            mainDict['parsedText'] = None
            mainDict['lsBase64'] = None
            mainDict['gpt_text_of_this_product_only_answer'] = None

            return mainDict
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
