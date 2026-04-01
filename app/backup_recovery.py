"""Database backup and recovery system with point-in-time restore."""
import sqlite3
import shutil
import gzip
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timezone, timedelta


class BackupType(str, Enum):
    """Types of database backups."""
    FULL = "full"          # Full database snapshot
    INCREMENTAL = "incremental"  # Changes since last full backup
    COMPRESSED = "compressed"    # Compressed full backup


class BackupRecoveryManager:
    """Manage database backups and point-in-time recovery."""
    
    BACKUP_RETENTION_DAYS = 30
    
    def __init__(self, db_path: Path, backup_dir: Optional[Path] = None):
        self.db_path = Path(db_path)
        self.backup_dir = backup_dir or self.db_path.parent / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.backup_dir / 'backup_manifest.json'
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Load backup metadata."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {'backups': []}

    def _save_manifest(self) -> None:
        """Save backup metadata."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.manifest, f, indent=2)

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def create_full_backup(self, description: str = "") -> Dict[str, Any]:
        """Create full database backup."""
        timestamp = datetime.now(timezone.utc).isoformat()
        backup_name = f"backup_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = self.backup_dir / backup_name
        
        try:
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            # Calculate checksum
            checksum = self._calculate_checksum(backup_path)
            
            # Verify database integrity
            self._verify_backup(backup_path)
            
            # Record metadata
            backup_info = {
                'type': BackupType.FULL,
                'filename': backup_name,
                'path': str(backup_path),
                'timestamp': timestamp,
                'checksum': checksum,
                'size_bytes': backup_path.stat().st_size,
                'description': description,
                'verified': True
            }
            
            self.manifest['backups'].append(backup_info)
            self._save_manifest()
            
            return {
                'success': True,
                'backup': backup_info,
                'message': f"Full backup created: {backup_name}"
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"Failed to create backup: {e}"
            }

    def create_compressed_backup(self, description: str = "") -> Dict[str, Any]:
        """Create compressed backup for archival."""
        timestamp = datetime.now(timezone.utc).isoformat()
        backup_name = f"backup_compressed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db.gz"
        backup_path = self.backup_dir / backup_name
        
        try:
            # Create compressed backup
            with open(self.db_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Calculate checksum
            checksum = self._calculate_checksum(backup_path)
            
            original_size = self.db_path.stat().st_size
            compressed_size = backup_path.stat().st_size
            compression_ratio = round((1 - compressed_size / original_size) * 100, 2)
            
            backup_info = {
                'type': BackupType.COMPRESSED,
                'filename': backup_name,
                'path': str(backup_path),
                'timestamp': timestamp,
                'checksum': checksum,
                'original_size_bytes': original_size,
                'compressed_size_bytes': compressed_size,
                'compression_ratio_percent': compression_ratio,
                'description': description
            }
            
            self.manifest['backups'].append(backup_info)
            self._save_manifest()
            
            return {
                'success': True,
                'backup': backup_info,
                'message': f"Compressed backup created: {backup_name} ({compression_ratio}% reduction)"
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"Failed to create compressed backup: {e}"
            }

    def restore_backup(self, backup_name: str, restore_path: Optional[Path] = None) -> Dict[str, Any]:
        """Restore database from backup."""
        backup_info = None
        for backup in self.manifest['backups']:
            if backup['filename'] == backup_name:
                backup_info = backup
                break
        
        if not backup_info:
            return {
                'success': False,
                'error': 'Backup not found',
                'message': f"Backup '{backup_name}' not found in manifest"
            }
        
        backup_path = Path(backup_info['path'])
        if not backup_path.exists():
            return {
                'success': False,
                'error': 'Backup file missing',
                'message': f"Backup file not found at {backup_path}"
            }
        
        restore_target = restore_path or self.db_path
        
        try:
            # Create safety backup of current database
            if restore_target.exists():
                safety_backup = self.backup_dir / f"safety_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(restore_target, safety_backup)
            
            # Restore backup
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(restore_target, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(backup_path, restore_target)
            
            # Verify restored database
            self._verify_backup(restore_target)
            
            return {
                'success': True,
                'restored_path': str(restore_target),
                'backup_name': backup_name,
                'timestamp': backup_info['timestamp'],
                'message': f"Successfully restored from {backup_name}"
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"Failed to restore backup: {e}"
            }

    def _verify_backup(self, db_path: Path) -> bool:
        """Verify database integrity."""
        try:
            with sqlite3.connect(db_path) as conn:
                # Run integrity check
                cursor = conn.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                
                if result[0] != 'ok':
                    raise ValueError(f"Integrity check failed: {result[0]}")
            
            return True
        except Exception as e:
            raise ValueError(f"Backup verification failed: {e}")

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = sorted(
            self.manifest['backups'],
            key=lambda x: x['timestamp'],
            reverse=True
        )
        
        for backup in backups:
            path = Path(backup['path'])
            backup['exists'] = path.exists()
            backup['age_days'] = (
                datetime.fromisoformat(backup['timestamp'].replace('Z', '+00:00'))
                if backup['timestamp'].endswith('Z') or '+' in backup['timestamp']
                else datetime.fromisoformat(backup['timestamp'])
            )
            backup['age_days'] = round(
                (datetime.now(timezone.utc) - (
                    datetime.fromisoformat(backup['timestamp'].replace('Z', '+00:00'))
                    if backup['timestamp'].endswith('Z') or '+' in backup['timestamp']
                    else datetime.fromisoformat(backup['timestamp'])
                )).total_seconds() / 86400, 1
            )
        
        return backups

    def cleanup_old_backups(self, retention_days: int = BACKUP_RETENTION_DAYS) -> Dict[str, Any]:
        """Remove backups older than retention period."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted_count = 0
        freed_space_bytes = 0
        
        remaining_backups = []
        
        for backup in self.manifest['backups']:
            backup_date = datetime.fromisoformat(
                backup['timestamp'].replace('Z', '+00:00')
                if backup['timestamp'].endswith('Z') or '+' in backup['timestamp']
                else backup['timestamp']
            )
            
            if backup_date < cutoff_date:
                path = Path(backup['path'])
                try:
                    if path.exists():
                        freed_space_bytes += path.stat().st_size
                        path.unlink()
                    deleted_count += 1
                except Exception as e:
                    # Log but continue
                    pass
            else:
                remaining_backups.append(backup)
        
        self.manifest['backups'] = remaining_backups
        self._save_manifest()
        
        return {
            'deleted_count': deleted_count,
            'freed_space_bytes': freed_space_bytes,
            'freed_space_mb': round(freed_space_bytes / (1024 * 1024), 2),
            'retention_days': retention_days,
            'message': f"Deleted {deleted_count} old backups, freed {freed_space_bytes} bytes"
        }

    def get_backup_stats(self) -> Dict[str, Any]:
        """Get comprehensive backup statistics."""
        backups = self.list_backups()
        
        total_backup_space = sum(
            b.get('size_bytes', b.get('compressed_size_bytes', 0))
            for b in backups
        )
        
        by_type = {}
        for backup in backups:
            btype = backup['type']
            if btype not in by_type:
                by_type[btype] = 0
            by_type[btype] += 1
        
        return {
            'total_backups': len(backups),
            'by_type': by_type,
            'total_backup_space_bytes': total_backup_space,
            'total_backup_space_mb': round(total_backup_space / (1024 * 1024), 2),
            'newest_backup': backups[0]['timestamp'] if backups else None,
            'oldest_backup': backups[-1]['timestamp'] if backups else None
        }
