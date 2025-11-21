import tempfile
import os
import shutil
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import requests
import json
import hashlib
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

def PIM_buildBodyGetProductNameAndSupplierFromTextAndImage(parsed_text, ls_base64):
    # SYSTEM PROMPT
    system_prompt = """
    # INSTRUCTION #
    You are a data extraction agent that extract product name and manufacturer from given technical documents.
    Sometimes the parsed PDF has only one product, sometimes multiple, make sure that the output covers all the product and manufacturer in the provided data

    # OUTPUT FORMAT #
    {{
        "products_and_suppliers": array of objects
    }}

    # OUTPUT EXAMPLES #

    [
    {"PRODUCT_NAME":"Sugar C1002","SUPPLIER_NAME":"ACME Sugar Malaysia Berhad"}
    ]

    [
    {"PRODUCT_NAME":"Mint Concentrate MT2245","SUPPLIER_NAME":"Emmi Switzerland"}
    ]

    [
    {"PRODUCT_NAME":"AirPods Pro (2nd Generation)","SUPPLIER_NAME":"Apple Inc."},
    {"PRODUCT_NAME":"Apple Watch Series 9","SUPPLIER_NAME":"Apple Inc."}
    ]

    [
    {"PRODUCT_NAME":"HP Spectre x360 14","SUPPLIER_NAME":"HP Inc."},
    {"PRODUCT_NAME":"HP ENVY 6055 All-in-One Printer","SUPPLIER_NAME":"HP Inc."},
    {"PRODUCT_NAME":"HP Omen 45L Gaming Desktop","SUPPLIER_NAME":"HP Inc."}
    ]

    [
    {"PRODUCT_NAME":"PlayStation 5","SUPPLIER_NAME":"Sony Interactive Entertainment"},
    {"PRODUCT_NAME":"PlayStation 5 Digital Edition","SUPPLIER_NAME":"Sony Interactive Entertainment"},
    {"PRODUCT_NAME":"PlayStation VR2","SUPPLIER_NAME":"Sony Interactive Entertainment"},
    {"PRODUCT_NAME":"WH-1000XM5 Wireless Headphones","SUPPLIER_NAME":"Sony Interactive Entertainment"},
    {"PRODUCT_NAME":"Alpha 7 IV Mirrorless Camera","SUPPLIER_NAME":"Sony Interactive Entertainment"}
    ]

    [
    {"PRODUCT_NAME":"LG Gram 17 Laptop","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG C3 OLED TV","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG UltraGear 27GN950 Gaming Monitor","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG TONE Free HBS-FN7 Earbuds","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG CordZero A9 Ultimate Vacuum","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG Styler ThinQ Steam Closet","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG TWINWash Washing Machine","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG InstaView Door-in-Door Refrigerator","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG ThinQ Speaker XBOOM 360","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG UBK90 Ultra HD Blu-ray Player","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG R9 Robot Vacuum Cleaner","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG OLED evo Gallery Edition TV","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG Soundbar S95QR","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG DualUp Monitor 28MQ780","SUPPLIER_NAME":"LG Electronics"},
    {"PRODUCT_NAME":"LG PuriCare 360° Air Purifier","SUPPLIER_NAME":"LG Electronics"}
    ]
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user","content": parsed_text}] 
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # CONSTRUCT BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "product_supplier_list",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "products_and_suppliers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "PRODUCT_NAME": {
                                        "type": "string",
                                        "description": "Name of the product"
                                    },
                                    "SUPPLIER_NAME": {
                                        "type": "string",
                                        "description": "Name of the supplier or manufacturer"
                                    }
                                },
                                "required": ["PRODUCT_NAME", "SUPPLIER_NAME"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["products_and_suppliers"],
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

def PIM_buildBodyGetManufacturerOrSupplier(parsed_text, product_name, ls_base64):
    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
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
    properties = {}
    properties["manufacturer_or_supplier"] = {"type": "string", "description": f"Give the manufacturer or supplier name. Focus on product [{product_name}]. No explanation"}
    properties["reason"] = {"type": "string", "description": "Reasoning for each option selected, grounded from given document"}
    required  = ["manufacturer_or_supplier", "reason"]
    json_schema = {
        "name": "manufacturer_or_supplier_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False}}
    # FULL REQUEST BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
    return body    

def PIM_buildBodyGetProductInfo(parsed_text, product_name, manufacturer_name, ls_base64, searched_text=''):
    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are a data extraction agent that processes technical documents and extracts information.
    Based on the provided text and images, focus only on product [{product_name}] from manufacturer [{manufacturer_name}].
    Some time the given data will have multiple products, but you only need to focus on [{product_name}].
    Do not do summarization on the text, we need the full raw data of this product.
    If you found image related to the product, parse the image data as much detail as possible and include it in the output.

    # IMPORTANT NOTE #
    This text will be the representation of the whole document for this product to input to the next llm step, 
    so make sure the data is complete and accurate.

    # OUTPUT FORMAT #
    Output in markdown format.
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": parsed_text},
        {"role": "user", "content": searched_text}
    ]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # CONSTRUCT BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16
        }
    return body

def PIM_buildBodySelectIndustryCluster(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # Define mapping of business lines to industry clusters

    # OLD LIST
    # if business_line == 'FBI':
    #     selection_list = [
    #         'Beverage & Dairy',
    #         'Confectionary & Bakery',
    #         'Food Supplements & Nutrition',
    #         'Processed Food & Food Service']
    # elif business_line == 'PCI':
    #     selection_list = [
    #         'Cosmetics & Toiletries',
    #         'Homecare & Institutional Cleaning',
    #         'Cosmetics & Toiletries, Homecare & Institutional Cleaning']
    # elif business_line == 'PHI':
    #     selection_list = [
    #         'Animal Care Industry',
    #         'API',
    #         'Biopharma',
    #         'Excipients',
    #         'Intermediates & Reagents',
    #         'Nutraceuticals',
    #         'Packing Materials',
    #         'Clean Room Management']
    # elif business_line == 'SCI':
    #     selection_list = [
    #         'Electronic & Specialties',
    #         'Paints & Coatings',
    #         'Polymers',
    #         'Agrochemicals',
    #         'Electronic & Specialties, Paints & Coatings',
    #         'Paints & Coatings, Polymers',
    #         'Electronic & Specialties, Polymers',
    #         'Electronic & Specialties, Paints & Coatings, Polymers']
    
    # 2025-11-20 | YEOH HUI YIN & PAULA: Change to new list
    if business_line == 'FBI':
        selection_list = [
            'Beverage & Dairy (BD)',
            'Confectionary & Bakery (CB)',
            'Food Supplements & Nutrition (FSN)',
            'Processed Food & Food Service (PFFS)']
            # Seafood
            # Food & Beverage Industry VAM
            # Food Service VAM
    elif business_line == 'PCI':
        selection_list = [
            'Personal Care',
            'Homecare & Institutional Cleaning']
    elif business_line == 'PHI':
        selection_list = [
            'Animal Care Industry (ACI)',
            'APIs',
            'Biopharma',
            'Excipients',
            'Intermediates',
            'Nutraceuticals',
            'Packing Materials',
            'Clean Room Management']
    elif business_line == 'SCI':
        selection_list = [
            'Electronics & Specialties (ES)',
            'Paints & Coatings (PC)',
            'Polymers (PO)',
            'Agrochemicals (AG)']


    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are an expert data‐flagging assistant for technical product dossiers. 
    Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].   
    Use the given data combine with your own knowledge to determine the INDUSTRY CLUSTER related to the product [{product_name}] from the following list:{selection_list}

    # RULE #
    RULE1: Only select if it is related to the data mentioned in the given document.
    RULE2: Only select if you are atleast 95% sure, no guessing.

    # REASONING #
    Provide short and concise reason why you select each option, Where is it mentioned in the document that make you select this option.
    Your reason format should be "Selected xxx because the mention of yyy in the document" or explanation similar to this.

    # OUTPUT FORMAT #
    {{
        "industry_cluster1": boolean,
        "industry_cluster2": boolean,
        ...
        "reason": string
    }}
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user","content": parsed_text},
        {"role": "user", "content": searched_text}]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # CONSTRUCT BODY
    properties = {name: {"type": "boolean", "description": f"True if the product is related or utilize in the {name} category"} for name in selection_list}
    properties['reason'] = {"type": "string", "description": "Reasoning for each option selected, grounded from given document"}
    required   = list(selection_list) + ['reason']
    json_schema = {
        "name": "flags_only",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False}}
    # FULL REQUEST BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
    return body    

def PIM_buildBodySelectComposition(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are an expert data‐flagging assistant for technical product dossiers. 
    Your task is to analyze only the details provided for product “{product_name}” from manufacturer “{manufacturer_name}” (including text and any images) 
    and determine, for each composition category in the selection list, 
    whether the product composition/ingredients may contain substances from that category.

    # RULE #
    RULE1: Only select if it is related to the data mentioned in the given document.
    RULE2: Only select if you are atleast 95% sure, no guessing.

    # REASONING #
    Provide short and concise reason why you select each option, Where is it mentioned in the document that make you select this option.
    Your reason format should be "Selected xxx because the mention of yyy in the document" or explanation similar to this.
    """
    # CASE BY BL
    if business_line == 'PCI':
        selection_list = [
        # "Animal", 2025-10-10 | SAINT:REQUEST FROM BUSINESS TO REMOVE
        "Biomolecule/Micro-organisms",
        "Derived Natural",
        "Mineral",
        "Synthetic",
        "Vegetal",
        ""]
        system_prompt += """
        # OUTPUT FORMAT #
        {{
            "composition1": boolean,
            "composition2": boolean,
            ...
            "reason": string
        }}
        """
        # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user","content": parsed_text},
            {"role": "user", "content": searched_text}]
        # ADD BASE64 IMAGES IF PROVIDED
        for base64_img in ls_base64:
            messages.append({"role": "user", 
                            "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]})            
        # CONSTRUCT BODY
        properties = {name: {"type": "boolean", "description": f"True if any of the the composition/ingredients has source the is from {name} category"} for name in selection_list}
        properties['reason'] = {"type": "string", "description": "Reasoning for each option selected, grounded from given document"}
        required   = list(selection_list) + ['reason']
        json_schema = {
            "name": "flags_only",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False}}
        # Full request body
        body = {
            "model": "gpt-4.1-mini",
            "messages": messages,
            "temperature": 0,
            "max_tokens": 1024*16,
            "response_format": {
                "type": "json_schema",
                "json_schema": json_schema}}

    else:
        system_prompt += """
        # OUTPUT FORMAT #
        {{
            "compositions": array of objects,
            "reason": string
        }}
        """
        # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user","content": parsed_text},
            {"role": "user", "content": searched_text}]
        # ADD BASE64 IMAGES IF PROVIDED
        for base64_img in ls_base64:
            messages.append({
                "role": "user", "content": [{"type": "image_url",
                                            "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
            })
        # CONSTRUCT BODY
        properties = {}
        properties["compositions"] = {"type": "array", 
                                      "items": {"type": "string"}, 
                                      "description": f"Select as much as possible unique COMPOSITIONS/INGREDIENTS but only those related to the product [{product_name}]"}
        properties["reason"] = {"type": "string", "description": "Reasoning for each option selected, grounded from given document"}
        required  = ["compositions","reason"]
        json_schema = {
            "name": "compositions_output",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False}}
        # FULL REQUEST BODY
        body = {
            "model": "gpt-4.1-mini",
            "messages": messages,
            "temperature": 0,
            "max_tokens": 1024*16,
            "response_format": {
                "type": "json_schema",
                "json_schema": json_schema}}
    return body

def PIM_buildBodySelectFunction(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # SELECTION LIST
    if business_line == 'FBI':
        selection_list = [
            "Acidity Regulator",
            "Antibiotic Residue Testing",
            "Anti-Caking Agent",
            "Antioxidant",
            "Bleaching Agent",
            "Carbonating Agent",
            "Carrier & Bulking Agent",
            "Colour & Colour Retention Agent",
            "Dietary Fiber",
            "Emulsifier",
            "Emulsifying Salt",
            "Firming Agent",
            "Flavour Enhancer",
            "Flavouring & Flavour Modulation",
            "Flour Treatment Agent",
            "Foaming Agent",
            "Food Culture",
            "Food Enzyme",
            "Food Essential",
            "Fortification/Nutraceutical",
            "Humectant",
            "Inclusion",
            "Preservative",
            "Probiotic/Postbiotic",
            "Protein",
            "Raising Agent",
            "Sequestrant",
            "Stabilizer & Thickener",
            "Sweetener",
            "Other"]
    elif business_line == 'PCI':
        selection_list = [
            "Active",
            "Anti-Deposition",
            "Antioxidant",
            "AP/Deo Active",
            # "Biocide", 2025-10-10 | SAINT:REQUEST FROM BUSINESS TO REMOVE
            "Chelating Agent",
            "Cleanser",
            "Coating Agent",
            "Co-Emulsifier",
            "Conditioner",
            "Dispersing Agent",
            "Dye/Pigment",
            "Effect Pigment",
            "Emollient",
            "Emulsifier",
            "Exfoliant",
            "Filler",
            "Film Former",
            "Fixative",
            "Fragrance",
            "Humectant",
            "Neutralizing Agent",
            "Opacifier",
            "Others",
            "Pearlizer",
            "Preservative",
            "Preservative Booster",
            "Rheology Modifier",
            "Skin Sensory Additive",
            "Solubilizer",
            "Solvent",
            "SPF Booster",
            "Stabilizer",
            "Styling Polymer",
            "Sun Filter",
            "Texturizer",
            "Visual Carrier"]
    elif business_line == 'PHI':
        selection_list = [
            "Adjuvant",
            "Analgesics",
            "Anesthetics",
            "Anti-aging / Oxidant / Cancer / Inflammatory",
            "Antibacterials",
            "Antibiotic",
            "Anticonvulsants",
            "Antidementia Agents",
            "Antidepressants",
            "Antidotes, Deterrents, and Toxicologic Agents",
            "Antiemetics",
            "Antifungals",
            "Antigout Agents",
            "Anti-inflammatory Agents",
            "Antimigraine Agents",
            "Antimyasthenic Agents",
            "Antimycobacterials",
            "Antineoplastics",
            "Antiparasitics",
            "Antiparkinson Agents",
            "Antipsychotics",
            "Antispasticity Agents",
            "Antivirals",
            "Anxiolytics",
            "Binder",
            "Biological Buffers",
            "Blood Glucose Regulators",
            "Blood Products/Modifiers/Volume Expanders",
            "Bone and Joint management",
            "Botanicals",
            "Buffer, pH Adjustment",
            "Building Block",
            "Bulking Agent",
            "Carbohydrate Sources",
            "Cardiovascular Agents",
            "Cardiovascular Health",
            "Carrier",
            "Catalyst",
            "Central Nervous System Agents",
            "Cleanroom Disinfectants",
            "Cognitive Health",
            "Coloring",
            "Controlled Release Matrix",
            "Coupling Reagent",
            "Denaturants",
            "Dental and Oral Agents",
            "Dermatological Agents",
            "Diluent, Filler",
            "Disinfection",
            "Disintegrant",
            "Emollient",
            "Emulsifier",
            "Enzyme Replacements/Modifiers",
            "Enzymes",
            "Eye Health",
            "Feed Additive",
            "Fermentation & Cell culture",
            "Fertility Control",
            "Gastrointestinal Agents",
            "General Health",
            "Genitourinary Agents",
            "Growth Factors",
            "Gut Health",
            "Hormones & Steroids",
            "Immune System",
            "Immunological Agents",
            "Inflammatory Bowel Disease Agents",
            "Kryoprotectant",
            "Mental Health and Mood Improvement",
            "Metabolic Bone Disease Agents",
            "Minerals and Nutrients",
            "mRNA Raw Material",
            "Ophthalmic Agents",
            "Peptones",
            "Pest Control",
            "pH Adjusters",
            "Plasticizer",
            "Pre-, Pro- and Postbiotics",
            "Preservative",
            "Protecting Group",
            "Recombinant Proteins and Cytokines",
            "Reporter",
            "Respiratory Tract Agents",
            "Sedatives/Hypnotics",
            "Skeletal Muscle Relaxants",
            "Skin, Nails, Hair",
            "Solubilizer",
            "Sports Nutrition",
            "Sugars",
            "Surfactant",
            "Sweetener",
            "Tablet Coating",
            "Taste Improvement, Taste Masking",
            "Therapeutic Nutrients/Minerals/Electrolytes",
            "Thickener, Viscosity Modifier",
            "Tonicidic Modifier",
            "Vaccine",
            "Vitamins and Minerals",
            "Weight and Diabetes Management",
            "Women and Men Wellness",
            "Yeast Extracts"]
    elif business_line == 'SCI':
        selection_list = [
            "ADDITIVES - Adhesion Promoter",
            "ADDITIVES - Adsorbent",
            "ADDITIVES - Anti-freezing Agent",
            "ADDITIVES - Anti-Graffiti",
            "ADDITIVES - Antioxidant",
            "ADDITIVES - Antiscratch",
            "ADDITIVES - Antistatic",
            "ADDITIVES - Biocide",
            "ADDITIVES - Catalyst/Crosslinker",
            "ADDITIVES - Coalescent",
            "ADDITIVES - Corrosion Inhibitor",
            "ADDITIVES - Coupling Agent/Chain Extender",
            "ADDITIVES - Dispersing Agent",
            "ADDITIVES - Drier",
            "ADDITIVES - Emulsifier",
            "ADDITIVES - Flame Retardant",
            "ADDITIVES - Intermediate & Accelerator",
            "ADDITIVES - Matting Agent",
            "ADDITIVES - Optical Material",
            "ADDITIVES - Other",
            "ADDITIVES - Oxidant",
            "ADDITIVES - Photoinitiator",
            "ADDITIVES - Reagent",
            "ADDITIVES - Rheology Modifier",
            "ADDITIVES - Semiconductor Material",
            "ADDITIVES - Stabiliser",
            "ADDITIVES - Surface Modifier/Defoamer",
            "ADDITIVES - Tower Packing",
            "ADDITIVES - UV Absorber",
            "ADDITIVES - Water Repellent",
            "ADDITIVES - Water Scavenger",
            "ADDITIVES - Wax",
            "ADDITIVES - Wetting Agent",
            "BINDERS - Acrylic Dispersion",
            "BINDERS - Acrylic Emulsion",
            "BINDERS - Acrylic Resin",
            "BINDERS - Aldehyde Resin",
            "BINDERS - Alkyd Resin",
            "BINDERS - Alkyd Resin (Emulsifiable)",
            "BINDERS - Alkyl Polysilicate Resin",
            "BINDERS - Amino/Melamine/Urea Resin",
            "BINDERS - Chlorinated Rubber",
            "BINDERS - Epoxy Resin",
            "BINDERS - Fluorinated Resin",
            "BINDERS - Gum Rosin Ester",
            "BINDERS - Hydrocarbon Resin",
            "BINDERS - Ketone Resin",
            "BINDERS - Nitrocellulose Resin",
            "BINDERS - Other",
            "BINDERS - Phenolic Resin",
            "BINDERS - Polyaldehydes/Polyketone",
            "BINDERS - Polyamide",
            "BINDERS - Polychloroprene",
            "BINDERS - Polyester",
            "BINDERS - Polyisocyanate",
            "BINDERS - Polyurethane/Polyaspartic",
            "BINDERS - Polyurethane Dispersion",
            "BINDERS - Redispersable Powder",
            "BINDERS - Styrene Butadiene Rubber Emulsion",
            "BINDERS - Silane Terminated Polyether",
            "BINDERS - Silicone Resin",
            "BINDERS - Styrene-Acrylic Dispersion",
            "BINDERS - UV Binder & Oligomer",
            "BINDERS - Vinyl Acetate Emulsion",
            "BINDERS - Vinyl Resin",
            "BINDERS - Vinyl-Veova Dispersion",
            "PIGMENTS - Aluminum Pigment",
            "PIGMENTS - Anticorrosive Pigment",
            "PIGMENTS - Cadmium Pigment",
            "PIGMENTS - Carbon Black",
            "PIGMENTS - Complex Inorganic Pigment",
            "PIGMENTS - Dye",
            "PIGMENTS - Fluorescent Pigment",
            "PIGMENTS - Functional Dye",
            "PIGMENTS - Iron Oxide",
            "PIGMENTS - Lead Chrome Pigment",
            "PIGMENTS - Opacifier/Filler",
            "PIGMENTS - Organic Pigment",
            "PIGMENTS - Other",
            "PIGMENTS - Pearlescent Pigment",
            "PIGMENTS - Phosphorescent Pigment",
            "PIGMENTS - Photochromic/Thermochromic Pigment",
            "PIGMENTS - Titanium Dioxide",
            "PIGMENTS - Ultra Marine Blue",
            "POLYMERS - Acrylonitrile Butadiene Styrene",
            "POLYMERS - Butyl Rubber",
            "POLYMERS - Ethylene Propylene Diene Monomer",
            "POLYMERS - Ethylene Vinyl Acetate",
            "POLYMERS - Fluoropolymer",
            "POLYMERS - Natural Rubber",
            "POLYMERS - Nitrile Butadiene Rubber",
            "POLYMERS - Other",
            "POLYMERS - Polybutylene Terephthalate",
            "POLYMERS - Polycarbonate",
            "POLYMERS - Polyamide",
            "POLYMERS - Polybutadiene",
            "POLYMERS - Polyester/Polyethylene Terephthalate",
            "POLYMERS - Polymer Producers/Rheology Modifier",
            "POLYMERS - Polyolefin",
            "POLYMERS - Polystyrene",
            "POLYMERS - Polyoxymethylene",
            "POLYMERS - Polyphenylenesulfide",
            "POLYMERS - Polyvinyl Chloride",
            "POLYMERS - Stylene Acrylonitrille Copolymer",
            "POLYMERS - Styrene Butadiene Rubber",
            "POLYMERS - Styrene Butadiene Styrene/Styrene Ethylene Butylene Styrene",
            "POLYMERS - Silicone Rubber",
            "POLYMERS - Thermoplastic Polyurethane",
            "POLYMERS - Unsaturated Polyester",
            "Polyurethane Foam",
            "Raw Material for Electronics",
            "SOLVENTS - Base Oils & Plasticizer",
            "SOLVENTS - Cleaner/Detergent",
            "SOLVENTS - Cosolvent",
            "SOLVENTS - Diluent",
            "SOLVENTS - Other"]

    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are an expert data‐flagging assistant for technical product dossiers.
    Analyze only the provided details for product “{product_name}” from manufacturer “{manufacturer_name}” (parsed_text, any images, and optional searched_text) 
    and determine, for each function category in the selection list, whether the product exhibits that function.
    Also give reason or example why you select each of the function.

    # RULE #
    RULE1: Only select if it is related to the data mentioned in the given document.
    RULE2: Only select if you are atleast 95% sure, no guessing.

    # REASONING #
    Provide short and concise reason why you select each option, Where is it mentioned in the document that make you select this option.
    Your reason format should be "Selected xxx because the mention of yyy in the document" or explanation similar to this.

    # OUTPUT FORMAT #
    {{
        "function1": boolean,
        "function2": boolean,
        ...
        "reason": string
    }}
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user","content": parsed_text},
        {"role": "user", "content": searched_text}]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({"role": "user", 
                         "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]})
    # CONSTRUCT BODY
    properties = {name: {"type": "boolean", "description": f"True if the product exhibits {name} as the function"} for name in selection_list}
    properties['reason'] = {"type": "string", "description": "Reasoning for each option selected, grounded from given document"}
    required   = list(selection_list) + ['reason']
    json_schema = {
        "name": "flags_only",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False}}
    # FULL REQUEST BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
    return body


def PIM_buildBodySelectApplication(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # SELECTION LIST
    if business_line == 'FBI':
        selection_list = [
            "Alcoholic Beverage",
            "Baby Food",
            "Beverage",
            "Biscuit",
            "Bread, Cakes & Pastries, Frozen Dough",
            "Breakfast Cereals/Bars",
            "Confectionery",
            "Dairy",
            "Desserts & Ice Cream",
            "Dressing",
            "Edible Oils",
            "Fruit & Vegetables",
            "Meals Replacement",
            "Meat Products",
            "Noodles",
            "Nutraceuticals - Capsules",
            "Nutraceuticals - Drinks",
            "Nutraceuticals - Effervescent",
            "Nutraceuticals - Granules",
            "Nutraceuticals - Gummies",
            "Nutraceuticals - Oral Dispersible",
            "Nutraceuticals - Pellets",
            "Nutraceuticals - Powders",
            "Nutraceuticals - Soft-Gel Capsules",
            "Nutraceuticals - Solutions",
            "Nutraceuticals - Suspensions",
            "Nutraceuticals - Syrups",
            "Nutraceuticals - Tablets",
            "Other",
            "Plant-Based Dairy Alternative",
            "Plant-Based Meat Alternative",
            "Processed Food",
            "Sauces",
            "Seasonings",
            "Snacks (Salty)",
            "Soup",
            "Sweet Snack"]
    elif business_line == 'PCI':
        selection_list = [
            "Air Care",
            "Antiperspirants & Deodorants",
            "Baby Care",
            "Bath & Toilet Cleaner",
            "Car Care",
            "Color Care",
            "Dishwashing",
            "Fabric care",
            "Floor & Surface Cleaner",
            "Fragrance",
            "Hair Care",
            "Household Polishes",
            "Insect Care",
            "Institutional Cleaner",
            "Institutional Laundry",
            "Laundry",
            "Oral Care",
            "Others",
            "Skin Care",
            "Soap & Bath",
            "Spa & Wellness",
            "Sun Care"]
    elif business_line == 'PHI':
        selection_list = [
            "Amino Acid",
            "Animal Health",
            "Animal Nutrition",
            "Biochemical & Reagent",
            "Biological Buffer & Denaturant",
            "Capsules",
            "Carbohydrate & Sugar",
            "Cell Culture Supplement",
            "Clean Room Management",
            "Cream-based Ointment",
            "Dental",
            "Drinks",
            "Effervescent",
            "Enzyme",
            "Gel-based Ointment",
            "Granules",
            "Gummies",
            "Inhalation",
            "Injectables and Parenterals",
            "Lipid",
            "Liposomes",
            "Medical Devices",
            "Microspheres",
            "Mineral & Nutrient",
            "mRNA Research",
            "Nasal",
            "Nucleosides and Derivatives",
            "Ophthalmic",
            "Oral",
            #"Oral Disperable Dosage Forms",
            "Oral Dispersible",
            "Pellets",
            "Peptone & Yeast Extract",
            "Plasticizer",
            "Powder",
            "Primary Packaging",
            "Probiotic",
            "Protecting Group",
            "Reagent",
            "Recombinant Proteins and Cytokines",
            "Soft-gel Capsules",
            "Solubilizer",
            "Solutions",
            "Supositries",
            "Suspensions",
            "Sweetener",
            "Synthesis",
            "Syrups",
            "Tablet Coating",
            "Tablets",
            "Taste Improvement, Taste Masking",
            "Thickener, Viscosity Modifier",
            "Topical",
            "Vaccines",
            "Weight Management"]
    elif business_line == 'SCI':
        selection_list = [
            "Bristles",
            "Ceramics",
            "Electronic Chemicals",
            "Fine Chemicals & Custom Synt.",
            "Lubricants",
            "Medical Application",
            "Mining",
            "Others",
            "Plant & Crop Protection",
            "Petrochemicals",
            "Adhesives & Sealants",
            "Architectural and Deco.",
            "Automotive Paints",
            "Can, Coil and Industrial",
            "Construction",
            "Printing Inks",
            "Lamination and Converting",
            "Powder Coating",
            "Fibers, Textiles & Films",
            "Masterbatch & Compounders",
            "Polymer Producers",
            "Rubber & Elastomers",
            "Thermosets & Composites",
            "Thermoplastic Transformers"]

    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are an expert data‐flagging assistant for technical product dossiers.
    Analyze only the details provided for product “{product_name}” from manufacturer “{manufacturer_name}” (including parsed text, any images, and optional searched text).
    The product name might be the specific brand-name, in that case, you can determine the application from the ingredients/composition instead.
    Use the given documentation combine with your knowledge to determine, for each application category in the selection list, whether the product is related to that application.
    Also give reason or example why you select each of the application.

    # RULE #
    RULE1: Only select if it is related to the data mentioned in the given document.
    RULE2: Only select if you are atleast 95% sure, no guessing.

    # REASONING #
    Provide short and concise reason why you select each option, Where is it mentioned in the document that make you select this option.
    Your reason format should be "Selected xxx because the mention of yyy in the document" or explanation similar to this.

    # OUTPUT FORMAT #
    {{
        "application1": boolean,
        "application2": boolean,
        ...
        "reason": string
    }}

    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user","content": parsed_text},
        {"role": "user", "content": searched_text}]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({"role": "user", 
                         "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]})
    # CONSTRUCT BODY
    properties = {name: {"type": "boolean", "description": f"True if the product includes {name} as application"} for name in selection_list}
    properties['reason'] = {"type": "string", "description": "Reasoning for each option selected, grounded from given document"}
    required   = list(selection_list) + ['reason']
    json_schema = {
        "name": "flags_only",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False}}
    # FULL REQUEST BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
    return body


def PIM_buildBodyFindCASNumber(parsed_text, product_name, manufacturer_name, ls_base64, searched_text=''):
    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are a data extraction agent that processes technical documents and extracts information.
    Based on the provided text and images, focus only on product [{product_name}] from manufacturer [{manufacturer_name}].
    Try to find any CAS Registry Number mentioned in the content. If none is found, output "N/A".

    # RULE #
    RULE1: Only output if data mentioned in the given document.
    RULE2: Only output if you are atleast 95% sure, no guessing.

    # OUTPUT FORMAT #
    {{
        "cas_number": string,
        "reason": string
    }}
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": parsed_text},
        {"role": "user", "content": searched_text}
    ]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # CONSTRUCT BODY
    properties = {}
    properties['cas_number'] = {"type": "string", "description": "The CAS Registry Number found in the document, or 'N/A' if none is present"}
    properties['reason'] = {"type": "string", "description": "Reasoning or explanation for the CAS number extracted, grounded from given document"}
    required  = ['cas_number','reason']
    json_schema = {
        "name": "cas_number_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False}}
    # FULL REQUEST BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
    return body


def PIM_buildBodyFindPhysicalForm(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # Define mapping of business lines to industry clusters
    if business_line == 'FBI':
        selection_list = [
            "Block",
            "Deep Frozen",
            "Dispersion",
            "Diverse",
            "Emulsion",
            "Flakes",
            "Gel",
            "Granule",
            "Liquid",
            "Micronized Powder",
            "Nano Particle",
            "Other",
            "Paste",
            "Pieces",
            "Powder",
            "Suspension",
            ""]
    elif business_line == 'PCI':
        selection_list = [
            "Bead",
            "Block",
            "Dispersion",
            "Emulsion",
            "Flakes",
            "Gas",
            "Gel",
            "Granule",
            "Liquid",
            "Micronized Powder",
            "Nano",
            "Others",
            "Paste",
            "Powder",
            "Sponge",
            "Suspension",
            "Wax",
            ""]
    elif business_line == 'PHI':
        selection_list = [
            "Solid",
            "Dispersion",
            "Emulsion",
            "Flakes",
            "Gel",
            "Granule",
            "Liquid",
            "Micronized Powder",
            "Nano",
            "Paste",
            "Powder",
            "Semi-Solid",
            "Suspension",
            "Fiber & Stainless Steel",
            ""]
    elif business_line == 'SCI':
        selection_list = [
            "Dispersion",
            "Emulsion",
            "Liquid",
            "Micronized powder",
            "Nano powder",
            "Paste",
            "Solid",
            ""]
    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are a data extraction agent that processes technical documents and extracts information.
    Based on the provided text and images, focus only on product [{product_name}] from manufacturer [{manufacturer_name}].
    Select the correct PHYSICAL_FORM of this specific product. If none is found, output "".

    # RULE #
    RULE1: Only select if it is related to the data mentioned in the given document.
    RULE2: Only select if you are atleast 95% sure, no guessing.

    # REASONING #
    Provide short and concise reason why you select this option, Where is it mentioned in the document that make you select this option.
    Your reason format should be "Selected xxx because the mention of yyy in the document" or explanation similar to this.

    # OUTPUT FORMAT #
    {{
        "physical_form": string,
        "reason": string
    }}
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": parsed_text},
        {"role": "user", "content": searched_text}
    ]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })

    # CONSTRUCT BODY
    properties = {}
    properties['physical_form'] = {"type": "string",
                                   "enum": selection_list,
                                   "description": f"Select PHYSICAL_FORM of the product [{product_name}]. If none is found, output 'N/A'."}
    properties['reason'] = {"type": "string","description": "Reason why you select the PHYSICAL_FORM, grounded from given document"}
    json_schema = {
        "name": "physical_form_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": ["physical_form","reason"],
            "additionalProperties": False}}
    # FULL REQUEST BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
    return body

def PIM_buildBodyGetProductDescription(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION V1 #
    You are a data extraction agent that processes technical documents and extracts information.
    Based on the provided text and images, focus only on product [{product_name}] from manufacturer [{manufacturer_name}].
    The Description should begin with the product name and be at least Minimum 75 characters and maximum 400 characters in length.
    The Description may include information such as the product’s physical form and composition. 
    It can also highlight the product’s strengths, potential benefits, and relevant applications.
    When generate the description, Do not repeat the content, use easy to understand wordings.

    # RULE V1 #
    Only create description from given data/document, dont use data outside of the given data/document

    # OUTPUT FORMAT #
    {{
        "product_description": string
    }}
    """
    # BL SPECIFIC
    if business_line == 'FBI':
        add_prompt = """
        # FEEDBACK FROM OLD INSTRUCTION V1, USE TO IMPROVE GENERATION #
        The sentence is a little too long and may lose the focus of the reader. Prefer the context to be focused on the food industry 
        """
    elif business_line == 'PCI':
        add_prompt = """
        # FEEDBACK FROM OLD INSTRUCTION V1, USE TO IMPROVE GENERATION #
        Only that this is too lengthy, not sure if the customer will read through all of this. If we compare it to other famous marketplaces we may consider decreasing.
        """
    elif business_line == 'PHI':
        add_prompt = """
        # FEEDBACK FROM OLD INSTRUCTION V1, USE TO IMPROVE GENERATION #
        No specific concern, good as it is. As long as the user does not need to write it themselves.
        """
    elif business_line == 'SCI':
        add_prompt = """
        # FEEDBACK FROM OLD INSTRUCTION V1, USE TO IMPROVE GENERATION #
        The longer the sentence occurs in TDS, the more he believes that the description will be as follows, and no need to repeat.
        """
        system_prompt += add_prompt
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": parsed_text},
        {"role": "user", "content": searched_text}]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                             "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # CONSTRUCT BODY
    properties = {}
    properties['product_description'] = {"type": "string",
                                         "description": """
                                          The Description should begin with the product name and be at least Minimum 75 characters and maximum 400 characters in length.
                                          The Description may include information such as the product’s physical form and composition. 
                                          It can also highlight the product’s strengths, potential benefits, and relevant applications.
                                          When generate the description, Do not repeat the content, use easy to understand wordings."""}
    required = ['product_description']
    json_schema = {
        "name": "product_description_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False}}
    # FULL REQUEST BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
    return body

def PIM_buildBodyGetRecommendedDosage(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are a data extraction agent that processes technical documents and extracts information.
    Based on the provided text and images, focus only on product [{product_name}] from manufacturer [{manufacturer_name}].
    Try to find any recommended dosage instructions mentioned in the content. This may include dosage amount, units, dosage frequency, or administration route.
    Do not include any labels, section headers, or explanatory phrases such as "example", "usage", "incorporation", etc.
    Output only the clean dosage text as it appears, preserving context + dosage together.
    If none is found, output "N/A".

    # RULE #
    RULE1: Only select if it is in the given document.
    RULE2: Only select if you are atleast 95% sure, no guessing.

    # REASONING #
    Provide short and concise reason why you show this recommended dosage, Where is it mentioned in the document.
    Your reason format should be "Dosage is xxx because it's mentioned yyy in the document" or explanation similar to this.

    # OUTPUT FORMAT #
    {{
        "recommended_dosage": string,
        "reason": string
    }}
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": parsed_text},
        {"role": "user", "content": searched_text}]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                             "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # CONSTRUCT BODY
    properties = {}
    properties['recommended_dosage'] =  {"type": "string",
                                        "description": "The recommended dosage found in the document, or 'N/A' if none is present"}
    properties['reason'] =  {"type": "string",
                             "description": "The reason for the recommended dosage, or 'N/A' if none is present, grounded from given document"}
    required  = ['recommended_dosage','reason']
    json_schema = {
        "name": "recommended_dosage_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False}}
    # FULL REQUEST BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
    return body

def PIM_buildBodySelectCertifications(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # SELECTION LIST
    if business_line == 'FBI':
        selection_list = [
            "ISO",
            "ASC",
            "BIO",
            "BRC",
            "CODEX, JECFA",
            "EFSA",
            "FAMI-QS",
            "FSSC",
            "GMP",
            "GRAS, FEMAGRAS",
            "HACCP",
            "HALAL, JAKIM, MUI",
            "IFS",
            "Kosher",
            "MSC",
            "Vegan"]
    elif business_line == 'PCI':
        selection_list = [
            "China Compliant",
            "COSMOS Standard",
            "CSCA",
            "EPA",
            "Fair Trade / Fair For Life",
            "FDA",
            "HALAL",
            "ISCC / ISCC PLUS",
            "JSQI",
            "Kosher",
            "NATRUE Standard",
            "Natural Cosmetic",
            "Nordic Swan Ecolabel",
            "NPA",
            "Organic",
            "REACH",
            "Sustainable Palm Oil",
            "U.S. EPA",
            "USP",
            "Vegan"]
    elif business_line == 'PHI':
        selection_list = [
            "CEP",
            "DMF",
            "EP",
            "FAMI-QS",
            "GMP",
            "Halal",
            "JP",
            "Kosher",
            "USP/NF"]
    elif business_line == 'SCI':
        selection_list = [
            "AICS",
            "ASIA-PAC",
            "BgVV Approval",
            "China (CRC/SEPA)",
            "DLS",
            "DSL",
            "ECL",
            "EINECS",
            "ENCS",
            "FDA",
            "FOOD CONTACT",
            "JAPAN (Low Volume)",
            "NA",
            "NDSL",
            "NEW ZEALAND",
            "NOR:ECOC9400131A",
            "NZIoC",
            "PICCS",
            "REACH",
            "TSCA"]       

    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are a data extraction agent that processes technical documents and extracts information.
    Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].   
    Select as much as possible CERTIFICATIONS but only those related to the product [{product_name}] from the following list:{selection_list}

    # RULE #
    RULE1: Only select if it is related to the data mentioned in the given document.
    RULE2: Only select if you are atleast 95% sure, no guessing.

    # REASONING #
    Provide short and concise reason why you select each option, Where is it mentioned in the document that make you select this option.
    Your reason format should be "Selected xxx because the mention of yyy in the document" or explanation similar to this.

    # OUTPUT FORMAT #
    {{
        "certification1": boolean,
        "certification2": boolean,
        ...
        "reason": string
    }}
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user","content": parsed_text},
        {"role": "user", "content": searched_text}]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # CONSTRUCT BODY
    properties = {name: {"type": "boolean", "description": f"True if the products has {name}"} for name in selection_list}
    properties['reason'] = {"type": "string", "description": "Reasoning for each option selected, grounded from given document"}
    required   = list(selection_list) + ['reason']
    json_schema = {
        "name": "flags_only",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False}}
    # FULL REQUEST BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
    return body


def PIM_buildBodySelectClaims(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # Define mapping of business lines to industry clusters
    if business_line == 'FBI':
        selection_list = [
            'Bio-Fermentation',
            'Meat & Dairy Alternative',
            'Natural & Ethically Sourced',
            'Resource & Energy Optimization',
            'Sustainable Food Waste Reduction',
            'Upcycled'
        ]
    elif business_line == 'PCI':
        selection_list = [
            'Anti-Aging',
            'Anti-Bacterial',
            'Anti-Cellulite',
            'Anti-Dandruff',
            'Anti-Dark Circles',
            'Anti-Fatigue',
            'Anti-Frizz',
            'Anti-Inflammatory',
            'Anti-Itching',
            'Anti-Microbial',
            'Anti-Oxidant',
            'Anti-Pollution',
            'Anti-Stress',
            'Anti-Stretch Mark',
            'Anti-Virus',
            'Anti-Wrinkle',
            'Blue Light Protection',
            'Brightening',
            'Conditioning',
            'Cooling/Warming Effect',
            'COSMOS Standard',
            'Curl Retention',
            'Elasticity',
            'Fair Trade / Fair For Life',
            'Film Forming',
            'Firming',
            'Free Radical Scavenger',
            'Gene Expression Modulation',
            'Hair Color Protection',
            'Hair Loss Reduction',
            'Hair Radiance',
            'Hair Repair',
            'Hair Volume',
            'Immuno Modulation',
            'Insect Repellent',
            'ISCC',
            'Lifting',
            'Mattifying',
            'Microbiome Balance',
            'Moisturizing',
            'NATRUE Standard',
            'Natural Cosmetic',
            'Nordic Swan Ecolabel',
            'Nourishing',
            'Odor Masking',
            'Organic',
            'Pore Refiner',
            'Purifying',
            'Redness Reduction',
            'Relaxer',
            'Safer Choice',
            'Scalp Protection',
            'Sculpting',
            'Sebum Control',
            'Skin Barrier Function',
            'Skin Radiance',
            'Skin Renewal',
            'Skin Repair',
            'Smoothing',
            'Soft Focus',
            'Soothing',
            'Strengthening',
            'Sustainable Palm Oil',
            'Texturizer',
            'UV Protection',
            'Vegan',
            'Wound Healing'
        ]
    elif business_line == 'PHI':
        selection_list = [
            'Animal Derived Component Free (ADCF)',
            'Biodegradable',
            'Bio-Fermentation',
            'Circularity',
            'Environmentally Sustainable Pharmaceutical Manufacturing',
            'Free from Nitrosamine Impurities',
            'Free from Solvents Class 1',
            'Organic',
            'Plant-Based (Min. 80%)',
            'Sustainable Palm Oil'
        ]
    elif business_line == 'SCI':
        selection_list = [
            'Bio-Based',
            'Biodegradable',
            'Bioplastic',
            'Circularity',
            'EcoTain Label',
            'Emission Control',
            'Low VOC',
            'Solvent Free Alternatives',
            'VOC Free'
        ] 
    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are an expert data‐extraction assistant for technical product dossiers.
    Analyze only the provided details for product “{product_name}” from manufacturer “{manufacturer_name}” (parsed_text, any images, and optional searched_text) 
    and identify which of the following claims apply.
    Also give reason or example why you select each of the claims.

    # RULE #
    RULE1: Only select if it is related to the data mentioned in the given document.
    RULE2: Only select if you are atleast 95% sure, no guessing.

    # REASONING #
    Provide short and concise reason why you select each option, Where is it mentioned in the document that make you select this option.
    Your reason format should be "Selected xxx because the mention of yyy in the document" or explanation similar to this.

    # OUTPUT FORMAT #
    {{
        "claim1": boolean,
        "claim2": boolean,
        ...
        "reason": string
    }}

    """
    # BL SPECIFIC
    if business_line == 'FBI':
        system_prompt += 'Only select claims that is really found to be related to the the given data, no guessing \n'
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user","content": parsed_text},
        {"role": "user", "content": searched_text}]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({"role": "user", 
                         "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]})
    # CONSTRUCT BODY
    properties = {name: {"type": "boolean", "description": f"True if the product claims to exhibits {name}"} for name in selection_list}
    properties['reason'] = {"type": "string", "description": "Give reason or example why you select each of the claims, grounded from given document"}
    required   = list(selection_list) + ['reason']
    json_schema = {
        "name": "flags_only",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False}} 
    # Full request body
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
    return body


def PIM_buildBodySelectHealthBenefits(parsed_text, product_name, manufacturer_name, ls_base64, searched_text=''):
    selection_list = [
        "Anti-aging, Antioxidant, Anti-Cancer, Anti-Inflammatory",
        "Bone and Joint management",
        "Botanicals",
        "Cardiovascular health",
        "Cognitive health",
        "Diabetes/Blood Sugar Management",
        "Eye health",
        "General Health",
        "Gut health",
        "Immune system",
        "Mental health and mood improvement",
        "Pre, Pro and Postbiotics",
        "Skin, Nails, Hair",
        "Sports nutrition",
        "Vitamins and Minerals",
        "Weight Management",
        "Women and Men wellness"]
    # SYSTEM PROMPT
    system_prompt = f"""
    # INSTRUCTION #
    You are a data extraction agent that processes technical documents and extracts information.
    Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].   
    Use the given data combine with your own knowledge to select as much as possible RECOMMENDED_HEALTH_BENEFITS but only those related to the product [{product_name}] from the following list:{selection_list}

    # RULE #
    RULE1: Only select if it is related to the data mentioned in the given document.
    RULE2: Only select if you are atleast 95% sure, no guessing.

    # REASONING #
    Provide short and concise reason why you select each option, Where is it mentioned in the document that make you select this option.
    Your reason format should be "Selected xxx because the mention of yyy in the document" or explanation similar to this.

    # OUTPUT FORMAT #
    {{
        "rec_health_benefits1": boolean,
        "rec_health_benefits2": boolean,
        ...
        "reason": string
    }}
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user","content": parsed_text},
        {"role": "user", "content": searched_text}]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # CONSTRUCT BODY
    properties = {name: {"type": "boolean", "description": f"True if the product is recommended for {name}"} for name in selection_list}
    properties['reason'] = {"type": "string", "description": "Give reason or example why you select the health benefits are recommended for the product, grounded from given document"}
    required   = list(selection_list) + ['reason']
    json_schema = {
        "name": "flags_only",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False}}
    # FULL REQUEST BODY
    body = {
        "model": "gpt-4.1-mini",
        "messages": messages,
        "temperature": 0,   
        "max_tokens": 1024*16,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema}}
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

def v1_saveUploadFilesTemporarlyB64(inputListDocumentationB64):
    if not inputListDocumentationB64:
        return []
    # Sort input list by Base64 string length (ascending)
    sorted_b64_list = sorted(inputListDocumentationB64, key=len)
    lsTempFile = []
    for b64data in sorted_b64_list:
        if not b64data:
            continue  # skip empty strings
        # Generate deterministic hash-based filename
        hash_name = hashlib.sha256(b64data.encode("utf-8")).hexdigest()
        filename = f"{hash_name}.pdf"
        # Decode Base64 and write to temp directory
        pdf_bytes = base64.b64decode(b64data)
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        with open(temp_path, "wb") as tmp:
            tmp.write(pdf_bytes)
        lsTempFile.append({
            "filename": filename,
            "temp_path": temp_path
        })
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
    mainDict['gpt_cas_from_doc_reason'] = None
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

def v1_getProductNameAndSupplierFromTextAndImage(mainDict):
    parsed_text = mainDict['stg_parsedText']
    ls_base64 = mainDict['stg_lsBase64']
    # CALL API
    body = PIM_buildBodyGetProductNameAndSupplierFromTextAndImage(parsed_text, ls_base64)
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0: return rescontent['products_and_suppliers']
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_getProductNameAndSupplierFromTextAndImage')

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

def v1_searchComposition(mainDict):
    if mainDict['inputWebSearch']==True:
        # BUILD BODY + CALL API
        inputProductName = mainDict['inputProductName']
        gpt_manufacturer_or_supplier_answer = mainDict['gpt_manufacturer_or_supplier_answer']
        question = f"""
        What are the COMPOSITIONS of [{inputProductName}] from manufacturer [{gpt_manufacturer_or_supplier_answer}], like what is it made from? or the raw material used?
        If there is no information available, Just return "No information available on Internet", do not list any composition, ingredient, or raw material.
        If there is information avaliable, list the composition,ingredient, or raw material used in the product.
        Use exact product name [{inputProductName}] and manufacturer name [{gpt_manufacturer_or_supplier_answer}] in the search.
        """
        body = {"model": "gpt-4o-mini-search-preview",
                'web_search_options': {'search_context_size': 'low'},
                "messages": [{'role': 'user', 
                            'content': question}],
                "max_tokens": 4096*2}
        url = "https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai"
        params = {"apikey": os.getenv('OPENAI_API_KEY')}
        api_error, response, rescontent = v1_customCallAPI(url, body, headers={}, params=params)
        # SAVE RESULT
        if api_error == 0: return rescontent
        else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_searchComposition')
    else: return ''

def v1_searchFunction(mainDict):
    if mainDict['inputWebSearch']==True:
        # BUILD BODY + CALL API
        inputProductName = mainDict['inputProductName']
        stg_businessLineStr = mainDict['stg_businessLineStr']
        question = f"""
        Give me as much information as possible about the FUNCTIONS of [{inputProductName}] utilization in the [{stg_businessLineStr}] industries
        If there is no information available, Just return "No information available on Internet"
        If there is information avaliable, then output data.
        Use exact product name [{inputProductName}] in the search.
        """
        body = {"model": "gpt-4o-mini-search-preview",
                'web_search_options': {'search_context_size': 'low'},
                "messages": [{'role': 'user', 
                            'content': question}],
                "max_tokens": 4096*2}
        url = "https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai"
        params = {"apikey": os.getenv('OPENAI_API_KEY')}
        api_error, response, rescontent = v1_customCallAPI(url, body, headers={}, params=params)
        # SAVE RESULT
        if api_error == 0: return rescontent
        else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_searchFunction')
    else: return ''

def v1_searchApplication(mainDict):
    if mainDict['inputWebSearch']==True:
        # BUILD BODY + CALL API
        inputProductName = mainDict['inputProductName']
        stg_businessLineStr = mainDict['stg_businessLineStr']
        question = f"""
        Give me as much information as possible about the APPLICATIONS of [{inputProductName}] utilization in the [{stg_businessLineStr}] industries
        If there is no information available, Just return "No information available on Internet"
        If there is information avaliable, then output data.
        Use exact product name [{inputProductName}] in the search.
        """
        body = {"model": "gpt-4o-mini-search-preview",
                'web_search_options': {'search_context_size': 'low'},
                "messages": [{'role': 'user', 
                            'content': question}],
                "max_tokens": 4096*2}
        url = "https://ancient-almeda-personal-personal-22e19704.koyeb.app/openai"
        params = {"apikey": os.getenv('OPENAI_API_KEY')}
        api_error, response, rescontent = v1_customCallAPI(url, body, headers={}, params=params)
        # SAVE RESULT
        if api_error == 0: return rescontent
        else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_searchApplication')
    else: return ''

def v1_combineWebSearch(mainDict):
    if mainDict['inputWebSearch']==True:
        searched_text = ''
        searched_text += '### COMPOSITIONS WEB SEARCH RESULTS ###\n'
        searched_text += mainDict['gpt_composition_search_answer'] + '\n\n\n'
        searched_text += '### FUNCTIONS WEB_SEARCH RESULTS ###\n'
        searched_text += mainDict['gpt_function_search_answer'] + '\n\n\n'
        searched_text += '### APPLICATIONS WEB_SEARCH RESULTS ###\n'
        searched_text += mainDict['gpt_application_search_answer'] + '\n\n\n'
        return searched_text
    else:
        return ''
    
def v1_getTextOfThisProductOnly(mainDict):
    # CALL API
    body = PIM_buildBodyGetProductInfo(mainDict['stg_parsedText'], 
                                       mainDict['inputProductName'], 
                                       mainDict['gpt_manufacturer_or_supplier_answer'], 
                                       mainDict['stg_lsBase64'], 
                                       mainDict['gpt_combined_web_search'])
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0: return str(rescontent)
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_getTextOfThisProductOnly')

def v1_selectIndustryCluster(mainDict):
    # CALL API
    lsBase64 = []
    body = PIM_buildBodySelectIndustryCluster(mainDict['gpt_text_of_this_product_only_answer'], 
                                              mainDict['inputProductName'],
                                              mainDict['gpt_manufacturer_or_supplier_answer'],
                                              lsBase64,
                                              mainDict['inputBusinessLine'],
                                              mainDict['gpt_combined_web_search'])
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0: return [k for k, v in rescontent.items() if v is True], rescontent['reason']
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_selectIndustryCluster')

def v1_selectCompositions(mainDict):
    # CALL API
    lsBase64 = []
    body = PIM_buildBodySelectComposition(mainDict['gpt_text_of_this_product_only_answer'], 
                                          mainDict['inputProductName'],
                                          mainDict['gpt_manufacturer_or_supplier_answer'],
                                          lsBase64,
                                          mainDict['inputBusinessLine'],
                                          mainDict['gpt_combined_web_search'])
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0:
        if mainDict['inputBusinessLine'] == 'PCI': return [k for k, v in rescontent.items() if v is True], rescontent['reason']
        else: return rescontent['compositions'], rescontent['reason']
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_selectCompositions')

def v1_selectFunctions(mainDict):
    # CALL API
    lsBase64 = []
    body = PIM_buildBodySelectFunction(mainDict['gpt_text_of_this_product_only_answer'], 
                                       mainDict['inputProductName'], 
                                       mainDict['gpt_manufacturer_or_supplier_answer'], 
                                       lsBase64, 
                                       mainDict['inputBusinessLine'], 
                                       mainDict['gpt_combined_web_search'])
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0: return [k for k, v in rescontent.items() if v is True], rescontent['reason']
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_selectFunctions')

def v1_selectApplications(mainDict):
    # CALL API
    lsBase64 = []
    body = PIM_buildBodySelectApplication(mainDict['gpt_text_of_this_product_only_answer'], 
                                          mainDict['inputProductName'], 
                                          mainDict['gpt_manufacturer_or_supplier_answer'], 
                                          lsBase64, 
                                          mainDict['inputBusinessLine'], 
                                          mainDict['gpt_combined_web_search'])
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0: return [k for k, v in rescontent.items() if v is True], rescontent['reason']
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_selectApplications')

def v1_findCASNumber(mainDict):
    # CALL API
    lsBase64 = []
    body = PIM_buildBodyFindCASNumber(mainDict['gpt_text_of_this_product_only_answer'], 
                                      mainDict['inputProductName'], 
                                      mainDict['gpt_manufacturer_or_supplier_answer'], 
                                      lsBase64, 
                                      mainDict['gpt_combined_web_search'])
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0: return rescontent['cas_number'], rescontent['reason']
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_findCASNumber')

def v1_findPhysicalForm(mainDict):
    # CALL API
    lsBase64 = []
    body = PIM_buildBodyFindPhysicalForm(mainDict['gpt_text_of_this_product_only_answer'], 
                                         mainDict['inputProductName'], 
                                         mainDict['gpt_manufacturer_or_supplier_answer'], 
                                         lsBase64, 
                                         mainDict['inputBusinessLine'], 
                                         mainDict['gpt_combined_web_search'])
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0: return rescontent['physical_form'], rescontent['reason']
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_findPhysicalForm')

def v1_genProductDescription(mainDict):
    # CALL API
    lsBase64 = []
    body = PIM_buildBodyGetProductDescription(mainDict['gpt_text_of_this_product_only_answer'], 
                                              mainDict['inputProductName'], 
                                              mainDict['gpt_manufacturer_or_supplier_answer'], 
                                              lsBase64, 
                                              mainDict['gpt_combined_web_search'])
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0: return rescontent['product_description']
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_genProductDescription')

def v1_getRecommendedDosage(mainDict):
    if mainDict['inputBusinessLine'] == 'PHI': 
        return '','For PHI, Recommended dosage to be manually input'
    else:
        # CALL API
        lsBase64 = []
        body = PIM_buildBodyGetRecommendedDosage(mainDict['gpt_text_of_this_product_only_answer'], 
                                                mainDict['inputProductName'], 
                                                mainDict['gpt_manufacturer_or_supplier_answer'], 
                                                lsBase64, 
                                                mainDict['gpt_combined_web_search'])
        url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
        headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
        api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
        # SAVE RESULT
        if api_error == 0: return rescontent['recommended_dosage'], rescontent['reason']
        else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_getRecommendedDosage')

def v1_selectCertifications(mainDict):
    if mainDict['inputBusinessLine'] == 'PHI': 
        return '','For PHI, Certifications to be manually input'
    else:
        # CALL API
        lsBase64 = []
        body = PIM_buildBodySelectCertifications(mainDict['gpt_text_of_this_product_only_answer'], 
                                                mainDict['inputProductName'], 
                                                mainDict['gpt_manufacturer_or_supplier_answer'], 
                                                lsBase64, 
                                                mainDict['inputBusinessLine'], 
                                                mainDict['gpt_combined_web_search'])
        url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
        headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
        api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
        # SAVE RESULT
        if api_error == 0: return [k for k, v in rescontent.items() if v is True], rescontent['reason']
        else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_selectCertifications')

def v1_selectClaims(mainDict):
    # CALL API
    lsBase64 = []
    body = PIM_buildBodySelectClaims(mainDict['gpt_text_of_this_product_only_answer'], 
                                     mainDict['inputProductName'], 
                                     mainDict['gpt_manufacturer_or_supplier_answer'], 
                                     lsBase64, 
                                     mainDict['inputBusinessLine'], 
                                     mainDict['gpt_combined_web_search'])
    url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
    headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
    api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
    # SAVE RESULT
    if api_error == 0: return [k for k, v in rescontent.items() if v is True], rescontent['reason']
    else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_selectClaims')

def v1_selectHealthBenefits(mainDict):
    if mainDict['inputBusinessLine']=='FBI':
        selection_list = ["Dietary Fiber",
                          "Food Culture",
                          "Fortification/Nutraceutical",
                          "Probiotic/Postbiotic",
                          "Protein"]
        lsFunctionsStr = str(mainDict['gpt_select_functions_answer'])
        if any(item in lsFunctionsStr for item in selection_list):
            # CALL API
            lsBase64 = []
            body = PIM_buildBodySelectHealthBenefits(mainDict['gpt_text_of_this_product_only_answer'], 
                                                     mainDict['inputProductName'], 
                                                     mainDict['gpt_manufacturer_or_supplier_answer'], 
                                                     lsBase64, 
                                                     mainDict['gpt_combined_web_search'])
            url = "https://azure-ai-services-main01.cognitiveservices.azure.com/openai/deployments/azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser/chat/completions?api-version=2025-01-01-preview"
            headers = {"Content-Type": "application/json", "api-key": os.getenv('AZURE_OPENAI_KEY')}
            api_error, response, rescontent = v1_customCallAPI(url, body, headers=headers)
            # SAVE RESULT
            if api_error == 0: return [k for k, v in rescontent.items() if v is True], rescontent['reason']
            else: raise HTTPException(status_code=response.status_code, detail='Critical Error: v1_selectHealthBenefits')
        else:
            return [], "No applicable health benefits because product functions not in the required list (Dietary Fiber, Food Culture, Fortification/Nutraceutical, Probiotic/Postbiotic, Protein)"
    return [], "Only applicable for FBI business line"

###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################

def pdf_to_base64(pdf_path):
    with open(pdf_path, "rb") as pdf_file:
        encoded_string = base64.b64encode(pdf_file.read()).decode("utf-8")
    return encoded_string

def base64_to_pdf(b64_string, output_path):
    with open(output_path, "wb") as pdf_file:
        pdf_file.write(base64.b64decode(b64_string))

def load_hist_by_hash(hash_combined, folder='histAPICalls'):
    suffix = f"__{hash_combined}.json"
    # scandir is faster and gives you dir entries directly
    with os.scandir(folder) as it:
        for entry in it:
            # `is_file()` avoids directories; `name` avoids extra stat calls
            if entry.is_file() and entry.name.endswith(suffix):
                with open(entry.path, "r", encoding="utf-8") as f:
                    return json.load(f)
    return None