"""Enhanced audit logging service with immutable audit trails."""

import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models import AuditLog, User
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class AuditAction(Enum):
    """Standardized audit actions."""
    # Authentication actions
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    TOKEN_REFRESH = "auth.token.refresh"
    PASSWORD_CHANGE = "auth.password.change"
    
    # User management actions
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ACTIVATE = "user.activate"
    USER_DEACTIVATE = "user.deactivate"
    
    # Role management actions
    ROLE_ASSIGN = "role.assign"
    ROLE_REMOVE = "role.remove"
    ROLE_CREATE = "role.create"
    ROLE_UPDATE = "role.update"
    ROLE_DELETE = "role.delete"
    
    # Ingestion actions
    INGEST_UPLOAD = "ingest.upload"
    INGEST_PASTE = "ingest.paste"
    INGEST_START = "ingest.start"
    INGEST_COMPLETE = "ingest.complete"
    INGEST_FAIL = "ingest.fail"
    INGEST_RETRY = "ingest.retry"
    INGEST_DELETE = "ingest.delete"
    
    # Search actions
    SEARCH_QUERY = "search.query"
    SEARCH_EXPORT = "search.export"
    SEARCH_VIEW_CHUNK = "search.view_chunk"
    
    # Data actions
    DATA_VIEW = "data.view"
    DATA_EXPORT = "data.export"
    DATA_DELETE = "data.delete"
    PII_REDACT = "data.pii.redact"
    PII_VIEW_ORIGINAL = "data.pii.view_original"
    
    # System actions
    SYSTEM_CONFIG_CHANGE = "system.config.change"
    SYSTEM_BACKUP = "system.backup"
    SYSTEM_RESTORE = "system.restore"
    SYSTEM_MAINTENANCE = "system.maintenance"
    
    # Security actions
    SECURITY_VIOLATION = "security.violation"
    SECURITY_ALERT = "security.alert"
    ACCESS_DENIED = "security.access_denied"


class AuditSeverity(Enum):
    """Audit event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditService:
    """Service for managing immutable audit logs."""
    
    def __init__(self):
        self.hash_algorithm = 'sha256'
    
    def _calculate_hash(self, data: Dict[str, Any]) -> str:
        """
        Calculate hash for audit log entry to ensure immutability.
        
        Args:
            data: Audit log data
            
        Returns:
            str: Hash of the data
        """
        # Create a canonical string representation
        canonical_data = json.dumps(data, sort_keys=True, separators=(',', ':'))
        
        # Calculate hash
        hash_obj = hashlib.new(self.hash_algorithm)
        hash_obj.update(canonical_data.encode('utf-8'))
        
        return hash_obj.hexdigest()
    
    def _get_previous_hash(self, db: Session) -> Optional[str]:
        """
        Get the hash of the most recent audit log entry.
        
        Args:
            db: Database session
            
        Returns:
            Optional[str]: Previous hash or None if no previous entries
        """
        latest_entry = db.query(AuditLog).order_by(desc(AuditLog.created_at)).first()
        return latest_entry.hash if latest_entry else None
    
    async def log_event(
        self,
        action: AuditAction,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.LOW,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        db: Session = None
    ) -> AuditLog:
        """
        Log an audit event with immutable hash chain.
        
        Args:
            action: Action being audited
            user_id: ID of user performing action
            resource_type: Type of resource being acted upon
            resource_id: ID of resource being acted upon
            details: Additional details about the action
            severity: Severity level of the event
            ip_address: IP address of the user
            user_agent: User agent string
            db: Database session
            
        Returns:
            AuditLog: Created audit log entry
        """
        try:
            timestamp = datetime.utcnow()
            
            # Prepare audit data
            audit_data = {
                'action': action.value,
                'user_id': user_id,
                'resource_type': resource_type,
                'resource_id': resource_id,
                'details': details or {},
                'severity': severity.value,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'timestamp': timestamp.isoformat()
            }
            
            # Get previous hash for chain integrity
            previous_hash = self._get_previous_hash(db)
            if previous_hash:
                audit_data['previous_hash'] = previous_hash
            
            # Calculate hash for this entry
            entry_hash = self._calculate_hash(audit_data)
            
            # Create audit log entry
            audit_log = AuditLog(
                action=action.value,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
                severity=severity.value,
                ip_address=ip_address,
                user_agent=user_agent,
                hash=entry_hash,
                previous_hash=previous_hash,
                created_at=timestamp
            )
            
            db.add(audit_log)
            db.commit()
            
            logger.info("Audit event logged", action=action.value, user_id=user_id, hash=entry_hash)
            return audit_log
            
        except Exception as e:
            logger.error("Failed to log audit event", action=action.value, error=str(e))
            db.rollback()
            raise
    
    async def log_authentication(
        self,
        action: AuditAction,
        user_id: Optional[int],
        username: Optional[str],
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
        db: Session = None
    ):
        """
        Log authentication events.
        
        Args:
            action: Authentication action
            user_id: User ID (if known)
            username: Username attempted
            success: Whether authentication was successful
            ip_address: IP address
            user_agent: User agent string
            failure_reason: Reason for failure (if applicable)
            db: Database session
        """
        details = {
            'username': username,
            'success': success
        }
        
        if failure_reason:
            details['failure_reason'] = failure_reason
        
        severity = AuditSeverity.LOW if success else AuditSeverity.MEDIUM
        
        await self.log_event(
            action=action,
            user_id=user_id,
            resource_type='authentication',
            details=details,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            db=db
        )
    
    async def log_data_access(
        self,
        user_id: int,
        resource_type: str,
        resource_id: str,
        action: AuditAction,
        sensitivity_level: Optional[str] = None,
        pii_detected: bool = False,
        redaction_applied: bool = False,
        ip_address: Optional[str] = None,
        db: Session = None
    ):
        """
        Log data access events with sensitivity tracking.
        
        Args:
            user_id: User accessing data
            resource_type: Type of data resource
            resource_id: ID of data resource
            action: Action performed
            sensitivity_level: Data sensitivity level
            pii_detected: Whether PII was detected
            redaction_applied: Whether redaction was applied
            ip_address: IP address
            db: Database session
        """
        details = {}
        
        if sensitivity_level:
            details['sensitivity_level'] = sensitivity_level
        
        if pii_detected:
            details['pii_detected'] = True
            details['redaction_applied'] = redaction_applied
        
        # Higher severity for sensitive data access
        severity = AuditSeverity.LOW
        if sensitivity_level in ['confidential', 'restricted']:
            severity = AuditSeverity.MEDIUM
        if pii_detected and not redaction_applied:
            severity = AuditSeverity.HIGH
        
        await self.log_event(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            severity=severity,
            ip_address=ip_address,
            db=db
        )
    
    async def log_pii_redaction(
        self,
        user_id: Optional[int],
        resource_type: str,
        resource_id: str,
        pii_types: List[str],
        redaction_count: int,
        original_length: int,
        redacted_length: int,
        db: Session = None
    ):
        """
        Log PII redaction events for compliance tracking.
        
        Args:
            user_id: User who triggered redaction
            resource_type: Type of resource
            resource_id: ID of resource
            pii_types: Types of PII detected
            redaction_count: Number of redactions applied
            original_length: Original text length
            redacted_length: Redacted text length
            db: Database session
        """
        details = {
            'pii_types': pii_types,
            'redaction_count': redaction_count,
            'original_length': original_length,
            'redacted_length': redacted_length,
            'reduction_percentage': round((1 - redacted_length / original_length) * 100, 2)
        }
        
        await self.log_event(
            action=AuditAction.PII_REDACT,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            severity=AuditSeverity.MEDIUM,
            db=db
        )
    
    async def log_security_violation(
        self,
        user_id: Optional[int],
        violation_type: str,
        description: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        additional_details: Optional[Dict[str, Any]] = None,
        db: Session = None
    ):
        """
        Log security violations and suspicious activities.
        
        Args:
            user_id: User involved in violation
            violation_type: Type of security violation
            description: Description of the violation
            ip_address: IP address
            user_agent: User agent string
            additional_details: Additional context
            db: Database session
        """
        details = {
            'violation_type': violation_type,
            'description': description
        }
        
        if additional_details:
            details.update(additional_details)
        
        await self.log_event(
            action=AuditAction.SECURITY_VIOLATION,
            user_id=user_id,
            resource_type='security',
            details=details,
            severity=AuditSeverity.HIGH,
            ip_address=ip_address,
            user_agent=user_agent,
            db=db
        )
    
    def verify_audit_chain(self, db: Session, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify the integrity of the audit log chain.
        
        Args:
            db: Database session
            limit: Maximum number of entries to verify
            
        Returns:
            Dict[str, Any]: Verification results
        """
        try:
            query = db.query(AuditLog).order_by(AuditLog.created_at)
            
            if limit:
                query = query.limit(limit)
            
            entries = query.all()
            
            if not entries:
                return {
                    'valid': True,
                    'total_entries': 0,
                    'verified_entries': 0,
                    'errors': []
                }
            
            errors = []
            verified_count = 0
            
            for i, entry in enumerate(entries):
                # Reconstruct audit data for hash verification
                audit_data = {
                    'action': entry.action,
                    'user_id': entry.user_id,
                    'resource_type': entry.resource_type,
                    'resource_id': entry.resource_id,
                    'details': entry.details,
                    'severity': entry.severity,
                    'ip_address': entry.ip_address,
                    'user_agent': entry.user_agent,
                    'timestamp': entry.created_at.isoformat()
                }
                
                if entry.previous_hash:
                    audit_data['previous_hash'] = entry.previous_hash
                
                # Verify hash
                calculated_hash = self._calculate_hash(audit_data)
                
                if calculated_hash != entry.hash:
                    errors.append({
                        'entry_id': entry.id,
                        'error': 'Hash mismatch',
                        'expected': entry.hash,
                        'calculated': calculated_hash
                    })
                else:
                    verified_count += 1
                
                # Verify chain linkage (except for first entry)
                if i > 0:
                    previous_entry = entries[i - 1]
                    if entry.previous_hash != previous_entry.hash:
                        errors.append({
                            'entry_id': entry.id,
                            'error': 'Chain linkage broken',
                            'expected_previous': previous_entry.hash,
                            'actual_previous': entry.previous_hash
                        })
            
            return {
                'valid': len(errors) == 0,
                'total_entries': len(entries),
                'verified_entries': verified_count,
                'errors': errors
            }
            
        except Exception as e:
            logger.error("Error verifying audit chain", error=str(e))
            return {
                'valid': False,
                'total_entries': 0,
                'verified_entries': 0,
                'errors': [{'error': f'Verification failed: {str(e)}'}]
            }
    
    def search_audit_logs(
        self,
        db: Session,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        severity: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLog]:
        """
        Search audit logs with various filters.
        
        Args:
            db: Database session
            user_id: Filter by user ID
            action: Filter by action
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            severity: Filter by severity
            start_date: Filter by start date
            end_date: Filter by end date
            ip_address: Filter by IP address
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List[AuditLog]: Matching audit log entries
        """
        query = db.query(AuditLog)
        
        # Apply filters
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        
        if resource_id:
            query = query.filter(AuditLog.resource_id == resource_id)
        
        if severity:
            query = query.filter(AuditLog.severity == severity)
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        if ip_address:
            query = query.filter(AuditLog.ip_address == ip_address)
        
        # Order by most recent first
        query = query.order_by(desc(AuditLog.created_at))
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        return query.all()
    
    def get_audit_statistics(
        self,
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get audit log statistics for reporting.
        
        Args:
            db: Database session
            start_date: Start date for statistics
            end_date: End date for statistics
            
        Returns:
            Dict[str, Any]: Audit statistics
        """
        try:
            query = db.query(AuditLog)
            
            if start_date:
                query = query.filter(AuditLog.created_at >= start_date)
            
            if end_date:
                query = query.filter(AuditLog.created_at <= end_date)
            
            total_events = query.count()
            
            # Count by action
            action_counts = {}
            for action in AuditAction:
                count = query.filter(AuditLog.action == action.value).count()
                if count > 0:
                    action_counts[action.value] = count
            
            # Count by severity
            severity_counts = {}
            for severity in AuditSeverity:
                count = query.filter(AuditLog.severity == severity.value).count()
                if count > 0:
                    severity_counts[severity.value] = count
            
            # Count by user
            user_counts = {}
            user_results = query.filter(AuditLog.user_id.isnot(None)).all()
            for entry in user_results:
                user_id = entry.user_id
                if user_id not in user_counts:
                    user_counts[user_id] = 0
                user_counts[user_id] += 1
            
            # Top users by activity
            top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                'total_events': total_events,
                'action_counts': action_counts,
                'severity_counts': severity_counts,
                'top_users': top_users,
                'date_range': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                }
            }
            
        except Exception as e:
            logger.error("Error getting audit statistics", error=str(e))
            return {}


# Global audit service instance
audit_service = AuditService()

