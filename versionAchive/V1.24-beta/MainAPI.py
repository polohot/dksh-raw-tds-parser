# GENERAL
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Body
from typing import Dict, Any
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
import hashlib
import time
import anyio
import requests
import json
import simple_salesforce
from PIL import Image

# URLLIB3
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# AZURE AI DOCUMENT INTELLIGENCE
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

# LOAD ENV VARIABLES
from dotenv import load_dotenv
load_dotenv()

# CUSTOM UTILS
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

async def v1_run_stage3_parallel(mainDict):
    """Run Stage 3 search functions in parallel using threads."""
    comp_task = asyncio.to_thread(v1_searchComposition, mainDict)
    func_task = asyncio.to_thread(v1_searchFunction, mainDict)
    appl_task = asyncio.to_thread(v1_searchApplication, mainDict)
    comp_res, func_res, appl_res = await asyncio.gather(
        comp_task, func_task, appl_task, return_exceptions=True
    )
    # Normalize exceptions into empty strings (or handle differently if you prefer)
    if isinstance(comp_res, Exception): comp_res = ''
    if isinstance(func_res, Exception): func_res = ''
    if isinstance(appl_res, Exception): appl_res = ''
    return comp_res, func_res, appl_res


async def run_stage5_parallel(mainDict):
    """Run Stage 5 extraction functions in parallel using threads."""
    tasks = await asyncio.gather(
        asyncio.to_thread(v1_selectIndustryCluster, mainDict),
        asyncio.to_thread(v1_selectCompositions, mainDict),
        asyncio.to_thread(v1_selectFunctions, mainDict),
        asyncio.to_thread(v1_selectApplications, mainDict),
        asyncio.to_thread(v1_findCASNumber, mainDict),
        asyncio.to_thread(v1_findPhysicalForm, mainDict),
        asyncio.to_thread(v1_genProductDescription, mainDict),
        asyncio.to_thread(v1_getRecommendedDosage, mainDict),
        asyncio.to_thread(v1_selectCertifications, mainDict),
        asyncio.to_thread(v1_selectClaims, mainDict),
        asyncio.to_thread(v1_selectHealthBenefits, mainDict),
        return_exceptions=True)

    # Unpack and normalize exceptions
    (
        industry_cluster,
        compositions,
        functions,
        applications,
        cas_number,
        physical_form,
        product_description,
        recommended_dosage,
        certifications,
        claims,
        health_benefits,
    ) = tasks

    def safe_unpack(val, n=2):
        if isinstance(val, Exception):
            return ("", "") if n == 2 else ""
        return val

    # Unpack properly (functions that return tuple vs single value)
    industry_cluster = safe_unpack(industry_cluster, 2)
    compositions     = safe_unpack(compositions, 2)
    functions        = safe_unpack(functions, 2)
    applications     = safe_unpack(applications, 2)
    cas_number       = safe_unpack(cas_number, 2)
    physical_form    = safe_unpack(physical_form, 2)
    product_description = safe_unpack(product_description, 1)
    recommended_dosage  = safe_unpack(recommended_dosage, 2)
    certifications      = safe_unpack(certifications, 2)
    claims              = safe_unpack(claims, 2)
    health_benefits     = safe_unpack(health_benefits, 2)

    return (
        industry_cluster,
        compositions,
        functions,
        applications,
        cas_number,
        physical_form,
        product_description,
        recommended_dosage,
        certifications,
        claims,
        health_benefits
    )

async def run_main(mainDict, time_start):
    ####################
    # STAGE 0 - SERIES #
    ####################
    # BUSINESS LINE
    if mainDict['inputBusinessLine'] == 'FBI': mainDict['stg_businessLineStr'] = "Food & Beverage"
    elif mainDict['inputBusinessLine'] == 'PCI': mainDict['stg_businessLineStr'] = "Personal Care"
    elif mainDict['inputBusinessLine'] == 'PHI': mainDict['stg_businessLineStr'] = "Pharma & Healthcare"
    elif mainDict['inputBusinessLine'] == 'SCI': mainDict['stg_businessLineStr'] = "Specialty Chemicals"            
    
    ###########################
    # STAGE 1 - CHECK HISTORY #
    ###########################
    # CHECK HASH
    mainDict['stg_hashinputProductName'] = hashlib.sha256(mainDict['inputProductName'].encode()).hexdigest()
    mainDict['stg_hashinputBusinessLine'] = hashlib.sha256(mainDict['inputBusinessLine'].encode()).hexdigest()
    lsdoc = [str(x) for x in mainDict['inputListDocumentation']]
    lsdoc.sort()
    mainDict['stg_hashinputListDocumentation'] = hashlib.sha256("".join(lsdoc).encode()).hexdigest()
    hashCombined = hashlib.sha256((mainDict['stg_hashinputProductName'] + mainDict['stg_hashinputBusinessLine'] + mainDict['stg_hashinputListDocumentation']).encode()).hexdigest()
    mainDict['stg_hashCombined'] = hashCombined
    # LOAD FROM HIST IF EXISTS
    mainDictH = load_hist_by_hash(hashCombined)
    if mainDictH is not None:
        mainDict = mainDictH
        time.sleep(random.uniform(10, 15))
        time_end = datetime.datetime.now()
        mainDict['time_start'] = str(time_start)
        mainDict['time_end'] = str(time_end)
        mainDict['time_duration'] = str((time_end - time_start).total_seconds())    
        mainDict['stg_parsedText'] = 'HIDDEN'
        return mainDict
    
    ####################
    # STAGE 2 - SERIES #
    ####################
    # PARSED_TO_TEXT
    stg_lsParsedText = v1_parsePDF(mainDict['stg_lsTempFile'])
    mainDict['stg_lsParsedText'] = stg_lsParsedText
    mainDict['stg_parsedText'] = "\n\n".join(stg_lsParsedText)
    # READ_PDF_TO_BASE64
    stg_lsBase64 = v1_readPDFToBase64(mainDict['stg_lsTempFile'])
    mainDict['stg_lsBase64'] = stg_lsBase64
    # GET MGF/SUPPLIER
    mainDict = v1_addFieldsMainDict(mainDict)
    mainDict['gpt_manufacturer_or_supplier_answer'], mainDict['gpt_manufacturer_or_supplier_reason'] = v1_getManufacturerOrSupplier(mainDict)

    ######################
    # STAGE 3 - PARALLEL #
    ######################
    if mainDict['inputParallel'] == True:
        comp_res, func_res, appl_res = await v1_run_stage3_parallel(mainDict)
        mainDict['gpt_composition_search_answer'] = comp_res
        mainDict['gpt_function_search_answer']   = func_res
        mainDict['gpt_application_search_answer'] = appl_res
    else:
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
    if mainDict['inputParallel'] == True:
        (
            (mainDict['gpt_select_industry_cluster_answer'], mainDict['gpt_select_industry_cluster_reason']),
            (mainDict['gpt_select_compositions_answer'], mainDict['gpt_select_compositions_reason']),
            (mainDict['gpt_select_functions_answer'], mainDict['gpt_select_functions_reason']),
            (mainDict['gpt_select_applications_answer'], mainDict['gpt_select_applications_reason']),
            (mainDict['gpt_cas_from_doc_answer'], mainDict['gpt_cas_from_doc_reason']),
            (mainDict['gpt_physical_form_answer'], mainDict['gpt_physical_form_reason']),
            mainDict['gpt_gen_product_description'],
            (mainDict['gpt_recommended_dosage_answer'], mainDict['gpt_recommended_dosage_reason']),
            (mainDict['gpt_certifications_answer'], mainDict['gpt_certifications_reason']),
            (mainDict['gpt_claims_answer'], mainDict['gpt_claims_reason']),
            (mainDict['gpt_health_benefits_answer'], mainDict['gpt_health_benefits_reason']),
        ) = await run_stage5_parallel(mainDict)
    else:
        mainDict['gpt_select_industry_cluster_answer'], mainDict['gpt_select_industry_cluster_reason'] = v1_selectIndustryCluster(mainDict)
        mainDict['gpt_select_compositions_answer'], mainDict['gpt_select_compositions_reason'] = v1_selectCompositions(mainDict)
        mainDict['gpt_select_functions_answer'], mainDict['gpt_select_functions_reason'] = v1_selectFunctions(mainDict)
        mainDict['gpt_select_applications_answer'], mainDict['gpt_select_applications_reason'] = v1_selectApplications(mainDict)        
        mainDict['gpt_cas_from_doc_answer'], mainDict['gpt_cas_from_doc_reason'] = v1_findCASNumber(mainDict)
        mainDict['gpt_physical_form_answer'], mainDict['gpt_physical_form_reason'] = v1_findPhysicalForm(mainDict)
        mainDict['gpt_gen_product_description'] = v1_genProductDescription(mainDict)
        mainDict['gpt_recommended_dosage_answer'], mainDict['gpt_recommended_dosage_reason'] = v1_getRecommendedDosage(mainDict)
        mainDict['gpt_certifications_answer'], mainDict['gpt_certifications_reason'] = v1_selectCertifications(mainDict)
        mainDict['gpt_claims_answer'], mainDict['gpt_claims_reason'] = v1_selectClaims(mainDict)
        mainDict['gpt_health_benefits_answer'], mainDict['gpt_health_benefits_reason'] = v1_selectHealthBenefits(mainDict)

    ##############################
    # STAGE 6 - HIDE SOME FIELDS #
    ##############################
    time_end = datetime.datetime.now()
    mainDict['time_start'] = str(time_start)
    mainDict['time_end'] = str(time_end)
    mainDict['time_duration'] = str((time_end - time_start).total_seconds())
    mainDict['inputListDocumentation'] = 'HIDDEN'
    mainDict['inputSecret'] = 'HIDDEN'
    mainDict['stg_lsTempFile'] = 'HIDDEN'
    mainDict['stg_lsParsedText'] = 'HIDDEN'
    # mainDict['stg_parsedText'] = 'HIDDEN'
    mainDict['stg_lsBase64'] = 'HIDDEN'
    mainDict['gpt_text_of_this_product_only_answer'] = 'HIDDEN'

    #######################
    # STAGE 7 - SAVE HASH #
    #######################
    tmp_dttm = mainDict['time_start'].replace("-", "").replace(" ", "_").replace(":", "").replace(".", "_")
    filepath = f"histAPICalls/{tmp_dttm}__{mainDict['stg_hashCombined']}.json"
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(mainDict, file, indent=4, 
                ensure_ascii=False,   # Keep all non-ASCII characters readable
                skipkeys=True)        # Skip any keys that aren't valid JSON types
    mainDict['stg_parsedText'] = 'HIDDEN'
    return mainDict




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
    
@app.post("/v1_histAPICalls_count")
async def v1_histAPICalls_count():
    try:
        def _count() -> int:
            # Stream over entries (no big list in memory), count only regular files
            with os.scandir('histAPICalls/') as it:
                return sum(1 for e in it if e.is_file())

        count_files = await anyio.to_thread.run_sync(_count)
        return {"count_histAPICalls": count_files}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Directory not found: histAPICalls/")
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1_histAPICalls_list")
async def v1_histAPICalls_list():
    try:
        def _build_summary() -> Dict[str, Dict[str, Any]]:
            by_date: Dict[str, Dict[str, Any]] = {}
            with os.scandir("histAPICalls/") as it:
                for entry in it:
                    if not entry.is_file() or not entry.name.endswith(".json"):
                        continue                    
                    stem = entry.name[:-5] # strip ".json"
                    try:
                        prefix, hash_combined = stem.split("__", 1)
                    except ValueError:
                        continue
                    date_raw = prefix.split("_", 1)[0]
                    if len(date_raw) != 8 or not date_raw.isdigit():
                        continue
                    date_key = f"{date_raw[0:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
                    if date_key not in by_date:
                        by_date[date_key] = {"count": 0, "hashCombined": []}
                    by_date[date_key]["count"] += 1
                    by_date[date_key]["hashCombined"].append(hash_combined)
            sorted_dates = sorted(by_date.keys(), reverse=True)
            return {d: by_date[d] for d in sorted_dates}
        body = await anyio.to_thread.run_sync(_build_summary)
        return body
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Directory not found: histAPICalls/")
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))

# @app.post("/v1_histAPICalls_read")
# async def v1_histAPICalls_read(
#     stg_hashCombined: Annotated[str, Form(...)]):
#     try:
#         filepath = f"histAPICalls/{stg_hashCombined}.json"
#         if os.path.isfile(filepath):
#             def _read_file() -> dict:
#                 with open(filepath, "r", encoding="utf-8") as file:
#                     return json.load(file)
#             file_content = await anyio.to_thread.run_sync(_read_file)
#             return file_content
#         else:
#             raise HTTPException(status_code=404, detail=f"File not found: {stg_hashCombined}.json")
#     except OSError as e:
#         raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/v1_histAPICalls_read")
async def v1_histAPICalls_read(
    stg_hashCombined: Annotated[str, Form(...)]
):
    try:
        def _find_and_read() -> dict:
            suffix = f"__{stg_hashCombined}.json"
            with os.scandir("histAPICalls/") as it:
                for entry in it:
                    if entry.is_file() and entry.name.endswith(suffix):
                        with open(entry.path, "r", encoding="utf-8") as f:
                            return json.load(f)
            raise FileNotFoundError(f"File not found for hash: {stg_hashCombined}")

        file_content = await anyio.to_thread.run_sync(_find_and_read)
        return file_content

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1_histAPICalls_delete")
async def v1_histAPICalls_delete(
    stg_hashCombined: Annotated[str, Form(...)]
):
    try:
        def _find_and_delete() -> str:
            suffix = f"__{stg_hashCombined}.json"
            with os.scandir("histAPICalls/") as it:
                for entry in it:
                    if entry.is_file() and entry.name.endswith(suffix):
                        os.remove(entry.path)
                        return entry.name  # return actual filename
            raise FileNotFoundError(f"File not found for hash: {stg_hashCombined}")

        deleted_filename = await anyio.to_thread.run_sync(_find_and_delete)
        return {"detail": f"File '{deleted_filename}' removed successfully."}

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1_get_products_and_suppliers")
async def v1_get_products_and_suppliers(
    inputListDocumentation: Annotated[List[UploadFile], File(...)],
    inputSecret: Annotated[str, Form(...)]):

    if str(inputSecret) == os.getenv('CUSTOM_SECRET1'):
        # INIT FILES
        stg_lsTempFile = v1_saveUploadFilesTemporarly(inputListDocumentation)
        mainDict = {
            'inputListDocumentation': inputListDocumentation,
            'inputSecret': inputSecret,
            'stg_lsTempFile': stg_lsTempFile}
        # PARSED_TO_TEXT
        stg_lsParsedText = v1_parsePDF(stg_lsTempFile)
        mainDict['stg_lsParsedText'] = stg_lsParsedText
        mainDict['stg_parsedText'] = "\n\n".join(stg_lsParsedText)
        # READ_PDF_TO_BASE64
        stg_lsBase64 = v1_readPDFToBase64(stg_lsTempFile)
        mainDict['stg_lsBase64'] = stg_lsBase64
        # GET PRODUCTS AND SUPPLIERS
        mainDict['products_and_suppliers'] = v1_getProductNameAndSupplierFromTextAndImage(mainDict)
        # FINALIZE
        mainDict['inputListDocumentation'] = 'HIDDEN'
        mainDict['inputSecret'] = 'HIDDEN'
        mainDict['stg_lsTempFile'] = 'HIDDEN'
        mainDict['stg_lsParsedText'] = 'HIDDEN'
        mainDict['stg_parsedText'] = 'HIDDEN'
        mainDict['stg_lsBase64'] = 'HIDDEN'
        return mainDict
    else:
        return HTTPException(status_code=401)

@app.post("/v1_parse_pim_fields")
async def v1_parse_pim_fields(
    inputProductName: Annotated[str, Form(...)],
    inputBusinessLine: Annotated[str, Form(...)],
    inputListDocumentation: Annotated[List[UploadFile], File(...)],
    inputSecret: Annotated[str, Form(...)],
    inputWebSearch: Annotated[bool, Form()] = False,
    inputParallel: Annotated[bool, Form()] = False):

    if str(inputSecret) == os.getenv('CUSTOM_SECRET1'):
        try:
            # TIME START
            time_start = datetime.datetime.now()
            # SAVE UPLOADED FIELS TEMPORARILY
            stg_lsTempFile = v1_saveUploadFilesTemporarly(inputListDocumentation)
            # MAINDICT
            mainDict = {}
            mainDict['inputProductName'] = inputProductName
            mainDict['inputBusinessLine'] = inputBusinessLine
            mainDict['inputListDocumentation'] = inputListDocumentation
            mainDict['inputSecret'] = inputSecret
            mainDict['inputWebSearch'] = inputWebSearch
            mainDict['inputParallel'] = inputParallel
            mainDict['stg_lsTempFile'] = stg_lsTempFile
            # RUN MAIN
            mainDict = await run_main(mainDict, time_start)
            return mainDict
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        return HTTPException(status_code=401)


@app.post("/v1_parse_pim_fields_b64")
async def v1_parse_pim_fields_b64(
    inputProductName: Annotated[str, Form(...)],
    inputBusinessLine: Annotated[str, Form(...)],
    inputListDocumentationB64: Annotated[List[str], Body(...)],
    inputSecret: Annotated[str, Form(...)],
    inputWebSearch: Annotated[bool, Form()] = False,
    inputParallel: Annotated[bool, Form()] = False):

    if str(inputSecret) == os.getenv('CUSTOM_SECRET1'):
        try:
            # TIME START
            time_start = datetime.datetime.now()
            # SAVE UPLOADED FIELS TEMPORARILY
            inputListDocumentation = inputListDocumentationB64
            stg_lsTempFile = v1_saveUploadFilesTemporarlyB64(inputListDocumentation)
            # MAINDICT
            mainDict = {}
            mainDict['inputProductName'] = inputProductName
            mainDict['inputBusinessLine'] = inputBusinessLine
            mainDict['inputListDocumentation'] = inputListDocumentation
            mainDict['inputSecret'] = inputSecret
            mainDict['inputWebSearch'] = inputWebSearch
            mainDict['inputParallel'] = inputParallel
            mainDict['stg_lsTempFile'] = stg_lsTempFile
            # RUN MAIN
            mainDict = await run_main(mainDict, time_start)
            return mainDict
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        return HTTPException(status_code=401)