import sqlite3
import csv
import os

# --- CONFIGURATION ---
INPUT_FILE = "wigle_data.txt"
DB_FILE = "wifi_database1.db"

def clean_and_read_file(filename):
    """Lit le fichier en nettoyant les caractères NUL et les erreurs d'encodage"""
    with open(filename, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
        # On supprime les octets nuls qui font planter le CSV
        return content.replace('\0', '').splitlines()

def import_wigle_data():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Erreur : Le fichier '{INPUT_FILE}' est introuvable.")
        return

    print(f"🗑️  Suppression de l'ancienne BDD (si elle existe) pour éviter les conflits...")
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    print(f"🔄 Traitement de {INPUT_FILE}...")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Création de la table avec TOUTES les colonnes nécessaires
    cursor.execute("""
        CREATE TABLE access_points (
            netid TEXT,
            ssid TEXT,
            lat REAL,
            lon REAL,
            lasttime TEXT,
            mac TEXT PRIMARY KEY
        )
    """)

    lines = clean_and_read_file(INPUT_FILE)
    
    # On cherche où commencent les données
    start_index = 0
    for i, line in enumerate(lines):
        if line.startswith("MAC,SSID"):
            start_index = i
            break
            
    csv_data = lines[start_index:]
    reader = csv.DictReader(csv_data)
    
    count = 0
    
    for row in reader:
        # Wigle met parfois "CurrentLatitude" ou "CurrrentLatitude" (typo)
        lat = row.get('CurrentLatitude') or row.get('CurrrentLatitude')
        lon = row.get('CurrentLongitude') or row.get('CurrrentLongitude')
        raw_mac = row.get('MAC')
        ssid = row.get('SSID', 'Unknown')
        time = row.get('FirstSeen', '')

        if raw_mac and lat and lon:
            try:
                mac_clean = raw_mac.strip().lower()
                
                # On insère. netid = mac_clean pour simplifier
                cursor.execute("""
                    INSERT OR REPLACE INTO access_points (netid, ssid, lat, lon, lasttime, mac)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (mac_clean, ssid, lat, lon, time, mac_clean))
                
                count += 1
            except Exception as e:
                pass # On ignore les lignes corrompues silencieusement

    conn.commit()
    conn.close()
    
    print("\n" + "="*40)
    print(f"✅ SUCCÈS : {count} points WiFi importés dans {DB_FILE} !")
    print("="*40)

if __name__ == "__main__":
    import_wigle_data()