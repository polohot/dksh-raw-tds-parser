# dksh-raw-tds-parser

**Use AI to parser PDF into specific format**

```
[V1.24-beta] - 2026-01-15
- Update "PIM_buildBodySelectFunction"
    Add new selection list for "FUNCTIONS"

[V1.23-beta] - 2025-11-20
- PIM_buildBodySelectIndustryCluster
    Change selection list to new list from SFDC
- mainDict['stg_parsedText'] - to save in history, but not to send back in response
- Reduce wait time for those hash already called 15-25s become 10-15s

[V1.22-beta] - 2025-10-28
- Code cleanup

[V1.20-beta] - 2025-10-27
- Add end point "v1_parse_pim_fields_b64"
    Allow input as base64 string inplace of PDF files

[V1.12-beta] - 2025-10-17
- v1_selectHealthBenefits change to either output blank list or list with object

[V1.11-beta] - 2025-10-17
- Add multiple hash functions
    /v1_histAPICalls_count
    /v1_histAPICalls_list
    /v1_histAPICalls_read
    /v1_histAPICalls_delete

[V1.10-beta] - 2025-10-17
- Fix exact call dont get same result
- Now exact call get exact same result

[V1.0-beta] - 2025-10-14
- All BL strictly follow given document
- For internal testing

[V0.9-alpha] - 2025-09-10
- Modify FBI to strictly follow the given document, for generation for FBI to check again

[V0.8-alpha] - 2025-08-25
- Adding MainAPI.py for API UAT

[V0.7-alpha] - 2025-08-20
- Adding page "(3) Gen PIM Template - No Search.py" - remove search function

[V0.6-alpha] - 2025-08-03
- Change Selection from list method to use Flag, instead of multi select for 
    COMPOSITIONS, APPLICATIONS, FUNCTIONS, CLAIMS

[V0.5-alpha] - 2025-07-30
- Fix bug for CLAIMS
- New resource map to this project
    AZURE AI FOUNDARY DEPLOYMENT : azure-ai-services-gpt-4.1-mini-dksh-raw-tds-parser
    AZURE DOCUMENT INTELLIGENCE : document-intelligence-standard-s0-dksh-raw-tds-parser
    OPENAI PROJECT : dksh-raw-tds-parser

[V0.4-alpha] - 2025-07-24
- New resource map to this project
    AZURE AI FOUNDARY DEPLOYMENT : dksh-raw-tds-parser
    AZURE DOCUMENT INTELLIGENCE : document-intelligence-standard-s0-dksh-raw-tds-parser
    OPENAI PROJECT : dksh-raw-tds-parser
- Add Generation "Product Description"
- Current cost around 10 THB per product

[V0.3-alpha] - 2025-07-23
- Change Subscription of Azure Document Intelligence from Free to standard-s0 resource
- (2) Gen PIM Template - Change location of run Log to show on top
- (2) Gen PIM Template - COMPOSITION, Allow all BL to do web search and list COMPOSITION,
                       - Except PCI, must select COMPOSITION from given list
- (2) Gen PIM Template - PHYSICAL_FORM if not found in document put N/A

[V0.2-alpha] - 2025-07-22
- Change Parsing PDF, from using LlamaParse, to use Internal Azure AI Document Intelligence for compliance
- Change from using OpenAI API to Azure AI Foundary API for compliance
- Create Page "Gen PIM Form"

[V0.1-alpha] - 2025-07-08
- First Deployment for "Gen Product Form"
```
