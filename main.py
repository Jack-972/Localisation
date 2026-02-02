from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import sqlite3
import uvicorn
import datetime
import base64

# --- CONFIGURATION ---
DB_FILE = "wifi_database1.db"
MAX_HISTORY = 100  # Nombre maximum de points a conserver pour le trace

app = FastAPI(title="Geo-Localisation LoRaWAN Dashboard")

# --- MEMOIRE (HISTORIQUE) ---
# On stocke une liste de points au lieu d'un etat unique
position_history = [] 

# --- MODELES ---
class UplinkMessage(BaseModel):
    decoded_payload: Optional[Dict[str, Any]] = None 
    frm_payload: Optional[str] = None

class TTNWebhookData(BaseModel):
    end_device_ids: Dict[str, Any]
    uplink_message: UplinkMessage

# --- FONCTIONS ---
def get_ap_coordinates(mac_address):
    if not mac_address: return None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        mac_clean = mac_address.strip().lower()
        cursor.execute("SELECT lat, lon FROM access_points WHERE mac = ?", (mac_clean,))
        result = cursor.fetchone()
        conn.close()
        if result: 
            return {"lat": result[0], "lon": result[1]}
        return None
    except Exception as e:
        print(f"Erreur SQL: {e}")
        return None

def estimate_position_weighted(aps_data):
    """Moyenne ponderee par le RSSI"""
    count = len(aps_data)
    if count == 0: return None

    sum_lat_weighted = 0
    sum_lon_weighted = 0
    total_weight = 0

    print(" Calcul de la position ponderee :")

    for ap in aps_data:
        rssi = ap.get('rssi', -100)
        # Bornage du RSSI pour eviter les valeurs aberrantes
        if rssi > -30: rssi = -30
        if rssi < -120: rssi = -120

        # Poids exponentiel
        weight = (rssi + 120) ** 2
        
        sum_lat_weighted += ap['lat'] * weight
        sum_lon_weighted += ap['lon'] * weight
        total_weight += weight
        
        print(f"   - MAC: {ap.get('mac')} | RSSI: {rssi} | Poids: {weight}")

    if total_weight == 0: return None

    return {
        "lat": sum_lat_weighted / total_weight, 
        "lon": sum_lon_weighted / total_weight
    }

def decode_raw_payload(b64_string):
    decoded_aps = []
    try:
        bytes_data = base64.b64decode(b64_string)
        for i in range(0, len(bytes_data), 7):
            if i + 6 < len(bytes_data):
                mac_bytes = bytes_data[i:i+6]
                mac_str = ":".join("{:02x}".format(b) for b in mac_bytes)
                rssi = bytes_data[i+6]
                if rssi > 127: rssi -= 256
                decoded_aps.append({"mac": mac_str, "rssi": rssi})
    except Exception as e:
        print(f"Erreur de décodage interne : {e}")
    return decoded_aps

# --- ROUTES ---

@app.get("/")
async def read_index():
    return FileResponse('index.html')

@app.get("/api/data")
async def get_data():
    # On renvoie la liste complete des points
    return {
        "history": position_history,
        "count": len(position_history)
    }

@app.post("/ttn-webhook")
async def receive_ttn_data(data: TTNWebhookData):
    global position_history
    try:
        device_id = data.end_device_ids.get("device_id", "unknown")
        uplink = data.uplink_message
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        print(f"\n[{timestamp}] RECEPTION UPLINK ({device_id})")

        inputs = []

        if uplink.decoded_payload:
            print(" Source : Decodeur TTN")
            payload = uplink.decoded_payload
            inputs = [
                {"mac": payload.get("mac_1"), "rssi": payload.get("rssi_1")},
                {"mac": payload.get("mac_2"), "rssi": payload.get("rssi_2")},
                {"mac": payload.get("mac_3"), "rssi": payload.get("rssi_3")}
            ]
            inputs = [i for i in inputs if i["mac"]]

        elif uplink.frm_payload:
            print(f" Source : Donnees brutes (Base64)")
            inputs = decode_raw_payload(uplink.frm_payload)

        else:
            return {"status": "no_data"}
        
        valid_aps_for_calc = []
        
        # Details pour le debug console uniquement
        print(f" Analyse de {len(inputs)} MACs...")

        for item in inputs:
            mac_recue = item["mac"]
            rssi = item.get("rssi", -100)
            coords = get_ap_coordinates(mac_recue)
            
            if coords:
                coords_with_rssi = {**coords, "rssi": rssi, "mac": mac_recue}
                valid_aps_for_calc.append(coords_with_rssi)

        # Calcul Position
        if valid_aps_for_calc:
            pos = estimate_position_weighted(valid_aps_for_calc)
            if pos:
                final_lat = pos['lat']
                final_lon = pos['lon']
                
                print(f" NOUVEAU POINT : {final_lat:.6f}, {final_lon:.6f}")

                # --- AJOUT A L'HISTORIQUE ---
                new_point = {
                    "lat": final_lat,
                    "lon": final_lon,
                    "timestamp": timestamp,
                    "aps_count": len(valid_aps_for_calc)
                }
                
                position_history.append(new_point)

                # Gestion de la taille de l'historique (FIFO)
                if len(position_history) > MAX_HISTORY:
                    position_history.pop(0) # On retire le plus ancien
                    
        else:
            print(" Position impossible (Pas assez de Wifi connus).")

        return {"status": "success", "history_size": len(position_history)}

    except Exception as e:
        print(f" ERREUR CRITIQUE: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)