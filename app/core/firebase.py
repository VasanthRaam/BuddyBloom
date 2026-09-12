import os
import json
import firebase_admin
from firebase_admin import credentials

def init_firebase_admin() -> bool:
    """
    Initializes Firebase Admin SDK using the first available method:
    1. FIREBASE_SERVICE_ACCOUNT_JSON environment variable (JSON string)
    2. Local serviceAccountKey.json file
    3. Google Application Default Credentials (ADC) for Cloud Run / GCP
    4. Default firebase_admin.initialize_app()
    """
    if firebase_admin._apps:
        return True

    # 1. Check env var containing raw JSON string
    service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") or os.environ.get("FIREBASE_CREDENTIALS")
    if service_account_json:
        try:
            cred_dict = json.loads(service_account_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("✅ [FIREBASE] Initialized from FIREBASE_SERVICE_ACCOUNT_JSON env var")
            return True
        except Exception as e:
            print(f"⚠️ [FIREBASE] Failed to init from env var JSON: {e}")

    # 2. Check local file paths
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    possible_paths = [
        os.path.join(base_dir, "serviceAccountKey.json"),
        os.path.join(os.path.dirname(base_dir), "serviceAccountKey.json"),
        os.path.join(os.getcwd(), "serviceAccountKey.json"),
        os.environ.get("FIREBASE_KEY_PATH", ""),
    ]
    for path in possible_paths:
        if path and os.path.exists(path):
            try:
                cred = credentials.Certificate(path)
                firebase_admin.initialize_app(cred)
                print(f"✅ [FIREBASE] Initialized from key file: {path}")
                return True
            except Exception as e:
                print(f"⚠️ [FIREBASE] Failed to init from key file {path}: {e}")

    # 3. Fallback to Google Application Default Credentials (GCP / Cloud Run)
    try:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
        print("✅ [FIREBASE] Initialized using Application Default Credentials (ADC)")
        return True
    except Exception as e:
        print(f"⚠️ [FIREBASE] Failed to init via ADC: {e}")

    # 4. Default initialization
    try:
        firebase_admin.initialize_app()
        print("✅ [FIREBASE] Initialized default app")
        return True
    except Exception as e:
        print(f"❌ [FIREBASE] Could not initialize Firebase Admin SDK: {e}")
        return False
