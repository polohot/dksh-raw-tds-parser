def buildQuestionGetProductNameAndSupplierFromParsedText(parsed_output):
    question = """
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

    ### PARSED OUTPUT ###
    """
    question += parsed_output  
    return question

def buildStructuredOutputBody(parsed_text, product_name, manufacturer_name):
    body = {
    "model": "gpt-4o",
    "messages": [
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
    ],
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
                "description": "Full address where the product is manufactured"
            },
            "manufacturing_country": {
                "type": "string",
                "description": "Country where the product is manufactured"
            },
            "manufacturer_article_number": {
                "type": "string",
                "description": "Internal reference number of the product from the manufacturer"
            },
            "physical_location_of_goods": {
                "type": "string",
                "description": "Country where the goods are physically located"
            },
            "contains_animal_origin": {
                "type": "string",
                "description": "Does the product contain substances of animal origin?"
            },
            "contains_vegetal_origin": {
                "type": "string",
                "description": "Does the product contain substances of vegetal origin?"
            },
            "contains_palm": {
                "type": "string",
                "description": "Does the product contain or use palm origin derivatives?"
            },
            "contains_mineral_origin": {
                "type": "string",
                "description": "Does the product contain substances of mineral origin?"
            },
            "contains_conflict_minerals": {
                "type": "string",
                "description": "Does the product contain conflict minerals (e.g., tantalum, tungsten, gold)?"
            },
            "contains_synthetic_origin": {
                "type": "string",
                "description": "Does the product contain substances of synthetic origin?"
            },
            "other_specified_origin": {
                "type": "string",
                "description": "If other origin is specified, include the detail"
            },
            "outer_packaging_unit": {
                "type": "string",
                "description": "Type of outer packaging unit (e.g., bag, box, drum)"
            },
            "outer_packaging_material": {
                "type": "string",
                "description": "Material used in outer packaging (e.g., PE, aluminum)"
            },
            "un_homologated_outer_packaging": {
                "type": "string",
                "description": "Is the outer packaging UN homologated?"
            },
            "inner_packaging_unit": {
                "type": "string",
                "description": "Inner packaging unit type"
            },
            "inner_packaging_material": {
                "type": "string",
                "description": "Material used in inner packaging"
            },
            "gross_weight_kg": {
                "type": "string",
                "description": "Gross weight in kilograms"
            },
            "net_weight_kg": {
                "type": "string",
                "description": "Net weight in kilograms"
            },
            "dimensions_lwh": {
                "type": "string",
                "description": "Length / Width / Height (in meters or cm)"
            },
            "volume_m3": {
                "type": "string",
                "description": "Volume of the packaging unit in cubic meters"
            },
            "pallet_type_material": {
                "type": "string",
                "description": "Type and material of pallet used"
            },
            "storage_conditions": {
                "type": "string",
                "description": "Storage conditions including temperature and humidity"
            },
            "transport_conditions": {
                "type": "string",
                "description": "Required transport temperature or conditions"
            },
            "shelf_life": {
                "type": "string",
                "description": "Shelf life of the product"
            },
            "lot_batch_structure": {
                "type": "string",
                "description": "Structure of lot or batch number (e.g., 200101 = YYMMDD)"
            },
            "tariff_code": {
                "type": "string",
                "description": "Tariff code for customs (TARIC for EU or local tariff code)"
            },
            "origin_country": {
                "type": "string",
                "description": "Country of origin (manufactured, processed or grown)"
            },
            "customs_status": {
                "type": "string",
                "description": "'Union' if product is from within EU; 'Non-Union' if from outside"
            },
            "preferential_origin_eu": {
                "type": "string",
                "description": "Preferential origin as per FTA with EU"
            },
            "preferential_origin_uk": {
                "type": "string",
                "description": "Preferential origin as per FTA with UK"
            },
            "preferential_origin_ch": {
                "type": "string",
                "description": "Preferential origin as per FTA with Switzerland"
            },
            "eu_supplier": {
                "type": "string",
                "description": "Is the supplier based in the EU?"
            },
            "estimated_cost_local": {
                "type": "string",
                "description": "Estimated cost in local currency"
            },
            "quantity_in_1st_po": {
                "type": "string",
                "description": "Quantity ordered in the first PO to supplier"
            },
            "estimated_year_quantity": {
                "type": "string",
                "description": "Estimated total quantity for current year"
            },
            "custom_clearance_by": {
                "type": "string",
                "description": "Who handles customs clearance (Us, Supplier)"
            },
            "country_sold_to": {
                "type": "string",
                "description": "Destination country of the goods"
            },
            "location_at_time_of_po": {
                "type": "string",
                "description": "Country where goods are located at the time of PO"
            },
            "custom_clearance_country": {
                "type": "string",
                "description": "Country where the goods will be cleared by customs"
            }
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
            "eu_supplier",
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