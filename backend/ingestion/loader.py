from io import BytesIO

def load_file(filename: str, data: bytes) -> str:
    name = filename.lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            pages = [p.extract_text() or "" for p in reader.pages]
            # Join pages with a form feed so the "page" chunking strategy
            # can split on real page boundaries.
            return "\f".join(pages)
        if name.endswith(".docx"):
            from docx import Document
            return "\n\n".join(p.text for p in Document(BytesIO(data)).paragraphs)
        if name.endswith((".txt", ".md")):
            return data.decode("utf-8", errors="ignore")
        if name.endswith((".html", ".htm")):
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(data, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            return soup.get_text("\n", strip=True)
    except Exception as e:
        raise ValueError(f"Failed to parse {filename}: {e}")
    return data.decode("utf-8", errors="ignore")