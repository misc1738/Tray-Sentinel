"""
Database Verification & Repair Script
Checks for issues and provides fixes
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/sentinel.db")
LEDGER_PATH = Path("data/ledger.jsonl")

def check_database():
    """Run comprehensive database checks"""
    
    if not DB_PATH.exists():
        print("❌ Database not found. Run the app first to create it.")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("TRACEY'S SENTINEL - DATABASE VERIFICATION REPORT")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # 1. Integrity Check
    print("1️⃣  DATABASE INTEGRITY CHECK")
    print("-" * 60)
    cursor.execute("PRAGMA integrity_check;")
    integrity = cursor.fetchall()
    if integrity[0][0] == 'ok':
        print("✅ Database integrity: OK")
    else:
        print("❌ Database integrity: FAILED")
        for issue in integrity:
            print(f"   {issue}")
    
    # 2. Table Status
    print("\n2️⃣  TABLE STATUS")
    print("-" * 60)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]};")
        count = cursor.fetchone()[0]
        print(f"   ✓ {table[0]}: {count} records")
    
    # 3. Evidence Table Check
    print("\n3️⃣  EVIDENCE TABLE ANALYSIS")
    print("-" * 60)
    try:
        cursor.execute("SELECT COUNT(*) FROM evidence;")
        total = cursor.fetchone()[0]
        print(f"   Total evidence items: {total}")
        
        # Check for duplicates
        cursor.execute("""
            SELECT sha256, COUNT(*) as count 
            FROM evidence 
            GROUP BY sha256 
            HAVING count > 1;
        """)
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"   ⚠️  Found {len(duplicates)} duplicate SHA256 hashes:")
            for sha, count in duplicates:
                print(f"      - {sha}: {count} occurrences")
        else:
            print("   ✅ No duplicate SHA256 hashes")
        
        # Check for missing files
        cursor.execute("""
            SELECT COUNT(DISTINCT e.evidence_id) 
            FROM evidence e
            LEFT JOIN evidence_file ef ON e.evidence_id = ef.evidence_id
            WHERE ef.evidence_id IS NULL;
        """)
        missing = cursor.fetchone()[0]
        if missing > 0:
            print(f"   ⚠️  {missing} evidence items missing file mappings")
        else:
            print("   ✅ All evidence items have file mappings")
        
    except Exception as e:
        print(f"   ❌ Error checking evidence table: {e}")
    
    # 4. Evidence File Table Check
    print("\n4️⃣  EVIDENCE FILE TABLE ANALYSIS")
    print("-" * 60)
    try:
        cursor.execute("SELECT COUNT(*) FROM evidence_file;")
        total_files = cursor.fetchone()[0]
        print(f"   Total file mappings: {total_files}")
        
        # Check for orphaned entries
        cursor.execute("""
            SELECT COUNT(*) FROM evidence_file ef
            WHERE ef.evidence_id NOT IN (SELECT evidence_id FROM evidence);
        """)
        orphaned = cursor.fetchone()[0]
        if orphaned > 0:
            print(f"   ⚠️  {orphaned} orphaned file mapping(s) found")
        else:
            print("   ✅ No orphaned file mappings")
            
    except Exception as e:
        print(f"   ❌ Error checking evidence_file table: {e}")
    
    # 5. Storage Directory Check
    print("\n5️⃣  STORAGE DIRECTORY CHECK")
    print("-" * 60)
    store_dir = Path("evidence_store")
    if store_dir.exists():
        file_count = sum(1 for _ in store_dir.glob("*/*"))
        print(f"   ✓ evidence_store directory exists")
        print(f"   ✓ Total encrypted files: {file_count}")
        
        # Check for orphaned files
        cursor.execute("SELECT evidence_id FROM evidence;")
        db_ids = {row[0] for row in cursor.fetchall()}
        disk_ids = {d.name for d in store_dir.glob("*") if d.is_dir()}
        orphaned_files = disk_ids - db_ids
        if orphaned_files:
            print(f"   ⚠️  {len(orphaned_files)} orphaned directories on disk")
        else:
            print("   ✅ No orphaned file directories")
    else:
        print("   ❌ evidence_store directory not found")
    
    # 6. Ledger Check
    print("\n6️⃣  LEDGER INTEGRITY CHECK")
    print("-" * 60)
    if LEDGER_PATH.exists():
        try:
            with open(LEDGER_PATH) as f:
                lines = f.readlines()
            print(f"   ✓ Ledger file exists")
            print(f"   ✓ Total ledger entries: {len(lines)}")
            
            # Verify JSON validity
            valid_entries = 0
            for line in lines:
                try:
                    json.loads(line)
                    valid_entries += 1
                except:
                    pass
            
            if valid_entries == len(lines):
                print(f"   ✅ All ledger entries are valid JSON")
            else:
                print(f"   ⚠️  {len(lines) - valid_entries} corrupted ledger entries")
        except Exception as e:
            print(f"   ❌ Error reading ledger: {e}")
    else:
        print("   ℹ️  Ledger not created yet (expected on first run)")
    
    # 7. Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    cursor.execute("SELECT COUNT(*) FROM evidence;")
    evidence_count = cursor.fetchone()[0]
    
    if evidence_count == 0:
        print("ℹ️  Database is empty. Upload some evidence to get started!")
    else:
        print(f"✅ Database appears healthy with {evidence_count} evidence items")
        print("   To upload more evidence, use the Evidence Intake Scanner tab")
    
    print("\n" + "="*60 + "\n")
    
    conn.close()

def fix_database():
    """Attempt to fix common database issues"""
    
    if not DB_PATH.exists():
        print("❌ Database not found.")
        return
    
    print("\n" + "="*60)
    print("DATABASE REPAIR UTILITY")
    print("="*60 + "\n")
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Fix 1: Remove orphaned file mappings
    print("🔧 Removing orphaned file mappings...")
    try:
        cursor.execute("""
            DELETE FROM evidence_file 
            WHERE evidence_id NOT IN (SELECT evidence_id FROM evidence);
        """)
        deleted = cursor.rowcount
        if deleted > 0:
            print(f"   ✓ Removed {deleted} orphaned mappings")
        else:
            print("   ✓ No orphaned mappings found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Fix 2: Optimize database
    print("\n🧹 Optimizing database...")
    try:
        cursor.execute("VACUUM;")
        print("   ✓ Database optimized")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "fix":
        check_database()
        fix_database()
    else:
        check_database()
    
    print("💡 Tip: Run 'python db_verify.py fix' to attempt repairs")
