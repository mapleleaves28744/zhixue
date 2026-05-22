from pathlib import Path


def parse_document_text(path: str | Path, file_type: str) -> str:
    source = Path(path)
    normalized_type = file_type.lower()

    if normalized_type in {"txt", "md"}:
        return source.read_text(encoding="utf-8")
    if normalized_type == "docx":
        return _parse_docx(source)
    if normalized_type == "pdf":
        return _parse_pdf(source)
    raise ValueError(f"不支持的文件类型：{file_type}")


def _parse_docx(path: Path) -> str:
    from docx import Document

    document = Document(str(path))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _parse_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)
