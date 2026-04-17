"""
Database Seeder - Populate Tracey's Sentinel with Realistic Sample Data
Generates:
  - Evidence items with realistic data
  - File mappings
"""

import sqlite3
import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import random

DB_PATH = Path("data/sentinel.db")

# Sample evidence types and descriptions
ACQUISITION_METHODS = [
    "MOBILE_DEVICE",
    "COMPUTER_FORENSICS",
    "VIDEO_CAPTURE",
    "DIGITAL_EXTRACTION",
    "PHYSICAL_SEIZURE",
    "INTERVIEW_RECORDING",
    "LAB_ANALYSIS",
    "SURVEILLANCE_SYSTEM",
]

SOURCE_DEVICES = [
    "iPhone 15 Pro",
    "Samsung Galaxy S24",
    "Dell Latitude 5540",
    "MacBook Pro",
    "CCTV System DVR-2048",
    "Audio Recorder Sony PCM-D100",
    "Canon EOS R6",
    "GoPro Hero 12",
    None,  # For evidence without specific source device
]

FILE_NAMES = [
    "surveillance_footage_2026-04-10.mp4",
    "witness_statement.pdf",
    "police_report.docx",
    "cctv_entrance_main.mp4",
    "forensic_report_analysis.pdf",
    "fingerprint_comparison.jpg",
    "dna_results.pdf",
    "audio_interview_suspect.wav",
    "crime_scene_photo_1.jpg",
    "crime_scene_photo_2.jpg",
    "chain_of_custody.pdf",
    "lab_test_results.xlsx",
    "device_extraction.bin",
    "memory_dump.img",
]

DESCRIPTIONS = [
    "Surveillance camera footage from incident location",
    "Written statement from eyewitness to incident",
    "Initial police report and incident summary",
    "CCTV footage from building main entrance",
    "Forensic analysis of physical evidence collected",
    "Digital fingerprint comparison analysis results",
    "DNA sample analysis results from crime scene",
    "Audio recording of suspect interrogation",
    "Close-up photograph of evidence item",
    "Wide angle crime scene photograph",
    "Complete chain of custody documentation",
    "Laboratory chemical analysis results",
    "Complete device memory forensic extraction",
    "System RAM capture from suspect computer",
    "Security camera recording from incident day",
    "Mobile device forensic data extraction",
    "Call logs and message history backup",
    "Bank transaction records in PDF format",
]

CASE_IDS = [
    "KPS-2026-001",  # Traffic Incident
    "KPS-2026-002",  # Property Theft
    "KPS-2026-003",  # Fraud Investigation
    "FBI-2026-001",  # Money Laundering
    "ICE-2026-001",  # Immigration Violation
]


def seed_evidence(conn):
    """Insert realistic evidence items"""
    print("\n[*] Seeding Evidence Items...")
    cursor = conn.cursor()
    
    evidence_added = 0
    
    for case_id in CASE_IDS:
        # Add 5-8 evidence items per case
        num_evidence = random.randint(5, 8)
        for i in range(num_evidence):
            evidence_id = str(uuid.uuid4())
            file_name = random.choice(FILE_NAMES)
            description = random.choice(DESCRIPTIONS)
            acquisition_method = random.choice(ACQUISITION_METHODS)
            source_device = random.choice(SOURCE_DEVICES)
            
            # Generate realistic SHA256 hash
            sha256 = hashlib.sha256(f"{evidence_id}{i}{random.random()}".encode()).hexdigest()
            
            # Vary creation times across past 90 days
            created_at = (datetime.utcnow() - timedelta(days=random.randint(1, 90))).isoformat()
            
            try:
                cursor.execute("""
                    INSERT INTO evidence (evidence_id, case_id, description, source_device, acquisition_method, file_name, sha256, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    evidence_id,
                    case_id,
                    description,
                    source_device,
                    acquisition_method,
                    f"{file_name}_{case_id}_{i+1}",
                    sha256,
                    created_at
                ))
                
                # Also add to evidence_file mapping
                cursor.execute("""
                    INSERT INTO evidence_file (evidence_id, file_path)
                    VALUES (?, ?)
                """, (evidence_id, f"evidence_store/{evidence_id}/{file_name}"))
                
                evidence_added += 1
            except Exception as e:
                print(f"   [ERROR] Failed to insert evidence: {e}")
                continue
    
    conn.commit()
    print(f"   [OK] Added {evidence_added} evidence items across {len(CASE_IDS)} cases")


def clear_existing_data(conn):
    """Clear existing data"""
    print("\n[*] Clearing existing records...")
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM evidence_file;")
        cursor.execute("DELETE FROM evidence;")
        conn.commit()
        print("   [OK] Old records cleared")
    except Exception as e:
        print(f"   [WARNING] Could not clear records: {e}")


def main():
    print("\n" + "="*60)
    print("TRACEY'S SENTINEL - DATABASE SEEDER")
    print("="*60)
    
    if not DB_PATH.exists():
        print("\n[ERROR] Database not found at", DB_PATH)
        print("[INFO] Run the application first to initialize the database")
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    
    try:
        print("\n[*] Clearing existing sample data...")
        clear_existing_data(conn)
        
        print("\n[*] Populating database with realistic sample data...")
        seed_evidence(conn)
        
        print("\n" + "="*60)
        print("[OK] DATABASE SEEDING COMPLETE")
        print("="*60)
        
        print("\n[*] SAMPLE DATA SUMMARY:")
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM evidence;")
        total_evidence = cursor.fetchone()[0]
        print(f"   Total Evidence Items: {total_evidence}")
        
        print("\n[*] EVIDENCE BY CASE:")
        cursor.execute("""
            SELECT case_id, COUNT(*) as count 
            FROM evidence 
            GROUP BY case_id 
            ORDER BY count DESC;
        """)
        for case_id, count in cursor.fetchall():
            print(f"   • {case_id}: {count} evidence items")
        
        print("\n[*] EVIDENCE BREAKDOWN BY TYPE:")
        cursor.execute("""
            SELECT acquisition_method, COUNT(*) as count 
            FROM evidence 
            GROUP BY acquisition_method 
            ORDER BY count DESC;
        """)
        for method, count in cursor.fetchall():
            print(f"   • {method}: {count} items")
        
        print("\n" + "="*60 + "\n")
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
