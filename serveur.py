from fastapi import FastAPI, Request, HTTPException
import uvicorn
import datetime

# --- Importez Pydantic pour valider les données entrantes ---
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI(
    title="Projet Géolocalisation WiFi-LoRaWAN",
    description="Serveur FastAPI pour recevoir les données de TTN."
)

# --- 1. Définir la structure des données (Modèles Pydantic) ---
# Modèle pour ce que VOTRE décodeur TTN envoie (les données utiles)
class DecodedPayload(BaseModel):
    AP1_MAC: Optional[str] = None
    AP1_RSSI: Optional[int] = None
    AP2_MAC: Optional[str] = None
    AP2_RSSI: Optional[int] = None
    # Ajoutez d'autres champs si votre décodeur en envoie plus

# Modèle pour le message de TTN (on ne prend que ce qui nous intéresse)
class UplinkMessage(BaseModel):
    decoded_payload: DecodedPayload
    # Vous pouvez ajouter d'autres champs de TTN si besoin
    # ex: rx_metadata, settings, etc.

# Modèle pour le corps complet du Webhook TTN
class TTNWebhookData(BaseModel):
    end_device_ids: Dict[str, Any]
    uplink_message: UplinkMessage

# --- 2. L'Endpoint (la route) qui reçoit les données ---

@app.post("/ttn-webhook")
async def receive_ttn_data(data: TTNWebhookData):
    """
    Ce endpoint reçoit les données envoyées par le Webhook TTN.
    """
    try:
        device_id = data.end_device_ids.get("device_id", "unknown_device")
        payload = data.uplink_message.decoded_payload
        
        timestamp = datetime.datetime.now().isoformat()
        
        # Affiche les données reçues dans la console du serveur
        print(f"--- {timestamp} ---")
        print(f"Données reçues de l'appareil : {device_id}")
        print(f"  AP 1: {payload.AP1_MAC} (RSSI: {payload.AP1_RSSI})")
        print(f"  AP 2: {payload.AP2_MAC} (RSSI: {payload.AP2_RSSI})")
        print("---------------------------------")

        # --- C'EST ICI QUE VOUS CONTINUEZ LE PROJET ---
        
        # 1. Stocker les données 
        # (ex: appeler une fonction qui écrit dans une BDD SQLite ou un CSV)
        # store_in_database(device_id, timestamp, payload)
        
        # 2. Estimer la position 
        # (ex: appeler une fonction qui effectue la trilatération) [cite: 39]
        # estimated_position = calculate_position(payload)
        # print(f"  Position estimée : {estimated_position}")
        
        # 3. Stocker la position calculée
        # store_position(device_id, timestamp, estimated_position)

        # Répondre à TTN que tout s'est bien passé
        return {"status": "success", "message": "Données reçues et traitées"}

    except Exception as e:
        print(f"Erreur lors du traitement des données: {e}")
        # En cas d'erreur, informer TTN
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "Serveur de géolocalisation actif. L'endpoint est sur /ttn-webhook"}

# --- 3. Démarrer le serveur ---
if __name__ == "__main__":
    print("Démarrage du serveur FastAPI sur http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)