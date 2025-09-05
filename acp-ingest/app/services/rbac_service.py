"""Role-Based Access Control (RBAC) service."""

from enum import Enum
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import User, Role, Permission, UserRole, RolePermission
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class SystemRole(Enum):
    """System-defined roles."""
    ADMIN = "admin"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class SystemPermission(Enum):
    """System-defined permissions."""
    # Ingest permissions
    INGEST_UPLOAD = "ingest:upload"
    INGEST_PASTE = "ingest:paste"
    INGEST_VIEW_OWN = "ingest:view_own"
    INGEST_VIEW_ALL = "ingest:view_all"
    INGEST_DELETE_OWN = "ingest:delete_own"
    INGEST_DELETE_ALL = "ingest:delete_all"
    INGEST_RETRY = "ingest:retry"
    
    # Search permissions
    SEARCH_QUERY = "search:query"
    SEARCH_EXPORT = "search:export"
    SEARCH_ADVANCED = "search:advanced"
    
    # Admin permissions
    ADMIN_USERS = "admin:users"
    ADMIN_ROLES = "admin:roles"
    ADMIN_SYSTEM = "admin:system"
    ADMIN_AUDIT = "admin:audit"
    ADMIN_METRICS = "admin:metrics"
    
    # Data permissions
    DATA_VIEW_SENSITIVE = "data:view_sensitive"
    DATA_VIEW_CONFIDENTIAL = "data:view_confidential"
    DATA_VIEW_RESTRICTED = "data:view_restricted"
    DATA_EXPORT = "data:export"
    
    # Review permissions
    REVIEW_APPROVE = "review:approve"
    REVIEW_REJECT = "review:reject"
    REVIEW_ASSIGN = "review:assign"


class SensitivityLevel(Enum):
    """Data sensitivity levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class RBACService:
    """Service for managing role-based access control."""
    
    def __init__(self):
        self.role_permissions = self._initialize_role_permissions()
    
    def _initialize_role_permissions(self) -> Dict[SystemRole, Set[SystemPermission]]:
        """Initialize default role-permission mappings."""
        return {
            SystemRole.ADMIN: {
                # All permissions
                SystemPermission.INGEST_UPLOAD,
                SystemPermission.INGEST_PASTE,
                SystemPermission.INGEST_VIEW_ALL,
                SystemPermission.INGEST_DELETE_ALL,
                SystemPermission.INGEST_RETRY,
                SystemPermission.SEARCH_QUERY,
                SystemPermission.SEARCH_EXPORT,
                SystemPermission.SEARCH_ADVANCED,
                SystemPermission.ADMIN_USERS,
                SystemPermission.ADMIN_ROLES,
                SystemPermission.ADMIN_SYSTEM,
                SystemPermission.ADMIN_AUDIT,
                SystemPermission.ADMIN_METRICS,
                SystemPermission.DATA_VIEW_SENSITIVE,
                SystemPermission.DATA_VIEW_CONFIDENTIAL,
                SystemPermission.DATA_VIEW_RESTRICTED,
                SystemPermission.DATA_EXPORT,
                SystemPermission.REVIEW_APPROVE,
                SystemPermission.REVIEW_REJECT,
                SystemPermission.REVIEW_ASSIGN,
            },
            SystemRole.ANALYST: {
                # Core analyst permissions
                SystemPermission.INGEST_UPLOAD,
                SystemPermission.INGEST_PASTE,
                SystemPermission.INGEST_VIEW_OWN,
                SystemPermission.INGEST_DELETE_OWN,
                SystemPermission.INGEST_RETRY,
                SystemPermission.SEARCH_QUERY,
                SystemPermission.SEARCH_EXPORT,
                SystemPermission.SEARCH_ADVANCED,
                SystemPermission.DATA_VIEW_SENSITIVE,
                SystemPermission.DATA_VIEW_CONFIDENTIAL,
                SystemPermission.DATA_EXPORT,
            },
            SystemRole.REVIEWER: {
                # Review and oversight permissions
                SystemPermission.INGEST_VIEW_ALL,
                SystemPermission.SEARCH_QUERY,
                SystemPermission.SEARCH_ADVANCED,
                SystemPermission.DATA_VIEW_SENSITIVE,
                SystemPermission.DATA_VIEW_CONFIDENTIAL,
                SystemPermission.DATA_VIEW_RESTRICTED,
                SystemPermission.REVIEW_APPROVE,
                SystemPermission.REVIEW_REJECT,
                SystemPermission.REVIEW_ASSIGN,
                SystemPermission.ADMIN_AUDIT,
            },
            SystemRole.VIEWER: {
                # Read-only permissions
                SystemPermission.INGEST_VIEW_OWN,
                SystemPermission.SEARCH_QUERY,
                SystemPermission.DATA_VIEW_SENSITIVE,
            },
        }
    
    async def initialize_system_roles(self, db: Session):
        """Initialize system roles and permissions in the database."""
        logger.info("Initializing system roles and permissions")
        
        try:
            # Create permissions
            for permission in SystemPermission:
                existing = db.query(Permission).filter(
                    Permission.name == permission.value
                ).first()
                
                if not existing:
                    perm = Permission(
                        name=permission.value,
                        description=self._get_permission_description(permission),
                        created_at=datetime.utcnow()
                    )
                    db.add(perm)
            
            # Create roles
            for role in SystemRole:
                existing = db.query(Role).filter(Role.name == role.value).first()
                
                if not existing:
                    role_obj = Role(
                        name=role.value,
                        description=self._get_role_description(role),
                        is_system_role=True,
                        created_at=datetime.utcnow()
                    )
                    db.add(role_obj)
            
            db.commit()
            
            # Assign permissions to roles
            for role, permissions in self.role_permissions.items():
                role_obj = db.query(Role).filter(Role.name == role.value).first()
                
                for permission in permissions:
                    perm_obj = db.query(Permission).filter(
                        Permission.name == permission.value
                    ).first()
                    
                    # Check if assignment already exists
                    existing = db.query(RolePermission).filter(
                        RolePermission.role_id == role_obj.id,
                        RolePermission.permission_id == perm_obj.id
                    ).first()
                    
                    if not existing:
                        role_perm = RolePermission(
                            role_id=role_obj.id,
                            permission_id=perm_obj.id,
                            created_at=datetime.utcnow()
                        )
                        db.add(role_perm)
            
            db.commit()
            logger.info("System roles and permissions initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize system roles", error=str(e))
            db.rollback()
            raise
    
    def _get_role_description(self, role: SystemRole) -> str:
        """Get description for a system role."""
        descriptions = {
            SystemRole.ADMIN: "System administrator with full access to all features and data",
            SystemRole.ANALYST: "Data analyst with access to ingestion, search, and analysis features",
            SystemRole.REVIEWER: "Reviewer with oversight capabilities and access to sensitive data",
            SystemRole.VIEWER: "Read-only access to basic features and own data"
        }
        return descriptions.get(role, "System role")
    
    def _get_permission_description(self, permission: SystemPermission) -> str:
        """Get description for a system permission."""
        descriptions = {
            SystemPermission.INGEST_UPLOAD: "Upload files for ingestion",
            SystemPermission.INGEST_PASTE: "Paste text content for ingestion",
            SystemPermission.INGEST_VIEW_OWN: "View own ingestion jobs",
            SystemPermission.INGEST_VIEW_ALL: "View all ingestion jobs",
            SystemPermission.INGEST_DELETE_OWN: "Delete own ingestion jobs",
            SystemPermission.INGEST_DELETE_ALL: "Delete any ingestion jobs",
            SystemPermission.INGEST_RETRY: "Retry failed ingestion jobs",
            SystemPermission.SEARCH_QUERY: "Perform basic search queries",
            SystemPermission.SEARCH_EXPORT: "Export search results",
            SystemPermission.SEARCH_ADVANCED: "Use advanced search features",
            SystemPermission.ADMIN_USERS: "Manage user accounts",
            SystemPermission.ADMIN_ROLES: "Manage roles and permissions",
            SystemPermission.ADMIN_SYSTEM: "Manage system configuration",
            SystemPermission.ADMIN_AUDIT: "Access audit logs and reports",
            SystemPermission.ADMIN_METRICS: "Access system metrics and monitoring",
            SystemPermission.DATA_VIEW_SENSITIVE: "View sensitive data",
            SystemPermission.DATA_VIEW_CONFIDENTIAL: "View confidential data",
            SystemPermission.DATA_VIEW_RESTRICTED: "View restricted data",
            SystemPermission.DATA_EXPORT: "Export data and analysis results",
            SystemPermission.REVIEW_APPROVE: "Approve analysis results",
            SystemPermission.REVIEW_REJECT: "Reject analysis results",
            SystemPermission.REVIEW_ASSIGN: "Assign review tasks",
        }
        return descriptions.get(permission, "System permission")
    
    def check_permission(
        self,
        user: User,
        permission: SystemPermission,
        db: Session
    ) -> bool:
        """
        Check if a user has a specific permission.
        
        Args:
            user: User to check
            permission: Permission to check
            db: Database session
            
        Returns:
            bool: True if user has permission
        """
        try:
            # Get user roles
            user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
            
            for user_role in user_roles:
                # Check if role has the permission
                role_permission = db.query(RolePermission).join(Permission).filter(
                    RolePermission.role_id == user_role.role_id,
                    Permission.name == permission.value
                ).first()
                
                if role_permission:
                    return True
            
            return False
            
        except Exception as e:
            logger.error("Error checking permission", user_id=user.id, permission=permission.value, error=str(e))
            return False
    
    def check_data_access(
        self,
        user: User,
        sensitivity_level: SensitivityLevel,
        db: Session
    ) -> bool:
        """
        Check if a user can access data of a specific sensitivity level.
        
        Args:
            user: User to check
            sensitivity_level: Data sensitivity level
            db: Database session
            
        Returns:
            bool: True if user can access data
        """
        permission_map = {
            SensitivityLevel.PUBLIC: None,  # No special permission needed
            SensitivityLevel.INTERNAL: SystemPermission.DATA_VIEW_SENSITIVE,
            SensitivityLevel.CONFIDENTIAL: SystemPermission.DATA_VIEW_CONFIDENTIAL,
            SensitivityLevel.RESTRICTED: SystemPermission.DATA_VIEW_RESTRICTED,
        }
        
        required_permission = permission_map.get(sensitivity_level)
        
        if not required_permission:
            return True  # Public data
        
        return self.check_permission(user, required_permission, db)
    
    def get_user_permissions(self, user: User, db: Session) -> Set[str]:
        """
        Get all permissions for a user.
        
        Args:
            user: User to get permissions for
            db: Database session
            
        Returns:
            Set[str]: Set of permission names
        """
        try:
            permissions = set()
            
            # Get user roles
            user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
            
            for user_role in user_roles:
                # Get role permissions
                role_permissions = db.query(RolePermission).join(Permission).filter(
                    RolePermission.role_id == user_role.role_id
                ).all()
                
                for role_permission in role_permissions:
                    permission = db.query(Permission).filter(
                        Permission.id == role_permission.permission_id
                    ).first()
                    if permission:
                        permissions.add(permission.name)
            
            return permissions
            
        except Exception as e:
            logger.error("Error getting user permissions", user_id=user.id, error=str(e))
            return set()
    
    def assign_role_to_user(
        self,
        user_id: int,
        role_name: str,
        assigned_by: int,
        db: Session
    ) -> bool:
        """
        Assign a role to a user.
        
        Args:
            user_id: User ID
            role_name: Role name to assign
            assigned_by: ID of user making the assignment
            db: Database session
            
        Returns:
            bool: True if successful
        """
        try:
            # Get role
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                logger.error("Role not found", role_name=role_name)
                return False
            
            # Check if assignment already exists
            existing = db.query(UserRole).filter(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id
            ).first()
            
            if existing:
                logger.warning("User already has role", user_id=user_id, role_name=role_name)
                return True
            
            # Create assignment
            user_role = UserRole(
                user_id=user_id,
                role_id=role.id,
                assigned_by=assigned_by,
                assigned_at=datetime.utcnow()
            )
            
            db.add(user_role)
            db.commit()
            
            logger.info("Role assigned to user", user_id=user_id, role_name=role_name)
            return True
            
        except Exception as e:
            logger.error("Error assigning role", user_id=user_id, role_name=role_name, error=str(e))
            db.rollback()
            return False
    
    def remove_role_from_user(
        self,
        user_id: int,
        role_name: str,
        removed_by: int,
        db: Session
    ) -> bool:
        """
        Remove a role from a user.
        
        Args:
            user_id: User ID
            role_name: Role name to remove
            removed_by: ID of user making the removal
            db: Database session
            
        Returns:
            bool: True if successful
        """
        try:
            # Get role
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                logger.error("Role not found", role_name=role_name)
                return False
            
            # Find assignment
            user_role = db.query(UserRole).filter(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id
            ).first()
            
            if not user_role:
                logger.warning("User does not have role", user_id=user_id, role_name=role_name)
                return True
            
            # Remove assignment
            db.delete(user_role)
            db.commit()
            
            logger.info("Role removed from user", user_id=user_id, role_name=role_name)
            return True
            
        except Exception as e:
            logger.error("Error removing role", user_id=user_id, role_name=role_name, error=str(e))
            db.rollback()
            return False
    
    def create_custom_role(
        self,
        name: str,
        description: str,
        permissions: List[str],
        created_by: int,
        db: Session
    ) -> Optional[Role]:
        """
        Create a custom role with specified permissions.
        
        Args:
            name: Role name
            description: Role description
            permissions: List of permission names
            created_by: ID of user creating the role
            db: Database session
            
        Returns:
            Optional[Role]: Created role or None if failed
        """
        try:
            # Check if role already exists
            existing = db.query(Role).filter(Role.name == name).first()
            if existing:
                logger.error("Role already exists", role_name=name)
                return None
            
            # Create role
            role = Role(
                name=name,
                description=description,
                is_system_role=False,
                created_by=created_by,
                created_at=datetime.utcnow()
            )
            
            db.add(role)
            db.flush()  # Get the role ID
            
            # Assign permissions
            for permission_name in permissions:
                permission = db.query(Permission).filter(
                    Permission.name == permission_name
                ).first()
                
                if permission:
                    role_permission = RolePermission(
                        role_id=role.id,
                        permission_id=permission.id,
                        created_at=datetime.utcnow()
                    )
                    db.add(role_permission)
                else:
                    logger.warning("Permission not found", permission_name=permission_name)
            
            db.commit()
            
            logger.info("Custom role created", role_name=name, permissions_count=len(permissions))
            return role
            
        except Exception as e:
            logger.error("Error creating custom role", role_name=name, error=str(e))
            db.rollback()
            return None
    
    def get_role_hierarchy(self) -> Dict[SystemRole, int]:
        """
        Get role hierarchy levels for authorization checks.
        
        Returns:
            Dict[SystemRole, int]: Role hierarchy levels (higher number = more privileges)
        """
        return {
            SystemRole.VIEWER: 1,
            SystemRole.ANALYST: 2,
            SystemRole.REVIEWER: 3,
            SystemRole.ADMIN: 4,
        }
    
    def can_manage_user(
        self,
        manager: User,
        target_user: User,
        db: Session
    ) -> bool:
        """
        Check if a user can manage another user.
        
        Args:
            manager: User attempting to manage
            target_user: User being managed
            db: Database session
            
        Returns:
            bool: True if manager can manage target user
        """
        # Admins can manage anyone
        if self.check_permission(manager, SystemPermission.ADMIN_USERS, db):
            return True
        
        # Users cannot manage themselves for role changes
        if manager.id == target_user.id:
            return False
        
        # Get role hierarchy levels
        hierarchy = self.get_role_hierarchy()
        
        manager_level = 0
        target_level = 0
        
        # Get manager's highest role level
        manager_roles = db.query(UserRole).join(Role).filter(
            UserRole.user_id == manager.id
        ).all()
        
        for user_role in manager_roles:
            role = db.query(Role).filter(Role.id == user_role.role_id).first()
            if role and role.name in [r.value for r in SystemRole]:
                role_enum = SystemRole(role.name)
                manager_level = max(manager_level, hierarchy.get(role_enum, 0))
        
        # Get target user's highest role level
        target_roles = db.query(UserRole).join(Role).filter(
            UserRole.user_id == target_user.id
        ).all()
        
        for user_role in target_roles:
            role = db.query(Role).filter(Role.id == user_role.role_id).first()
            if role and role.name in [r.value for r in SystemRole]:
                role_enum = SystemRole(role.name)
                target_level = max(target_level, hierarchy.get(role_enum, 0))
        
        # Manager must have higher level than target
        return manager_level > target_level


# Global RBAC service instance
rbac_service = RBACService()

