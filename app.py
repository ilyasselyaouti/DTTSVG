import requests
import subprocess
import os
import sys
from flask import Flask, request, jsonify
env_config = os.environ.copy()
env_config["OMP_NUM_THREADS"] = "1"

app = Flask(__name__)

# --- CONFIGURATION ---
HA_URL = "http://VOTRE_IP_HOME_ASSISTANT:8123"
HA_TOKEN = "HA_LONG_LIVE_TOKEN"
TTS_ENGINE = "tts.piper"
PIPER_VOICE = "fr_FR-siwis-medium"
OUTPUT_DIR = "/app/output"
PUBLIC_URL = "http://VOTRE_IP_LOCAL:3000/tts_visual.mp4"
# ---------------------

@app.route('/generate_tts_video', methods=['POST'])
def generate_video():
    data = request.json or {}
    text = data.get('text')
    
    print(f"\n--- NOUVELLE REQUÊTE RECUE ---", file=sys.stderr)
    print(f"Texte à générer : '{text}'", file=sys.stderr)
    
    if not text:
        print("Erreur : Texte manquant dans le payload", file=sys.stderr)
        return jsonify({"error": "Texte manquant"}), 400

    wav_path = "/tmp/tts.wav"
    mp4_path = os.path.join(OUTPUT_DIR, "tts_visual.mp4")

    headers = {
        'Authorization': f'Bearer {HA_TOKEN}',
        'Content-Type': 'application/json'
    }

    # 1. Demande de l'URL du cache TTS à HA
    try:
        payload = {
            "engine_id": TTS_ENGINE,
            "message": text,
            "language": "fr_FR",
            "options": {"voice": PIPER_VOICE}
        }
        print(f"[1/3] Demande de l'URL TTS à Home Assistant...", file=sys.stderr)
        ha_response = requests.post(f"{HA_URL}/api/tts_get_url", json=payload, headers=headers, timeout=10)
        
        print(f"Reponse HA Status: {ha_response.status_code}", file=sys.stderr)
        if ha_response.status_code != 200:
            print(f"Erreur HA body: {ha_response.text}", file=sys.stderr)
            return jsonify({"error": f"HA erreur {ha_response.status_code}"}), 500
            
        audio_data = ha_response.json()
        audio_url = audio_data.get("url")
        print(f"URL Audio reçue de HA : {audio_url}", file=sys.stderr)
        
        if not audio_url:
            return jsonify({"error": "Pas d'URL d'audio renvoyée"}, 500)
            
        if not audio_url.startswith("http"):
            audio_url = f"{HA_URL}{audio_url}"

        # 2. Téléchargement du fichier audio
        print(f"[2/3] Téléchargement du fichier audio depuis : {audio_url}", file=sys.stderr)
        audio_file_res = requests.get(audio_url, headers=headers, timeout=10)
        with open(wav_path, "wb") as f:
            f.write(audio_file_res.content)
        print(f"Fichier temporaire audio créé avec succès ({os.path.getsize(wav_path)} octets)", file=sys.stderr)

    except Exception as e:
        print(f"CRASH ÉTAPE AUDIO : {str(e)}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500

    print(f"[3/3] Lancement de l'encodage final...", file=sys.stderr)
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", wav_path,
        "-i", "/app/output/background.png",
        "-filter_complex", (
            # 1. On duplique l'audio dès l'entrée : une copie pour le son, une pour l'onde
            "[0:a]asplit=2[a_for_file][a_for_waves];"
            
            # 2. Flux fichier : On applique le délai
            "[a_for_file]adelay=2000|2000[a_out];"
            
            # 3. Flux onde : On applique le délai, puis showwaves
            "[a_for_waves]adelay=2000|2000,aformat=channel_layouts=mono,showwaves=s=1024x240:mode=line:rate=30:scale=sqrt:colors=0x00ccff[waves];"
            
            # 4. Padding vidéo
            "[waves]tpad=start_duration=2:color=black[v_padded];"
            
            # 5. Fond et Overlay
            "[1:v]scale=1024:600,format=rgba[bg];"
            "[bg][v_padded]overlay=0:180[v_final]"
        ),
        "-map", "[v_final]", 
        "-map", "[a_out]", 
        "-shortest",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k",
        mp4_path
    ]
    
    try:
        # On capture les erreurs de FFmpeg au lieu de les jeter au vide
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True, env=env_config)
        print(f"FFmpeg terminé avec succès. Vidéo générée dans {mp4_path}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"CRASH FFMPEG !", file=sys.stderr)
        print(f"FFmpeg STDOUT: {e.stdout}", file=sys.stderr)
        print(f"FFmpeg STDERR: {e.stderr}", file=sys.stderr)
        return jsonify({"error": "L'encodage FFmpeg a échoué"}), 500
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

    return jsonify({"success": True, "url": PUBLIC_URL})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)