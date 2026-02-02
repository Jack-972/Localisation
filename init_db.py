import sqlite3
import csv
import os

# CONFIGURATION
CSV_FILE = "data_5e_arr1.csv"
DB_FILE = "wifi_database1.db"

def create_database():
    # Suppression de l'ancienne base pour repartir à zéro si besoin
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        
    print("--- Création de la base de données SQLite ---")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Création de la table (indexée sur la mac pour la rapidité)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_points (
            mac TEXT PRIMARY KEY,
            lat REAL,
            lon REAL
        )
    ''')
    
    print(f"Lecture de {CSV_FILE}...")
    
    count = 0
    batch = []
    
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            # Adaptation à votre format
            reader = csv.DictReader(f, delimiter=',') 
            
            for row in reader:
                try:
                    # 1. Nettoyage de la MAC (minuscule) : "DE:34:..." -> "de:34:..."
                    mac = row['netid'].strip().lower()
                    
                    # 2. Récupération des coordonnées
                    lat = float(row['trilat'])
                    lon = float(row['trilong'])
                    
                    batch.append((mac, lat, lon))
                    count += 1
                except (ValueError, KeyError) as e:
                    # Ignore les lignes mal formées
                    continue

                # Insertion par paquet de 5000 pour aller très vite
                if len(batch) >= 5000:
                    cursor.executemany('INSERT OR IGNORE INTO access_points VALUES (?,?,?)', batch)
                    conn.commit()
                    batch = []
                    print(f"{count} APs traités...", end='\r')
            
            # Insérer ce qui reste à la fin
            if batch:
                cursor.executemany('INSERT OR IGNORE INTO access_points VALUES (?,?,?)', batch)
                conn.commit()

        print(f"\nSUCCÈS ! {count} points d'accès importés dans {DB_FILE}.")
        
    except FileNotFoundError:
        print(f"ERREUR : Le fichier {CSV_FILE} est introuvable.")
    finally:
        conn.close()

if __name__ == "__main__":
    create_database()