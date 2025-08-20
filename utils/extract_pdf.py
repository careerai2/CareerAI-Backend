from fastapi import UploadFile
import pdfplumber
from io import BytesIO

async def extract_text_from_pdf(file: UploadFile) -> str:
    file_bytes = await file.read()
    file_obj = BytesIO(file_bytes)  # in-memory file

    text = ""
    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    # Normalize whitespace
    return " ".join(text.split())
