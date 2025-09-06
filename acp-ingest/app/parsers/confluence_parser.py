"""Confluence HTML/XML parser for processing exported Confluence pages."""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from defusedxml import ElementTree as ET

logger = logging.getLogger(__name__)


class ConfluenceParser:
    """Parser for Confluence HTML/XML exports."""
    
    def __init__(self):
        # HTML tags to preserve structure
        self.structure_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'section']
        self.content_tags = ['pre', 'code', 'blockquote', 'ul', 'ol', 'li', 'table', 'tr', 'td', 'th']
        
        # Tags to ignore
        self.ignore_tags = ['script', 'style', 'nav', 'footer', 'header', 'aside']
    
    async def parse(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse Confluence HTML/XML content.
        
        Args:
            content: HTML/XML content as string
            metadata: Additional metadata
            
        Returns:
            List[Dict[str, Any]]: Parsed documents
        """
        try:
            logger.info("Parsing Confluence content")
            
            # Detect format (HTML vs XML)
            if content.strip().startswith('<?xml'):
                return await self._parse_xml(content, metadata)
            else:
                return await self._parse_html(content, metadata)
                
        except Exception as e:
            logger.error(f"Failed to parse Confluence content: {e}")
            raise
    
    async def _parse_html(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse Confluence HTML export.
        
        Args:
            content: HTML content
            metadata: Additional metadata
            
        Returns:
            List[Dict[str, Any]]: Parsed documents
        """
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove unwanted elements
            for tag_name in self.ignore_tags:
                for tag in soup.find_all(tag_name):
                    tag.decompose()
            
            documents = []
            
            # Try to find individual pages or sections
            pages = self._extract_pages_from_html(soup)
            
            if not pages:
                # Treat entire content as single document
                pages = [soup]
            
            for i, page_soup in enumerate(pages):
                try:
                    document = await self._parse_html_page(page_soup, metadata, i)
                    if document:
                        documents.append(document)
                except Exception as e:
                    logger.error(f"Failed to parse HTML page {i}: {e}")
                    continue
            
            logger.info(f"Parsed {len(documents)} Confluence pages from HTML")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to parse HTML content: {e}")
            raise
    
    async def _parse_xml(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse Confluence XML export.
        
        Args:
            content: XML content
            metadata: Additional metadata
            
        Returns:
            List[Dict[str, Any]]: Parsed documents
        """
        try:
            root = ET.fromstring(content)
            documents = []
            
            # Look for page elements
            pages = root.findall('.//page') or root.findall('.//object[@class="Page"]')
            
            if not pages:
                # Try to parse as single document
                document = await self._parse_xml_element(root, metadata, 0)
                if document:
                    documents.append(document)
            else:
                for i, page in enumerate(pages):
                    try:
                        document = await self._parse_xml_element(page, metadata, i)
                        if document:
                            documents.append(document)
                    except Exception as e:
                        logger.error(f"Failed to parse XML page {i}: {e}")
                        continue
            
            logger.info(f"Parsed {len(documents)} Confluence pages from XML")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to parse XML content: {e}")
            raise
    
    def _extract_pages_from_html(self, soup: BeautifulSoup) -> List[BeautifulSoup]:
        """
        Extract individual pages from HTML soup.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List[BeautifulSoup]: List of page soups
        """
        pages = []
        
        # Look for common Confluence page containers
        page_selectors = [
            '.page-content',
            '.wiki-content',
            '.content-body',
            'article',
            '.main-content',
            '[data-type="page"]'
        ]
        
        for selector in page_selectors:
            page_elements = soup.select(selector)
            if page_elements:
                pages.extend(page_elements)
                break
        
        # If no specific containers found, look for sections with headings
        if not pages:
            # Split by h1 tags
            h1_tags = soup.find_all('h1')
            if len(h1_tags) > 1:
                for h1 in h1_tags:
                    page_content = []
                    current = h1
                    
                    # Collect content until next h1 or end
                    while current:
                        if current.name == 'h1' and current != h1:
                            break
                        page_content.append(current)
                        current = current.next_sibling
                    
                    if page_content:
                        page_soup = BeautifulSoup('', 'html.parser')
                        for element in page_content:
                            if hasattr(element, 'name'):
                                page_soup.append(element.extract())
                        pages.append(page_soup)
        
        return pages
    
    async def _parse_html_page(
        self,
        page_soup: BeautifulSoup,
        metadata: Dict[str, Any],
        page_index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single HTML page.
        
        Args:
            page_soup: BeautifulSoup object for the page
            metadata: Additional metadata
            page_index: Page index
            
        Returns:
            Optional[Dict[str, Any]]: Parsed document or None
        """
        try:
            # Extract title
            title = self._extract_title_from_html(page_soup)
            if not title:
                title = f"Confluence Page {page_index + 1}"
            
            # Extract content
            content = self._extract_content_from_html(page_soup)
            if not content.strip():
                return None
            
            # Extract metadata
            page_metadata = self._extract_metadata_from_html(page_soup)
            
            # Build document
            document = {
                'id': f"confluence_page_{page_index}",
                'title': title,
                'content': content,
                'author': page_metadata.get('author', ''),
                'created_at': page_metadata.get('created_at', ''),
                'metadata': {
                    'source_type': 'confluence_html',
                    'page_index': page_index,
                    'page_title': title,
                    **page_metadata,
                    **metadata
                }
            }
            
            return document
            
        except Exception as e:
            logger.error(f"Failed to parse HTML page: {e}")
            return None
    
    async def _parse_xml_element(
        self,
        element: ET.Element,
        metadata: Dict[str, Any],
        page_index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single XML element as a page.
        
        Args:
            element: XML element
            metadata: Additional metadata
            page_index: Page index
            
        Returns:
            Optional[Dict[str, Any]]: Parsed document or None
        """
        try:
            # Extract title
            title = self._extract_title_from_xml(element)
            if not title:
                title = f"Confluence Page {page_index + 1}"
            
            # Extract content
            content = self._extract_content_from_xml(element)
            if not content.strip():
                return None
            
            # Extract metadata
            page_metadata = self._extract_metadata_from_xml(element)
            
            # Build document
            document = {
                'id': page_metadata.get('id', f"confluence_page_{page_index}"),
                'title': title,
                'content': content,
                'author': page_metadata.get('author', ''),
                'created_at': page_metadata.get('created_at', ''),
                'metadata': {
                    'source_type': 'confluence_xml',
                    'page_index': page_index,
                    'page_title': title,
                    **page_metadata,
                    **metadata
                }
            }
            
            return document
            
        except Exception as e:
            logger.error(f"Failed to parse XML element: {e}")
            return None
    
    def _extract_title_from_html(self, soup: BeautifulSoup) -> str:
        """Extract title from HTML soup."""
        # Try different title selectors
        title_selectors = [
            'h1',
            '.page-title',
            '.wiki-title',
            'title',
            '[data-title]'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title:
                    return title
        
        return ""
    
    def _extract_title_from_xml(self, element: ET.Element) -> str:
        """Extract title from XML element."""
        # Try different title attributes/elements
        title_paths = [
            'title',
            '@title',
            'name',
            '@name',
            'property[@name="title"]',
            'property[@name="name"]'
        ]
        
        for path in title_paths:
            if path.startswith('@'):
                # Attribute
                attr_name = path[1:]
                title = element.get(attr_name)
                if title:
                    return title
            else:
                # Element
                title_elem = element.find(path)
                if title_elem is not None:
                    title = title_elem.text
                    if title:
                        return title.strip()
        
        return ""
    
    def _extract_content_from_html(self, soup: BeautifulSoup) -> str:
        """Extract and format content from HTML soup."""
        content_parts = []
        
        # Process elements in order
        for element in soup.find_all(self.structure_tags + self.content_tags):
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # Heading
                level = int(element.name[1])
                prefix = '#' * level
                text = element.get_text(strip=True)
                if text:
                    content_parts.append(f"{prefix} {text}")
            
            elif element.name == 'p':
                # Paragraph
                text = element.get_text(strip=True)
                if text:
                    content_parts.append(text)
            
            elif element.name in ['pre', 'code']:
                # Code block
                text = element.get_text()
                if text.strip():
                    content_parts.append(f"```\n{text}\n```")
            
            elif element.name == 'blockquote':
                # Quote
                text = element.get_text(strip=True)
                if text:
                    content_parts.append(f"> {text}")
            
            elif element.name in ['ul', 'ol']:
                # List
                list_items = []
                for li in element.find_all('li', recursive=False):
                    item_text = li.get_text(strip=True)
                    if item_text:
                        prefix = '-' if element.name == 'ul' else '1.'
                        list_items.append(f"{prefix} {item_text}")
                
                if list_items:
                    content_parts.extend(list_items)
            
            elif element.name == 'table':
                # Table
                table_content = self._extract_table_content(element)
                if table_content:
                    content_parts.append(table_content)
        
        # If no structured content found, get all text
        if not content_parts:
            text = soup.get_text(separator='\n', strip=True)
            if text:
                content_parts.append(text)
        
        return '\n\n'.join(content_parts)
    
    def _extract_content_from_xml(self, element: ET.Element) -> str:
        """Extract content from XML element."""
        content_parts = []
        
        # Look for body/content elements
        content_elements = element.findall('.//body') or element.findall('.//content')
        
        if content_elements:
            for content_elem in content_elements:
                text = ET.tostring(content_elem, encoding='unicode', method='text')
                if text.strip():
                    content_parts.append(text.strip())
        else:
            # Get all text content
            text = ET.tostring(element, encoding='unicode', method='text')
            if text.strip():
                content_parts.append(text.strip())
        
        return '\n\n'.join(content_parts)
    
    def _extract_table_content(self, table: Tag) -> str:
        """Extract content from HTML table."""
        rows = []
        
        for tr in table.find_all('tr'):
            cells = []
            for cell in tr.find_all(['td', 'th']):
                cell_text = cell.get_text(strip=True)
                cells.append(cell_text)
            
            if cells:
                rows.append(' | '.join(cells))
        
        if rows:
            # Add header separator if first row looks like headers
            if len(rows) > 1:
                header_sep = ' | '.join(['---'] * len(rows[0].split(' | ')))
                rows.insert(1, header_sep)
            
            return '\n'.join(rows)
        
        return ""
    
    def _extract_metadata_from_html(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract metadata from HTML soup."""
        metadata = {}
        
        # Look for meta tags
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            name = meta.get('name') or meta.get('property')
            content = meta.get('content')
            if name and content:
                metadata[name] = content
        
        # Look for data attributes
        for element in soup.find_all(attrs={'data-author': True}):
            metadata['author'] = element.get('data-author')
        
        for element in soup.find_all(attrs={'data-created': True}):
            metadata['created_at'] = element.get('data-created')
        
        for element in soup.find_all(attrs={'data-modified': True}):
            metadata['modified_at'] = element.get('data-modified')
        
        return metadata
    
    def _extract_metadata_from_xml(self, element: ET.Element) -> Dict[str, Any]:
        """Extract metadata from XML element."""
        metadata = {}
        
        # Extract common attributes
        for attr in ['id', 'author', 'creator', 'created', 'modified', 'version']:
            value = element.get(attr)
            if value:
                metadata[attr] = value
        
        # Look for property elements
        for prop in element.findall('.//property'):
            name = prop.get('name')
            value = prop.text or prop.get('value')
            if name and value:
                metadata[name] = value
        
        return metadata
    
    def validate_format(self, content: str) -> bool:
        """
        Validate if content is valid Confluence HTML/XML.
        
        Args:
            content: Content to validate
            
        Returns:
            bool: True if valid format
        """
        try:
            if content.strip().startswith('<?xml'):
                # Try to parse as XML
                ET.fromstring(content)
                return True
            else:
                # Try to parse as HTML
                soup = BeautifulSoup(content, 'html.parser')
                # Check for common Confluence indicators
                confluence_indicators = [
                    'confluence',
                    'wiki-content',
                    'page-content',
                    'atlassian'
                ]
                
                content_lower = content.lower()
                return any(indicator in content_lower for indicator in confluence_indicators)
                
        except Exception:
            return False

