import streamlit as st
from streamlit_js_eval import streamlit_js_eval
import datetime

def get_time_difference(key: str = "client_ts") -> float:
    """
    Returns the difference between server time and client time in milliseconds.
    Internally handles the “waiting for browser” case by showing a message
    and stopping the app until a value arrives.
    """
    # Capture server timestamp immediately
    server_time = datetime.datetime.now()
    # Trigger the JS call to get client‐side epoch ms
    client_ts_ms = streamlit_js_eval(js_expressions="Date.now()", key=key)
    # If JS hasn’t returned yet, show a message and halt execution
    if client_ts_ms is None:
        st.info("⏳ Waiting for browser timestamp…")
        st.stop()
    # Convert back to a datetime and compute the delta
    client_time = datetime.datetime.fromtimestamp(client_ts_ms / 1000.0)
    delta = server_time - client_time
    # Return offset in milliseconds
    return delta.total_seconds() * 1000

###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################
###############################################################################################################################################################################

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

def azureDocumentIntelligenceParsePDF(file_path, key):
    document_intelligence_client = DocumentIntelligenceClient(
        endpoint="https://document-intelligence-standard-s0-main02.cognitiveservices.azure.com/", credential=AzureKeyCredential(key))
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
    ### INSTRUCTION ###
    You are a helpful assistant that extracts the name and manufacturer from parsed output of a PDF file.
    The parsed file is the Technical Data Sheet of the product.
    Sometimes the parsed PDF has only one product, sometimes multiple.
    Output ONLY the needed data in the required format.

    ### OUTPUT FORMAT ###
    Return a JSON array of objects.
    Do NOT put any text before or after the square brackets.

    Each object must have:
    - "PRODUCT_NAME": string
    - "SUPPLIER_NAME": string

    Examples:
    [{"PRODUCT_NAME":"Sugar C1002","SUPPLIER_NAME":"ACME Sugar Malaysia Berhad"}]
    [{"PRODUCT_NAME":"Mint Concentrate MT2245","SUPPLIER_NAME":"Emmi Switzerland"}]
    [{"PRODUCT_NAME":"iPhone 15 Pro","SUPPLIER_NAME":"Apple Inc."},
    {"PRODUCT_NAME":"Galaxy S24 Ultra","SUPPLIER_NAME":"Samsung Electronics"}]
    [{"PRODUCT_NAME":"PlayStation 5","SUPPLIER_NAME":"Sony Interactive Entertainment"},
    {"PRODUCT_NAME":"Air Jordan 1 Retro High OG","SUPPLIER_NAME":"Nike, Inc."},
    {"PRODUCT_NAME":"Model 3","SUPPLIER_NAME":"Tesla, Inc."}]
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
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.2,
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
        select exactly one INDUSTRY CLUSTER related to the product [{product_name}] from the following list:{selection_list}

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
        "temperature": 0.2,
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
                            "description": f"Select INDUSTRY CLUSTER related to the product [{product_name}]"
                        }
                    },
                    "required": ["industry_cluster"],
                    "additionalProperties": False
                }
            }
        }
    }
    return body    

def PIM_buildBodySelectComposition(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # Define mapping of business lines to industry clusters
    if business_line == 'FBI':
        selection_list = [
            "Plant (Vegetal)",
            "Animal",
            "Microbial, Fungal (yeast, bacteria)",
            "Algal, Marine",
            "Mineral, Inorganic",
            "Synthetic, Chemically Manufactured",
            "Fermentation, Biotech-Derived",
            "Semi-Synthetic, Modified Natural",
            "Nature-Identical (chemically equivalent to natural)",
            "Upcycled, Recovered Food Streams",
            "Processing Aid, Carrier (solvents, anticaking agents, fillers)"]
    elif business_line == 'PCI':
        selection_list = [
            "Animal",
            "Biomolecule/Micro-organisms",
            "Derived Natural",
            "Mineral",
            "Synthetic",
            "Vegetal"]
    elif business_line == 'PHI':
        selection_list = [
            "Plant, Herbal",
            "Animal-Derived",
            "Microbial, Fungal (yeast, bacteria, molds)",
            "Marine, Algal",
            "Mineral, Inorganic",
            "Synthetic Small Molecule (chemically manufactured)",
            "Semi-Synthetic, Modified Natural",
            "Biotech, Biologic (recombinant proteins, vaccines, cells, tissues)",
            "Cell-Derived, Tissue-Derived (human, animal)",
            "Gene-Based, Nucleic Acid-Based (mRNA, DNA, oligonucleotides)",
            "Radiochemical, Isotope-Labeled",
            "Polymeric Excipient, Synthetic Polymer (e.g., PEG, PVP)",
            "Fixed-Dose, Combination Product Blend"]
    elif business_line == 'SCI':
        selection_list = [
            "Petrochemical, Hydrocarbon-Derived",
            "Bio-based, Renewable",
            "Microbial, Biotech-Derived",
            "Inorganic, Mineral",
            "Organic Synthetic (non-polymeric)",
            "Polymer, Resin, Elastomer",
            "Silicone, Organosilicon",
            "Fluorinated, Halogenated",
            "Metal, Organometallic, Catalyst",
            "Formulated Blend, Mixture",
            "CO₂, Carbon-Capture-Derived",
            "Recycled, Reclaimed, By-product Stream",
            "Ionic Liquid, Deep Eutectic Solvent",
            "Electrochemically Produced, Battery-Grade Material"]
    # SYSTEM PROMPT
    system_prompt = f"""
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].        
        Select as much as possible COMPOSITIONS but only those related to the product [{product_name}] from the following list:{selection_list}

        Output format:
        {{
          "compositions": array of string
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
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.2,
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
                            "description": f"Select as much as possible COMPOSITIONS but only those related to the product [{product_name}]"}
                    },
                    "required": ["compositions"],
                    "additionalProperties": False
                }
            }
        }
    }
    return body


def PIM_buildBodySelectApplication(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # Define mapping of business lines to industry clusters
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
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].   
        Select as much as possible APPLICATIONS but only those related to the product [{product_name}] from the following list:{selection_list}

        Output format:
        {{
          "applications": array of string
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
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "applications_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "applications": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": selection_list},
                            "minItems": 1,
                            "description": f"Select as much as possible APPLICATIONS but only those related to the product [{product_name}]"
                        }
                    },
                    "required": ["applications"],
                    "additionalProperties": False
                }
            }
        }
    }

    return body


def PIM_buildBodySelectFunction(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # Define mapping of business lines to industry clusters
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
            "Other",
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
            "Biocide",
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
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].   
        Select as much as possible FUNCTIONS but only those related to the product [{product_name}] from the following list:{selection_list}

        Output format:
        {{
          "functions": array of string
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
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "functions_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "functions": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": selection_list},
                            "minItems": 1,
                            "description": f"Select as much as possible FUNCTIONS but only those related to the product [{product_name}]"
                        }
                    },
                    "required": ["functions"],
                    "additionalProperties": False
                }
            }
        }
    }

    return body

def PIM_buildBodyFindCASNumber(parsed_text, product_name, manufacturer_name, ls_base64, searched_text=''):
    # SYSTEM PROMPT
    system_prompt = f"""
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and images, focus only on product [{product_name}] from manufacturer [{manufacturer_name}].
        Try to find any CAS Registry Number mentioned in the content. If none is found, output "N/A".

        Output format:
        {{
          "cas_number": string
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
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "cas_number_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "cas_number": {
                            "type": "string",
                            "description": "The CAS Registry Number found in the document, or 'N/A' if none is present"
                        }
                    },
                    "required": ["cas_number"],
                    "additionalProperties": False
                }
            }
        }
    }

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
            "Suspension"]
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
            "Wax"]
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
            "Fiber & Stainless Steel"]
    elif business_line == 'SCI':
        selection_list = [
            "Dispersion",
            "Emulsion",
            "Liquid",
            "Micronized powder",
            "Nano powder",
            "Paste",
            "Solid"]
    # SYSTEM PROMPT
    system_prompt = f"""
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and images, focus only on product [{product_name}] from manufacturer [{manufacturer_name}].
        Select the correct PHYSICAL_FORM of this specific product. If none is found, output "N/A".

        Output format:
        {{
          "physical_form": string
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
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "physical_form_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "physical_form": {
                            "type": "string",
                            "enum": selection_list,
                            "description": f"Select PHYSICAL_FORM of the product [{product_name}]. If none is found, output 'N/A'."
                        }
                    },
                    "required": ["physical_form"],
                    "additionalProperties": False
                }
            }
        }
    }
    return body

def PIM_buildBodyGetRecommendedDosage(parsed_text, product_name, manufacturer_name, ls_base64, searched_text=''):
    # SYSTEM PROMPT
    system_prompt = f"""
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and images, focus only on product [{product_name}] from manufacturer [{manufacturer_name}].
        Try to find any recommended dosage instructions mentioned in the content. This may include dosage amount, units, dosage frequency, or administration route.
        If none is found, output "N/A".

        Output format:
        {{
          "recommended_dosage": string
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
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "recommended_dosage_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "recommended_dosage": {
                            "type": "string",
                            "description": "The recommended dosage found in the document, or 'N/A' if none is present"
                        }
                    },
                    "required": ["recommended_dosage"],
                    "additionalProperties": False
                }
            }
        }
    }
    return body

def PIM_buildBodySelectCertifications(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # Define mapping of business lines to industry clusters
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
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].   
        Select as much as possible CERTIFICATIONS but only those related to the product [{product_name}] from the following list:{selection_list}

        Output format:
        {{
          "certifications": array of string
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
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "certifications_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "certifications": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": selection_list},
                            "minItems": 1,
                            "description": f"Select as much as possible CERTIFICATIONS but only those related to the product [{product_name}]"
                        }
                    },
                    "required": ["certifications"],
                    "additionalProperties": False
                }
            }
        }
    }

    return body



def PIM_buildBodySelectClaims(parsed_text, product_name, manufacturer_name, ls_base64, business_line, searched_text=''):
    # Define mapping of business lines to industry clusters
    if business_line == 'FBI':
        selection_list = [
            "Bio-Fermentation",
            "Meat & Dairy Alternative",
            "Natural & Ethically Sourced",
            "Resource & Energy Optimization",
            "Sustainable Food Waste Reduction",
            "Upcycled"]
    elif business_line == 'PCI':
        selection_list = [
            "Anti-Aging",
            "Anti-Bacterial",
            "Anti-Cellulite",
            "Anti-Dandruff",
            "Anti-Dark Circles",
            "Anti-Fatigue",
            "Anti-Frizz",
            "Anti-Inflammatory",
            "Anti-Itching",
            "Anti-Microbial",
            "Antioxidant",
            "Anti-Pollution",
            "Anti-Stress",
            "Anti-Stretch Mark",
            "Anti-Virus",
            "Anti-Wrinkle",
            "Blue Light Protection",
            "Brightening",
            "Conditioning",
            "Cooling/Warming Effect",
            "COSMOS Standard",
            "Curl Retention",
            "Elasticity",
            "Fair Trade / Fair For Life",
            "Film Forming",
            "Firming",
            "Free Radical Scavenger",
            "Gene Expression Modulation",
            "Hair Color Protection",
            "Hair Loss Reduction",
            "Hair Radiance",
            "Hair Repair",
            "Hair Volume",
            "Immuno Modulation",
            "Insect Repellent",
            "ISCC",
            "Lifting",
            "Mattifying",
            "Microbiome Balance",
            "Moisturizing",
            "NATRUE Standard",
            "Natural Cosmetic",
            "Nordic Swan Ecolabel",
            "Nourishing",
            "Odor Masking",
            "Organic",
            "Pore Refiner",
            "Purifying",
            "Redness Reduction",
            "Relaxer",
            "Safer Choice",
            "Scalp Protection",
            "Sculpting",
            "Sebum Control",
            "Skin Barrier Function",
            "Skin Radiance",
            "Skin Renewal",
            "Skin Repair",
            "Smoothing",
            "Soft Focus",
            "Soothing",
            "Strengthening",
            "Sustainable Palm Oil",
            "Texturizer",
            "UV Protection",
            "Vegan",
            "Wound Healing"]
    elif business_line == 'PHI':
        selection_list = [
            "Animal Derived Component Free (ADCF)",
            "Biodegradable",
            "Bio-Fermentation",
            "Circularity",
            "Environmentally Sustainable Pharmaceutical Manufacturing",
            "Free from Nitrosamine Impurities",
            "Free from Solvents Class 1",
            "Organic",
            "Plant-Based (Min. 80%)",
            "Sustainable Palm Oil"]
    elif business_line == 'SCI':
        selection_list = [
            "Bio-Based",
            "Biodegradable",
            "Bioplastic",
            "Circularity",
            "EcoTain Label",
            "Emission Control",
            "Low VOC",
            "Solvent Free Alternatives",
            "VOC Free"]       

    # SYSTEM PROMPT
    system_prompt = f"""
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].   
        Select as much as possible CLAIMS but only those related to the product [{product_name}] from the following list:{selection_list}

        Output format:
        {{
          "claims": array of string
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
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "claims_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "claims": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": selection_list},
                            "minItems": 1,
                            "description": f"Select as much as possible CLAIMS but only those related to the product [{product_name}]"
                        }
                    },
                    "required": ["claims"],
                    "additionalProperties": False
                }
            }
        }
    }

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
        You are a data extraction agent that processes technical documents and extracts information.
        Based on the provided text and image, Focus only on product [{product_name}] from manufacturer [{manufacturer_name}].   
        Select as much as possible RECOMMENDED_HEALTH_BENEFITS but only those related to the product [{product_name}] from the following list:{selection_list}

        Output format:
        {{
          "rec_health_benefits": array of string
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
    body = {
        "model": "gpt-4o",
        "messages": messages,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "rec_health_benefits_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "rec_health_benefits": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": selection_list},
                            "minItems": 1,
                            "description": f"Select as much as possible RECOMMENDED_HEALTH_BENEFITS but only those related to the product [{product_name}]"
                        }
                    },
                    "required": ["rec_health_benefits"],
                    "additionalProperties": False
                }
            }
        }
    }
    return body