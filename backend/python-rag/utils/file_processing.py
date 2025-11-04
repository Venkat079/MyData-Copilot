# python-rag/utils/file_processing.py
import os
import shutil
import tempfile
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy imports
def _import_pdfplumber():
    try:
        import pdfplumber
        return pdfplumber
    except Exception as e:
        logger.debug("pdfplumber not available: %s", e)
        return None

def _import_pypdf2():
    try:
        import PyPDF2
        return PyPDF2
    except Exception as e:
        logger.debug("PyPDF2 not available: %s", e)
        return None

def _import_pymupdf():
    try:
        import fitz  # PyMuPDF
        return fitz
    except Exception as e:
        logger.debug("PyMuPDF (fitz) not available: %s", e)
        return None

def _import_docx():
    try:
        import docx
        return docx
    except Exception as e:
        logger.debug("python-docx not available: %s", e)
        return None

def _import_pdf2image_and_pytesseract():
    try:
        import pdf2image
        import pytesseract
        from PIL import Image
        return pdf2image, pytesseract, Image
    except Exception as e:
        logger.debug("pdf2image/pytesseract not available: %s", e)
        return None, None, None

def _import_easyocr():
    try:
        import easyocr
        return easyocr
    except Exception as e:
        logger.debug("easyocr not available: %s", e)
        return None

# Extraction helpers
def extract_text_from_pdf(path: str) -> str:
    # 1) try pdfplumber
    pdfplumber = _import_pdfplumber()
    if pdfplumber:
        try:
            parts = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    txt = page.extract_text()
                    if txt:
                        parts.append(txt)
            if parts:
                return "\n\n".join(parts).strip()
        except Exception:
            logger.exception("pdfplumber extraction failed for %s", path)

    # 2) try PyPDF2
    PyPDF2 = _import_pypdf2()
    if PyPDF2:
        try:
            parts = []
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for p in reader.pages:
                    try:
                        t = p.extract_text()
                    except Exception:
                        t = ""
                    if t:
                        parts.append(t)
            if parts:
                return "\n\n".join(parts).strip()
        except Exception:
            logger.exception("PyPDF2 extraction failed for %s", path)

    # 3) try PyMuPDF (fitz)
    fitz = _import_pymupdf()
    if fitz:
        try:
            doc = fitz.open(path)
            pages_text = []
            for p in doc:
                try:
                    pages_text.append(p.get_text())
                except Exception:
                    continue
            if pages_text:
                doc.close()
                return "\n\n".join([t for t in pages_text if t]).strip()
            doc.close()
        except Exception:
            logger.exception("PyMuPDF extraction failed for %s", path)

    # 4) OCR fallback (pytesseract/pdf2image)
    pdf2image, pytesseract, Image = _import_pdf2image_and_pytesseract()
    if pdf2image and pytesseract:
        try:
            pages = pdf2image.convert_from_path(path, dpi=200)
            txts = []
            for im in pages:
                try:
                    txt = pytesseract.image_to_string(im)
                    if txt and txt.strip():
                        txts.append(txt)
                except Exception:
                    logger.exception("tesseract failed on page")
            if txts:
                return "\n\n".join(txts).strip()
        except Exception:
            logger.exception("pytesseract/pdf2image OCR failed for %s", path)

    # 5) easyocr fallback
    easyocr = _import_easyocr()
    if easyocr:
        try:
            reader = easyocr.Reader(["en"], gpu=False)
            pdf2image_mod, _, _ = _import_pdf2image_and_pytesseract()
            if pdf2image_mod:
                pages = pdf2image_mod.convert_from_path(path, dpi=200)
                all_text = []
                for p in pages:
                    res = reader.readtext(p)
                    page_text = " ".join([r[1] for r in res])
                    if page_text.strip():
                        all_text.append(page_text)
                if all_text:
                    return "\n\n".join(all_text).strip()
        except Exception:
            logger.exception("easyocr fallback failed for %s", path)

    return ""


def extract_text_from_docx(path: str) -> str:
    docx = _import_docx()
    if not docx:
        logger.debug("python-docx not installed; cannot read .docx")
        return ""
    try:
        d = docx.Document(path)
        paragraphs = [p.text for p in d.paragraphs if p.text and p.text.strip()]
        return "\n\n".join(paragraphs).strip()
    except Exception:
        logger.exception("Failed to extract text from docx %s", path)
        return ""


def convert_doc_to_docx_win32(src_path: str, dst_path: str) -> bool:
    try:
        import win32com.client as win32
        import pythoncom
    except Exception:
        logger.debug("pywin32/pythoncom not available for DOC->DOCX conversion")
        return False

    try:
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        except Exception:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

        word = win32.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(os.path.abspath(src_path), ReadOnly=1)
        doc.SaveAs(os.path.abspath(dst_path), FileFormat=16)
        doc.Close(False)
        word.Quit()
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        logger.info("Converted DOC -> DOCX via MS Word COM: %s -> %s", src_path, dst_path)
        return True
    except Exception:
        logger.exception("Word COM conversion failed for %s", src_path)
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        return False


def convert_doc_to_docx_libreoffice(src_path: str, dst_path: str) -> bool:
    soffice_cmd = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice_cmd:
        logger.debug("LibreOffice (soffice) not found on PATH")
        return False
    outdir = os.path.dirname(dst_path)
    try:
        cmd = [soffice_cmd, "--headless", "--convert-to", "docx", "--outdir", outdir, src_path]
        subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
        return True
    except Exception:
        logger.exception("LibreOffice conversion failed for %s", src_path)
        return False


def extract_text_simple(path: str) -> str:
    if not path or not os.path.exists(path):
        logger.debug("extract_text_simple: path missing or does not exist: %s", path)
        return ""

    p = Path(path)
    ext = p.suffix.lower()
    tmpdir = tempfile.mkdtemp(prefix="extract_")
    tmp_path = os.path.join(tmpdir, p.name)
    try:
        shutil.copy2(path, tmp_path)
    except Exception:
        tmp_path = path

    try:
        if ext in [".txt", ".md", ".csv", ".json"]:
            try:
                with open(tmp_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read().strip()
            except Exception:
                logger.exception("Failed reading plain text file %s", tmp_path)
                return ""

        if ext == ".pdf":
            logger.debug("Attempting pdf extraction for %s", tmp_path)
            txt = extract_text_from_pdf(tmp_path)
            if txt:
                logger.info("PDF extraction succeeded for %s (len=%d)", tmp_path, len(txt))
                return txt
            logger.info("No PDF text extracted for %s", tmp_path)
            return ""

        if ext == ".docx":
            txt = extract_text_from_docx(tmp_path)
            if txt:
                logger.info("DOCX extraction succeeded for %s (len=%d)", tmp_path, len(txt))
                return txt
            logger.info("python-docx returned no text for %s", tmp_path)
            return ""

        if ext == ".doc":
            logger.info("DOC file detected - trying MS Word COM conversion for %s", tmp_path)
            target_docx = os.path.join(tmpdir, p.stem + ".docx")
            ok = convert_doc_to_docx_win32(tmp_path, target_docx)
            if not ok:
                ok = convert_doc_to_docx_libreoffice(tmp_path, target_docx)
            if ok and os.path.exists(target_docx):
                txt = extract_text_from_docx(target_docx)
                if txt:
                    logger.info("DOC conversion+extraction succeeded for %s (len=%d)", tmp_path, len(txt))
                    return txt
                else:
                    logger.info("Converted DOC produced no text for %s", tmp_path)
                    return ""
            logger.info("No extractable text from .doc file %s (conversion failed)", tmp_path)
            return ""

        # fallback: try read as text
        try:
            with open(tmp_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()
        except Exception:
            return ""
    finally:
        try:
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)
        except Exception:
            pass
