"""Jira CSV parser for processing exported Jira tickets."""

import logging
import csv
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class JiraParser:
    """Parser for Jira CSV exports."""
    
    def __init__(self):
        # Common Jira CSV field mappings
        self.field_mappings = {
            'Issue key': 'id',
            'Issue Key': 'id',
            'Key': 'id',
            'Summary': 'title',
            'Issue Type': 'issue_type',
            'Status': 'status',
            'Priority': 'priority',
            'Reporter': 'reporter',
            'Assignee': 'assignee',
            'Created': 'created_at',
            'Updated': 'updated_at',
            'Resolved': 'resolved_at',
            'Description': 'description',
            'Comment': 'comments',
            'Comments': 'comments',
            'Labels': 'labels',
            'Components': 'components',
            'Fix Version/s': 'fix_versions',
            'Affects Version/s': 'affects_versions',
            'Environment': 'environment',
            'Project key': 'project',
            'Project Key': 'project',
        }
    
    async def parse(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse Jira CSV content.
        
        Args:
            content: CSV content as string
            metadata: Additional metadata
            
        Returns:
            List[Dict[str, Any]]: Parsed documents
        """
        try:
            logger.info("Parsing Jira CSV content")
            
            # Read CSV content
            df = pd.read_csv(io.StringIO(content))
            
            # Normalize column names
            df.columns = df.columns.str.strip()
            
            documents = []
            for index, row in df.iterrows():
                try:
                    document = await self._parse_row(row, metadata)
                    if document:
                        documents.append(document)
                except Exception as e:
                    logger.error(f"Failed to parse row {index}: {e}")
                    continue
            
            logger.info(f"Parsed {len(documents)} Jira tickets")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to parse Jira CSV: {e}")
            raise
    
    async def _parse_row(self, row: pd.Series, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a single CSV row into a document.
        
        Args:
            row: Pandas Series representing a CSV row
            metadata: Additional metadata
            
        Returns:
            Optional[Dict[str, Any]]: Parsed document or None if invalid
        """
        try:
            # Map fields to standardized names
            mapped_data = {}
            for csv_field, standard_field in self.field_mappings.items():
                if csv_field in row.index and pd.notna(row[csv_field]):
                    mapped_data[standard_field] = str(row[csv_field]).strip()
            
            # Ensure we have required fields
            if 'id' not in mapped_data or 'title' not in mapped_data:
                logger.warning(f"Skipping row without required fields: {row.to_dict()}")
                return None
            
            # Build content text
            content_parts = []
            
            # Add title
            content_parts.append(f"# {mapped_data['title']}")
            
            # Add basic info
            if 'issue_type' in mapped_data:
                content_parts.append(f"**Type:** {mapped_data['issue_type']}")
            if 'status' in mapped_data:
                content_parts.append(f"**Status:** {mapped_data['status']}")
            if 'priority' in mapped_data:
                content_parts.append(f"**Priority:** {mapped_data['priority']}")
            if 'reporter' in mapped_data:
                content_parts.append(f"**Reporter:** {mapped_data['reporter']}")
            if 'assignee' in mapped_data:
                content_parts.append(f"**Assignee:** {mapped_data['assignee']}")
            
            # Add description
            if 'description' in mapped_data and mapped_data['description']:
                content_parts.append("## Description")
                content_parts.append(mapped_data['description'])
            
            # Add comments
            if 'comments' in mapped_data and mapped_data['comments']:
                content_parts.append("## Comments")
                content_parts.append(mapped_data['comments'])
            
            # Add environment info
            if 'environment' in mapped_data and mapped_data['environment']:
                content_parts.append("## Environment")
                content_parts.append(mapped_data['environment'])
            
            # Add labels and components
            if 'labels' in mapped_data and mapped_data['labels']:
                content_parts.append(f"**Labels:** {mapped_data['labels']}")
            if 'components' in mapped_data and mapped_data['components']:
                content_parts.append(f"**Components:** {mapped_data['components']}")
            
            content = "\n\n".join(content_parts)
            
            # Parse dates
            created_at = self._parse_date(mapped_data.get('created_at'))
            updated_at = self._parse_date(mapped_data.get('updated_at'))
            resolved_at = self._parse_date(mapped_data.get('resolved_at'))
            
            # Build document
            document = {
                'id': mapped_data['id'],
                'title': mapped_data['title'],
                'content': content,
                'author': mapped_data.get('reporter', ''),
                'created_at': created_at.isoformat() if created_at else '',
                'metadata': {
                    'source_type': 'jira_csv',
                    'issue_key': mapped_data['id'],
                    'issue_type': mapped_data.get('issue_type', ''),
                    'status': mapped_data.get('status', ''),
                    'priority': mapped_data.get('priority', ''),
                    'reporter': mapped_data.get('reporter', ''),
                    'assignee': mapped_data.get('assignee', ''),
                    'project': mapped_data.get('project', ''),
                    'labels': mapped_data.get('labels', ''),
                    'components': mapped_data.get('components', ''),
                    'fix_versions': mapped_data.get('fix_versions', ''),
                    'affects_versions': mapped_data.get('affects_versions', ''),
                    'created_at': created_at.isoformat() if created_at else '',
                    'updated_at': updated_at.isoformat() if updated_at else '',
                    'resolved_at': resolved_at.isoformat() if resolved_at else '',
                    **metadata
                }
            }
            
            return document
            
        except Exception as e:
            logger.error(f"Failed to parse row: {e}")
            return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date string to datetime object.
        
        Args:
            date_str: Date string
            
        Returns:
            Optional[datetime]: Parsed datetime or None
        """
        if not date_str or date_str.strip() == '':
            return None
        
        # Common Jira date formats
        date_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%m/%d/%Y %H:%M:%S',
            '%m/%d/%Y %H:%M',
            '%m/%d/%Y',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S',
        ]
        
        for date_format in date_formats:
            try:
                return datetime.strptime(date_str.strip(), date_format)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def validate_csv_format(self, content: str) -> bool:
        """
        Validate if the content is a valid Jira CSV.
        
        Args:
            content: CSV content
            
        Returns:
            bool: True if valid Jira CSV format
        """
        try:
            df = pd.read_csv(io.StringIO(content))
            
            # Check for common Jira columns
            required_columns = ['Issue key', 'Issue Key', 'Key', 'Summary']
            has_required = any(col in df.columns for col in required_columns)
            
            if not has_required:
                return False
            
            # Check if we have at least one row
            if len(df) == 0:
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_supported_fields(self) -> List[str]:
        """
        Get list of supported Jira fields.
        
        Returns:
            List[str]: Supported field names
        """
        return list(self.field_mappings.keys())
    
    def detect_csv_dialect(self, content: str) -> csv.Dialect:
        """
        Detect CSV dialect from content.
        
        Args:
            content: CSV content
            
        Returns:
            csv.Dialect: Detected dialect
        """
        try:
            sample = content[:1024]  # Use first 1KB for detection
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample)
            return dialect
        except Exception:
            # Return default dialect
            return csv.excel

