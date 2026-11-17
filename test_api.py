import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("LLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL")

print(f"Base URL: {base_url}")

try:
    # Timeout scurt pentru a evita blocarea
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=10.0)
    
    # 1. Listăm modelele și eliminăm prefixul "models/"
    models = client.models.list()
    available_models = [m.id.replace("models/", "") for m in models.data]
    
    print(f"✅ Succes! Au fost găsite {len(available_models)} modele.\n")
    
    # 2. Filtrăm modelele stabile (conțin "flash", dar nu sunt TTS sau preview)
    test_models = [
        m for m in available_models 
        if "flash" in m.lower() and "tts" not in m.lower() and "preview" not in m.lower()
    ][:5]  # Testăm doar primele 5
    
    print("🚀 Se testează modelele disponibile (timeout 10s):")
    
    succes = False
    for model_name in test_models:
        print(f"\n⏳ Testare: {model_name} ...", end=" ", flush=True)
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "Raspunde doar cu: OK"}],
                max_tokens=5
            )
            print(f"✅ SUCCES!")
            print(f"   Răspuns: {response.choices[0].message.content.strip()}")
            print(f"\n💡 RECOMANDARE FINALĂ:")
            print(f"   Deschide fișierul .env și setează: LLM_MODEL={model_name}")
            succes = True
            break  # Oprim testarea după primul succes
            
        except Exception as e:
            eroare_scurta = str(e).replace('\n', ' ')[:70]
            print(f"❌ Eșec ({type(e).__name__}): {eroare_scurta}...")

    if not succes:
        print("\n⚠️ Niciun model nu a funcționat. Este posibil ca cheia API să aibă restricții de regiune sau să necesite activarea facturării (Cloud Billing) în Google Cloud Console.")

except Exception as e:
    print(f"\n❌ EROARE GENERALĂ: {type(e).__name__}")
    print(f"Detalii: {e}")