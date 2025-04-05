# Terminology Browser and FHIR ValueSet Builder

This is a **Streamlit**-based web application designed to help users **search, explore, and build ValueSets** from medical terminologies based on the **OMOP CDM vocabulary**. It supports exporting results in **CSV** and **FHIR-compliant JSON** formats, making it useful for projects involving data harmonization, clinical research, and FHIR-based interoperability.

we have used following vocabularies

|ID|	CDM|	Code (cdm v5)|	Name|
|----|------|-----|-----|
|146|	CDM 5|	OMOP Genomic|	OMOP Genomic vocabulary of known variants involved in disease|
|82|	CDM 5|	RxNorm Extension|	OMOP RxNorm Extension|
|34|	CDM 5|	ICD10|	International Classification of Diseases, Tenth Revision (WHO)|
|21|	CDM 5|	ATC|	WHO Anatomic Therapeutic Chemical Classification|
|8|	CDM 5|	RxNorm|	RxNorm (NLM)|
|6|	CDM 5|	LOINC|	Logical Observation Identifiers Names and Codes (Regenstrief Institute)|
|1|	CDM 5|	SNOMED|	Systematic Nomenclature of Medicine - Clinical Terms (IHTSDO)|

You can download the vocahulary files from [athena](https://athena.ohdsi.org/vocabulary/list)

## 🔍 Features

- **Concept Search**
  - Search by concept name or concept code.
  - Filter results by vocabulary (e.g., SNOMED, LOINC, RxNorm).
  - Download results as CSV.

- **SNOMED Descendant Finder**
  - Find all descendants of one or more SNOMED concepts using `concept_ancestor` relationships.
  - Search ancestors by name or code.
  - Export descendant lists and build FHIR ValueSets.

- **FHIR ValueSet Builder**
  - Build FHIR-compliant ValueSets directly from search results or SNOMED descendants.
  - Download generated ValueSets as JSON.

## 🛠️ Technologies Used

- **Streamlit** for UI
- **SQLite** for local terminology database (OMOP vocabularies)
- **Pandas** for data manipulation
- **FHIR R4** standard for ValueSet formatting

## 🗂️ Folder Structure
📦 project_root/ <br>
├── db/ <br>
│   └── omop_vocab.sqlite         <br> 
├──vocabulary <br> 
├── app.py       <br>
├── init_db_omop.py <br>
└── README.md                    # This file


## 🧱 Prerequisites

- Python 3.8+
- OMOP Vocabulary tables exported to `omop_vocab.sqlite` database.
  - Required tables: `concept`, `concept_ancestor`

## ▶️ Getting Started

1. **Clone the repository**:

   ```bash
   git clone https://github.com/data2health-infoTerminologyBrowser.git
   cd TerminologyBrowser
   ```
2. **Download the required vocabularies from [athena](https://athena.ohdsi.org/vocabulary/list)**
3. **Create the db** 
```bash
python init_db_omop.py
```


4. **Run app.py**
```bash
streamlit run "app.py"
```
5. **Open the browser at http://localhost:8501**

