import os
import requests

def ingest_clinical_guidelines(output_dir="guidelines_corpus"):
    """
    Pulls authoritative clinical guideline PDFs for vector store ingestion.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Expanded seed list of real-world clinical guidelines (USPSTF, CDC, WHO)
    pdf_sources = {
        # USPSTF Clinician Summaries & Methodology
        "USPSTF_Aspirin_CVD": "https://www.uspreventiveservicestaskforce.org/uspstf/sites/default/files/file/supporting_documents/aspirin-cvd-prevention-clinician-summary.pdf",
        "USPSTF_Breast_Cancer_Screening": "https://www.uspreventiveservicestaskforce.org/uspstf/sites/default/files/file/supporting_documents/breast-cancer-screening-clinician-summary.pdf",
        "USPSTF_Statin_Use": "https://www.uspreventiveservicestaskforce.org/uspstf/sites/default/files/file/supporting_documents/statin-use-cvd-prevention-clinician-summary.pdf",
        "USPSTF_Hypertension_Screening": "https://www.uspreventiveservicestaskforce.org/home/getfilebytoken/ZLDgVoLvb--9ooeW9o5n8f",
        "USPSTF_Oral_Health_Screening": "https://www.uspreventiveservicestaskforce.org/home/getfilebytoken/_AjbWmAPGQzdG2A_qGu-ED",
        "USPSTF_Methodology_Overview": "https://www.uspreventiveservicestaskforce.org/uspstf/sites/default/files/2025-03/uspstf-who-we-are-how-we-work-2025.pdf",
        
        # CDC / ASAM Clinical Practice Guidelines
        "CDC_ASAM_Stimulant_Use_Disorder": "https://stacks.cdc.gov/view/cdc/156927/cdc_156927_DS1.pdf",
        
        # WHO Standard Treatment Guidelines
        "WHO_Standard_Treatment_Adults": "https://extranet.who.int/ncdccs/Data/PNG_D1_Standard-Treatment-Guidelines-for-Common-Illness-of-Adults-in-PNG.pdf"
    }

    for name, url in pdf_sources.items():
        print(f"Downloading {name}...")
        try:
            # Added a user-agent header as some government sites block default Python requests
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(url, headers=headers, stream=True, timeout=15)
            response.raise_for_status()
            
            file_path = os.path.join(output_dir, f"{name}.pdf")
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Saved: {file_path}")
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {name}: {e}")

if __name__ == "__main__":
    ingest_clinical_guidelines()