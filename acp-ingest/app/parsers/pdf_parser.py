"""PDF parser with OCR support for processing PDF documents."""

import logging
import tempfile
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import PyPDF2
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


class PDFParser:
    """Parser for PDF documents with OCR fallback."""
    
    def __init__(self):
        self.ocr_enabled = True
        self.ocr_languages = ['eng']  # Default to English
        
        # Check if Tesseract is available
        try:
            pytesseract.get_tesseract_version()
        except Exception:
            logger.warning("Tesseract not available, OCR will be disabled")
            self.ocr_enabled = False
    
    async def parse(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse PDF content.
        
        Args:
            content: PDF file path (content is actually file path for PDFs)
            metadata: Additional metadata
            
        Returns:
            List[Dict[str, Any]]: Parsed documents
        """
        try:
            logger.info("Parsing PDF content")
            
            # For PDF, content is the file path
            pdf_path = content
            
            # Try text extraction first
            documents = await self._extract_text_from_pdf(pdf_path, metadata)
            
            # If text extraction failed or returned empty content, try OCR
            if not documents or all(not doc['content'].strip() for doc in documents):
                if self.ocr_enabled:
                    logger.info("Text extraction failed, trying OCR")
                    documents = await self._extract_text_with_ocr(pdf_path, metadata)
                else:
                    logger.warning("OCR not available, cannot process image-based PDF")
            
            logger.info(f"Parsed {len(documents)} pages from PDF")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            raise
    
    async def _extract_text_from_pdf(self, pdf_path: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract text directly from PDF.
        
        Args:
            pdf_path: Path to PDF file
            metadata: Additional metadata
            
        Returns:
            List[Dict[str, Any]]: Extracted documents
        """
        documents = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Extract PDF metadata
                pdf_metadata = self._extract_pdf_metadata(pdf_reader)
                
                # Process each page
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        # Extract text from page
                        text = page.extract_text()
                        
                        if text.strip():
                            # Clean up text
                            text = self._clean_extracted_text(text)
                            
                            # Create document for this page
                            document = {
                                'id': f"pdf_page_{page_num + 1}",
                                'title': f"Page {page_num + 1}",
                                'content': text,
                                'author': pdf_metadata.get('author', ''),
                                'created_at': pdf_metadata.get('created_at', ''),
                                'metadata': {
                                    'source_type': 'pdf',
                                    'page_number': page_num + 1,
                                    'total_pages': len(pdf_reader.pages),
                                    'extraction_method': 'text',
                                    **pdf_metadata,
                                    **metadata
                                }
                            }
                            
                            documents.append(document)
                    
                    except Exception as e:
                        logger.error(f"Failed to extract text from page {page_num + 1}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Failed to read PDF file: {e}")
            raise
        
        return documents
    
    async def _extract_text_with_ocr(self, pdf_path: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract text from PDF using OCR.
        
        Args:
            pdf_path: Path to PDF file
            metadata: Additional metadata
            
        Returns:
            List[Dict[str, Any]]: Extracted documents
        """
        documents = []
        
        try:
            # Convert PDF to images
            images = convert_from_path(pdf_path)
            
            for page_num, image in enumerate(images):
                try:
                    # Perform OCR on the image
                    text = pytesseract.image_to_string(
                        image,
                        lang='+'.join(self.ocr_languages),
                        config='--psm 6'  # Assume uniform block of text
                    )
                    
                    if text.strip():
                        # Clean up OCR text
                        text = self._clean_ocr_text(text)
                        
                        # Create document for this page
                        document = {
                            'id': f"pdf_page_{page_num + 1}_ocr",
                            'title': f"Page {page_num + 1} (OCR)",
                            'content': text,
                            'author': '',
                            'created_at': '',
                            'metadata': {
                                'source_type': 'pdf',
                                'page_number': page_num + 1,
                                'total_pages': len(images),
                                'extraction_method': 'ocr',
                                'ocr_languages': self.ocr_languages,
                                **metadata
                            }
                        }
                        
                        documents.append(document)
                
                except Exception as e:
                    logger.error(f"OCR failed for page {page_num + 1}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            raise
        
        return documents
    
    def _extract_pdf_metadata(self, pdf_reader: PyPDF2.PdfReader) -> Dict[str, Any]:
        """
        Extract metadata from PDF.
        
        Args:
            pdf_reader: PyPDF2 PdfReader object
            
        Returns:
            Dict[str, Any]: PDF metadata
        """
        metadata = {}
        
        try:
            if pdf_reader.metadata:
                pdf_info = pdf_reader.metadata
                
                # Extract common metadata fields
                if '/Title' in pdf_info:
                    metadata['title'] = str(pdf_info['/Title'])
                
                if '/Author' in pdf_info:
                    metadata['author'] = str(pdf_info['/Author'])
                
                if '/Subject' in pdf_info:
                    metadata['subject'] = str(pdf_info['/Subject'])
                
                if '/Creator' in pdf_info:
                    metadata['creator'] = str(pdf_info['/Creator'])
                
                if '/Producer' in pdf_info:
                    metadata['producer'] = str(pdf_info['/Producer'])
                
                if '/CreationDate' in pdf_info:
                    creation_date = pdf_info['/CreationDate']
                    if creation_date:
                        try:
                            # Parse PDF date format (D:YYYYMMDDHHmmSSOHH'mm')
                            date_str = str(creation_date)
                            if date_str.startswith('D:'):
                                date_str = date_str[2:]
                            
                            # Extract date part (first 14 characters: YYYYMMDDHHMMSS)
                            if len(date_str) >= 14:
                                date_part = date_str[:14]
                                parsed_date = datetime.strptime(date_part, '%Y%m%d%H%M%S')
                                metadata['created_at'] = parsed_date.isoformat()
                        except Exception as e:
                            logger.warning(f"Failed to parse creation date: {e}")
                
                if '/ModDate' in pdf_info:
                    mod_date = pdf_info['/ModDate']
                    if mod_date:
                        try:
                            date_str = str(mod_date)
                            if date_str.startswith('D:'):
                                date_str = date_str[2:]
                            
                            if len(date_str) >= 14:
                                date_part = date_str[:14]
                                parsed_date = datetime.strptime(date_part, '%Y%m%d%H%M%S')
                                metadata['modified_at'] = parsed_date.isoformat()
                        except Exception as e:
                            logger.warning(f"Failed to parse modification date: {e}")
        
        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata: {e}")
        
        return metadata
    
    def _clean_extracted_text(self, text: str) -> str:
        """
        Clean up text extracted directly from PDF.
        
        Args:
            text: Raw extracted text
            
        Returns:
            str: Cleaned text
        """
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Fix common PDF extraction issues
        text = text.replace('\x00', '')  # Remove null characters
        text = text.replace('\uf0b7', '•')  # Replace bullet character
        text = text.replace('\uf020', ' ')  # Replace space character
        
        # Normalize line breaks
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        return text.strip()
    
    def _clean_ocr_text(self, text: str) -> str:
        """
        Clean up OCR-extracted text.
        
        Args:
            text: Raw OCR text
            
        Returns:
            str: Cleaned text
        """
        # Remove excessive whitespace
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # Skip empty lines
                # Remove common OCR artifacts
                line = line.replace('|', 'I')  # Common OCR mistake
                line = line.replace('0', 'O')  # In some contexts
                
                cleaned_lines.append(line)
        
        # Join lines with proper spacing
        text = '\n'.join(cleaned_lines)
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def validate_pdf(self, file_path: str) -> bool:
        """
        Validate if file is a valid PDF.
        
        Args:
            file_path: Path to file
            
        Returns:
            bool: True if valid PDF
        """
        try:
            with open(file_path, 'rb') as file:
                # Check PDF header
                header = file.read(4)
                if header != b'%PDF':
                    return False
                
                # Try to read with PyPDF2
                file.seek(0)
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Check if we can access pages
                num_pages = len(pdf_reader.pages)
                return num_pages > 0
                
        except Exception:
            return False
    
    def get_pdf_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get basic PDF information.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dict[str, Any]: PDF information
        """
        info = {}
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                info['num_pages'] = len(pdf_reader.pages)
                info['encrypted'] = pdf_reader.is_encrypted
                
                # Get metadata
                metadata = self._extract_pdf_metadata(pdf_reader)
                info.update(metadata)
                
                # Check if text extractable
                try:
                    first_page = pdf_reader.pages[0]
                    text = first_page.extract_text()
                    info['text_extractable'] = bool(text.strip())
                except:
                    info['text_extractable'] = False
                
        except Exception as e:
            info['error'] = str(e)
        
        return info
    
    def set_ocr_languages(self, languages: List[str]):
        """
        Set OCR languages.
        
        Args:
            languages: List of language codes (e.g., ['eng', 'fra'])
        """
        self.ocr_languages = languages
        logger.info(f"OCR languages set to: {languages}")
    
    def is_ocr_available(self) -> bool:
        """
        Check if OCR is available.
        
        Returns:
            bool: True if OCR is available
        """
        return self.ocr_enabled

