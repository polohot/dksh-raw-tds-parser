# dksh-raw-tds-parser

**Use AI to parser PDF into specific format**

```
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
