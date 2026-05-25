# **AI Engineer — Technical Assessment**

### **Objective**

This assessment evaluates your ability to design and implement local AI workflows that involve document understanding, classification, data extraction, and retrieval using open-source tools only.

Important: No hosted or paid AI services (e.g., OpenAI, Claude, Gemini) are allowed.  
 A simple CLI or API interface is sufficient, UI is optional.

### **Task Description**

You are required to build a local AI system that can:

1. Ingest & Process Documents  
   1. Read all PDF or text files from a provided folder (10–15 documents).  
   2. Extract and clean their text content.  
2. Classify Each Document  
    Classify every file into one of the following categories:  
   1. Invoice  
   2. Resume  
   3. Utility Bill  
   4. Other  
   5. Unclassifiable  
3. Extract Structured Data

| Document Type | Fields to Extract |
| :---- | :---- |
| Invoice | invoice\_number, date, company, total\_amount |
| Resume | name, email, phone, experience\_years |
| Utility Bill | account\_number, date, usage\_kwh, amount\_due |
| Other / Unclassifiable | No extraction required |

   

4. Implement a Simple Retrieval System  
    Build a local semantic search component using open-source embeddings (for example, SentenceTransformers or Hugging Face Transformers).  
    It should allow the user to search documents by meaning, e.g.:

“Find all documents mentioning payments due in January.”

5. (Optional Bonus)  
    Demonstrate how this retrieval could extend into a local question-answering workflow using an open-source LLM (e.g., Mistral, LLaMA, Falcon).  
    *This part is optional and not required for a passing score.*

### **Deliverables**

1. Solution Code : well-structured and documented.  
2. Output.json:  containing classifications and extracted fields.  
    Example:

{

  "invoice\_1.pdf": {

    "class": "Invoice",

    "invoice\_number": "INV-1234",

    "date": "2025-01-01",

    "company": "ACME Ltd.",

    "total\_amount": 350.5

  },

  "resume\_1.pdf": {

    "class": "Resume",

    "name": "John Doe",

    "email": "john@example.com",

    "phone": "123-456-7890",

    "experience\_years": 5

  }

}

3\.README.md explaining:

1. How to install dependencies  
   2. How to run the program locally  
   3. What libraries and methods were used

###  **Technical Rules**

* Allowed — Open-source libraries (PyTorch, Transformers, SentenceTransformers, FAISS, scikit-learn, pdfminer, PyPDF, etc.)  
* Not Allowed — Paid or hosted AI APIs (OpenAI, Claude, Gemini, etc.)  
* UI optional (CLI or API output is fine).  
* All processing must run locally.

### **Dataset**

You will be provided with a **sample dataset of PDF documents** (Invoices, Resumes, Utility Bills, and Others).  
 Use these files as input for your solution.

### **Submission Instructions**

1. Zip your solution or upload it to GitHub.  
2. Include:  
   1. Code folder  
   2. output.json  
   3. README.md  
3. Ensure it runs offline without internet access.

