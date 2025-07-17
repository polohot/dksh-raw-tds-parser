from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

def azureDocumentIntelligenceParsePDF(file_path, key):
    document_intelligence_client = DocumentIntelligenceClient(
        endpoint="https://document-intelligence-free-main01.cognitiveservices.azure.com/", credential=AzureKeyCredential(key))
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

def buildBodyGetProductNameAndSupplierFromTextAndImage(parsed_text, ls_base64):
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {
            "role": "system",
            "content": """
                ### INSTRUCTION ###
                You are a helpful assistant that extracts the name and manufacturer from parsed output of PDF file.
                The parsed file is the Technical Data Sheet of the product.
                Sometime the parsed pdf only have 1 product, sometime could have multiple products.                
                Output the needed data into specific format.

                ### OUTPUT FORMAT ###
                Output as list of json, sample below
                do not put any text before or after the square brackets
                Sample output1: [{"PRODUCT_NAME":"Sugar C1002","SUPPLIER_NAME":"ACME Sugar Malaysia Berhad"}]    
                Sample output2: [{"PRODUCT_NAME":"Mint Concentrate MT2245","SUPPLIER_NAME":"Emmi Switzerland"}]
                Sample output3: [{"PRODUCT_NAME":"iPhone 15 Pro","SUPPLIER_NAME":"Apple Inc."},
                                {"PRODUCT_NAME":"Galaxy S24 Ultra","SUPPLIER_NAME":"Samsung Electronics"}]     
                Sample output4: [{"PRODUCT_NAME":"PlayStation 5","SUPPLIER_NAME":"Sony Interactive Entertainment"},
                                {"PRODUCT_NAME":"Air Jordan 1 Retro High OG","SUPPLIER_NAME":"Nike, Inc."},
                                {"PRODUCT_NAME":"Model 3","SUPPLIER_NAME":"Tesla, Inc."}]   
            """
        },
        {
            "role": "user",
            "content": parsed_text
        }
    ]    

    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    
    # BUILD BODY
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "max_tokens": 1000,
        "temperature": 0.2}
    return body

# def buildQuestionGetProductNameAndSupplierFromParsedText(parsed_output):

#     question = """
#     ### INSTRUCTION ###
#     You are a helpful assistant that extracts the name and manufacturer from parsed output of PDF file.
#     The parsed file is the Technical Data Sheet of the product.
#     Sometime the parsed pdf only have 1 product, sometime could have multiple products.                
#     Output the needed data into specific format.

#     ### OUTPUT FORMAT ###
#     Output as list of json, sample below
#     do not put any text before or after the square brackets
#     Sample output1: [{"PRODUCT_NAME":"Sugar C1002","SUPPLIER_NAME":"ACME Sugar Malaysia Berhad"}]    
#     Sample output2: [{"PRODUCT_NAME":"Mint Concentrate MT2245","SUPPLIER_NAME":"Emmi Switzerland"}]
#     Sample output3: [{"PRODUCT_NAME":"iPhone 15 Pro","SUPPLIER_NAME":"Apple Inc."},
#                     {"PRODUCT_NAME":"Galaxy S24 Ultra","SUPPLIER_NAME":"Samsung Electronics"}]     
#     Sample output4: [{"PRODUCT_NAME":"PlayStation 5","SUPPLIER_NAME":"Sony Interactive Entertainment"},
#                     {"PRODUCT_NAME":"Air Jordan 1 Retro High OG","SUPPLIER_NAME":"Nike, Inc."},
#                     {"PRODUCT_NAME":"Model 3","SUPPLIER_NAME":"Tesla, Inc."}]   

#     ### PARSED OUTPUT ###
#     """
#     question += parsed_output  
#     return question

def buildStructuredOutputBody(parsed_text, product_name, manufacturer_name, ls_base64):
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {
            "role": "system",
            "content": f"""
                You will read the given text and extract specific product-related information.
                Always return all fields. If any information is missing or not found, return the string 'Not Specified' for that field.
                If there is multiple products in the text, only focus on finding answer for product [{product_name}] from manufacturer [{manufacturer_name}]. 
            """
        },
        {
            "role": "user",
            "content": parsed_text
        }
    ]    
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # BUILD BODY
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "full_supply_chain_form",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "manufacturing_site_address": {
                            "type": "string",
                            "description": "Full address where the product is manufactured"},
                        "manufacturing_country": {
                            "type": "string",
                            "description": "Country where the product is manufactured"},
                        "manufacturer_article_number": {
                            "type": "string",
                            "description": "Internal reference number of the product from the manufacturer"},
                        "physical_location_of_goods": {
                            "type": "string",
                            "description": "Country where the goods are physically located"},
                        "contains_animal_origin": {
                            "type": "string",
                            "description": "Does the product contain substances of animal origin?"},
                        "contains_vegetal_origin": {
                            "type": "string",
                            "description": "Does the product contain substances of vegetal origin?"},
                        "contains_palm": {
                            "type": "string",
                            "description": "Does the product contain or use palm origin derivatives?"},
                        "contains_mineral_origin": {
                            "type": "string",
                            "description": "Does the product contain substances of mineral origin?"},
                        "contains_conflict_minerals": {
                            "type": "string",
                            "description": "Does the product contain conflict minerals? (These conflict minerals are tin, tantalum, tungsten, gold and their derivatives)"},
                        "contains_synthetic_origin": {
                            "type": "string",
                            "description": "Does the product contain substances of synthetic origin?"},
                        "other_specified_origin": {
                            "type": "string",
                            "description": "If other origin is specified, include the detail"},
                        "outer_packaging_unit": {
                            "type": "string",
                            "description": "Type of outer packaging unit (e.g., bag, box, drum)"},
                        "outer_packaging_material": {
                            "type": "string",
                            "description": "Material used in outer packaging (e.g., PE, aluminum)"},
                        "un_homologated_outer_packaging": {
                            "type": "string",
                            "description": "Is the outer packaging UN homologated?"},
                        "inner_packaging_unit": {
                            "type": "string",
                            "description": "Inner packaging unit type"},
                        "inner_packaging_material": {
                            "type": "string",
                            "description": "Material used in inner packaging"},
                        "gross_weight_kg": {
                            "type": "string",
                            "description": "Gross weight in kilograms"},
                        "net_weight_kg": {
                            "type": "string",
                            "description": "Net weight in kilograms"},
                        "dimensions_lwh": {
                            "type": "string",
                            "description": "Length / Width / Height (in meters or cm)"},
                        "volume_m3": {
                            "type": "string",
                            "description": "Volume of the packaging unit in cubic meters"},
                        "pallet_type_material": {
                            "type": "string",
                            "description": "Type and material of pallet used"},
                        "storage_conditions": {
                            "type": "string",
                            "description": "Storage conditions including temperature and humidity"},
                        "transport_conditions": {
                            "type": "string",
                            "description": "Required transport temperature or conditions"},
                        "shelf_life": {
                            "type": "string",
                            "description": "Shelf life of the product"},
                        "lot_batch_structure": {
                            "type": "string",
                            "description": "Structure of lot or batch number (e.g., 200101 = YYMMDD)"},
                        "tariff_code": {
                            "type": "string",
                            "description": "Tariff code for customs (TARIC for EU or local tariff code)"},
                        "origin_country": {
                            "type": "string",
                            "description": "Country of origin (manufactured, processed or grown)"},
                        "customs_status": {
                            "type": "string",
                            "description": "'Union' if product is from within EU; 'Non-Union' if from outside"},
                        "preferential_origin_eu": {
                            "type": "string",
                            "description": "Preferential origin as per FTA with EU"},
                        "preferential_origin_uk": {
                            "type": "string",
                            "description": "Preferential origin as per FTA with UK"},
                        "preferential_origin_ch": {
                            "type": "string",
                            "description": "Preferential origin as per FTA with Switzerland"},
                        "preferred_eu_supplier": {
                            "type": "string",
                            "description": "Preferred supplier based in EU?"},
                        "estimated_cost_local": {
                            "type": "string",
                            "description": "Estimated cost in local currency"},
                        "quantity_in_1st_po": {
                            "type": "string",
                            "description": "Quantity ordered in the first PO to supplier"},
                        "estimated_year_quantity": {
                            "type": "string",
                            "description": "Estimated total quantity for current year"},
                        "custom_clearance_by": {
                            "type": "string",
                            "description": "Who handles customs clearance (Us, Supplier)"},
                        "country_sold_to": {
                            "type": "string",
                            "description": "Destination country of the goods"},
                        "location_at_time_of_po": {
                            "type": "string",
                            "description": "Country where goods are located at the time of PO"},
                        "custom_clearance_country": {
                            "type": "string",
                            "description": "Country where the goods will be cleared by customs"}
                        },
                    "required": [
                        "manufacturing_site_address",
                        "manufacturing_country",
                        "manufacturer_article_number",
                        "physical_location_of_goods",
                        "contains_animal_origin",
                        "contains_vegetal_origin",
                        "contains_palm",
                        "contains_mineral_origin",
                        "contains_conflict_minerals",
                        "contains_synthetic_origin",
                        "other_specified_origin",
                        "outer_packaging_unit",
                        "outer_packaging_material",
                        "un_homologated_outer_packaging",
                        "inner_packaging_unit",
                        "inner_packaging_material",
                        "gross_weight_kg",
                        "net_weight_kg",
                        "dimensions_lwh",
                        "volume_m3",
                        "pallet_type_material",
                        "storage_conditions",
                        "transport_conditions",
                        "shelf_life",
                        "lot_batch_structure",
                        "tariff_code",
                        "origin_country",
                        "customs_status",
                        "preferential_origin_eu",
                        "preferential_origin_uk",
                        "preferential_origin_ch",
                        "preferred_eu_supplier",
                        "estimated_cost_local",
                        "quantity_in_1st_po",
                        "estimated_year_quantity",
                        "custom_clearance_by",
                        "country_sold_to",
                        "location_at_time_of_po",
                        "custom_clearance_country"
                    ],
                    "additionalProperties": False
        }
        }
    }
    }
    return body

def buildCompositionOutputBody(parsed_text, product_name, manufacturer_name, ls_base64):
    messages = [
        {
            "role": "system",
            "content": f"""
                You are a data extraction agent that processes technical documents and extracts chemical composition information.
                Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].
                Your goal is to detect the composition details of that product and convert them into a structured format.

                Output format:
                {{
                  "composition": [
                    {{
                      "substance_name": string,
                      "role_of_substance": one of:
                        - Not Specified
                        - additive
                        - carrier
                        - emulsifier
                        - ingredient
                        - impurity (including residual solvents)
                        - preservative
                        - processing aids
                        - solvent
                        - stabilizer
                        - other (specify)
                          > Example: other (colorant)
                          > Example: other (defoaming)
                      "ec_number": string,
                      "percentage": string
                    }}
                  ]
                }}

                Output explanation
                - substance_name: Name of the substance used in the composition of this product.
                - role_of_substance: What is the purpose of this substance.
                - ec_number: EC number of this substance used in the composition of this product.
                - percentage: Percentage composition this substance, which is the composition of the product (not about the product usage recommendation percentage)

                Output rules:
                - If a field is missing or unclear, use "Not Specified".
                - If no composition is found for the specified product-manufacturer pair, return:
                    > [["Not Specified", "Not Specified", "Not Specified", "Not Specified"]]
                - If only some data is available for a substance (e.g., only Substance Name is mentioned), return what is available, and mark missing fields as "Not Specified".                
                    > Example: ["Magnesium Sulfate", "Not Specified", "Not Specified", "Not Specified"]
                    > Example: ["Citric Acid", "ingredient", "Not Specified", "Not Specified"]
                    > Example: ["Water", "solvent", "231-791-2", "Not Specified"]
                    > Example: ["Sodium Benzoate", "preservative", "Not Specified", "0.1%"]
                    > Example: ["Glycerin", "Not Specified", "200-289-5", "Not Specified"]                         
                    > Example: ["Zinc Oxide", "other (UV filter)", "Not Specified", "Not Specified"]          
                - Return all found substances as a list of lists in the required format.
                    > Example: [["Magnesium Sulfate", "Not Specified", "Not Specified", "Not Specified"]]
                    > Example: [["Citric Acid", "ingredient", "Not Specified", "Not Specified"],["Water", "solvent", "231-791-2", "Not Specified"]]
                    > Example: [["Sodium Benzoate", "preservative", "Not Specified", "0.1%"],["Glycerin", "Not Specified", "200-289-5", "Not Specified"],["Zinc Oxide", "other (UV filter)", "Not Specified", "Not Specified"]]               

            """
        },
        {
            "role": "user",
            "content": parsed_text
        }
    ]

    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })

    body = {
        "model": "gpt-4o",
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "composition_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "composition": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {

                                    "substance_name": { 
                                        "type": "string",
                                        "description": "Name of the substance used in the composition of this product"},
                                    "role_of_substance": {
                                        "type": "string",
                                        "pattern": "^(Not Specified|additive|carrier|emulsifier|ingredient|impurity \\(including residual solvents\\)|preservative|processing aids|solvent|stabilizer|other \\(.+\\))$",
                                        "description": "What is the purpose of this substance"},                                    
                                    "ec_number": { 
                                        "type": "string",
                                        "description": "EC number of this substance used in the composition of this product"},
                                    "percentage": { 
                                        "type": "string",
                                        "description": "percentage of this substance, which is the composition of the product"},

                                },
                                "required": ["substance_name", "role_of_substance", "ec_number", "percentage"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["composition"],
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



def PIM_buildBodySelectIndustryCluster(parsed_text, product_name, manufacturer_name, ls_base64, business_line):
    # Define mapping of business lines to industry clusters
    if business_line == 'FBI':
        selection_list = [
            'Beverage & Dairy',
            'Confectionery & Bakery',
            'Food Supplements & Nutrition',
            'Processed Food & Food Service']
    elif business_line == 'PCI':
        selection_list = [
            'Cosmetics & Toiletries',
            'Homecare & Institutional Cleaning',
            'Cosmetics & Toiletries, Homecare & Institutional Cleaning']
    elif business_line == 'PHI':
        selection_list = [
            'Animal Care',
            'API',
            'Biopharma',
            'Excipients',
            'Intermediates & Reagents',
            'Nutraceuticals',
            'Packing Materials',
            'Clean Room Management']
    elif business_line == 'SCI':
        selection_list = [
            'Electronic & Specialties',
            'Paints & Coatings',
            'Polymers',
            'Agrochemicals',
            'Electronic & Specialties, Paints & Coatings',
            'Paints & Coatings, Polymers',
            'Electronic & Specialties, Polymers',
            'Electronic & Specialties, Paints & Coatings, Polymers']
    # SYSTEM PROMPT
    system_prompt = f"""
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].        
        select exactly one INDUSTRY CLUSTER from the following list:{selection_list}

        Output format:
        {{
          "industry_cluster": string
        }}
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user","content": parsed_text}
    ]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # CONSTRUCT BODY
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "industry_cluster_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "industry_cluster": {
                            "type": "string",
                            "enum": selection_list,
                            "description": "Selected industry cluster based given text and image"
                        }
                    },
                    "required": ["industry_cluster"],
                    "additionalProperties": False
                }
            }
        }
    }

    return body



def PIM_buildBodySelectComposition(parsed_text, product_name, manufacturer_name, ls_base64):
    selection_list = [
        'Animal',
        'Biomolecule/Micro-organisms',
        'Derived Natural',
        'Mineral',
        'Synthetic',
        'Vegetal'
    ]
    # SYSTEM PROMPT
    system_prompt = f"""
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].        
        select one or more compositions from the following list:{selection_list}

        Output format:
        {{
          "compositions": string
        }}
    """
    # BUILD THE MESSAGES FOR THE STRUCTURED OUTPUT REQUEST
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user","content": parsed_text}
    ]
    # ADD BASE64 IMAGES IF PROVIDED
    for base64_img in ls_base64:
        messages.append({
            "role": "user", "content": [{"type": "image_url",
                                         "image_url": {"url": f"data:image/png;base64,{base64_img}"}}]
        })
    # CONSTRUCT BODY
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "composition_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "compositions": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": selection_list},
                            "minItems": 1,
                            "description": "One or more selected compositions based on the given text and image"}
                    },
                    "required": ["compositions"],
                    "additionalProperties": False
                }
            }
        }
    }

    return body