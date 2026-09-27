from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import requests
from flask import Flask, jsonify, request
import threading
import time
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from data_pb2 import AccountPersonalShowInfo
from google.protobuf.descriptor import FieldDescriptor
import uid_generator_pb2
import GetWishListItems_pb2

# ------------------ Logging Setup ------------------
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ------------------ JWT Cache ------------------
jwt_tokens = {}
jwt_expiry = {}
jwt_lock = threading.Lock()

# ------------------ HTTP Session with Retries ------------------
def create_http_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.timeout = (5, 10)  # connect timeout, read timeout
    return session

http_session = create_http_session()

# ------------------ Protobuf to Dict ------------------
def proto_to_dict(message):
    """
    Safely converts protobuf to dict without relying on buggy 'label' attributes.
    """
    result = {}
    
    for field in getattr(message.DESCRIPTOR, 'fields', []):
        value = getattr(message, field.name)
        val_type = type(value).__name__
        
        if 'MapContainer' in val_type:
            map_result = {}
            for k, v in value.items():
                if hasattr(v, 'DESCRIPTOR'):
                    map_result[k] = proto_to_dict(v)
                elif isinstance(v, bytes):
                    map_result[k] = binascii.hexlify(v).decode('utf-8')
                else:
                    map_result[k] = v
            result[field.name] = map_result
            
        elif 'Repeated' in val_type:
            list_result = []
            for item in value:
                if hasattr(item, 'DESCRIPTOR'):
                    list_result.append(proto_to_dict(item))
                elif isinstance(item, bytes):
                    list_result.append(binascii.hexlify(item).decode('utf-8'))
                else:
                    list_result.append(item)
            result[field.name] = list_result
            
        elif hasattr(value, 'DESCRIPTOR'):
            result[field.name] = proto_to_dict(value)
            
        elif getattr(field, 'type', None) == 14: # 14 is FieldDescriptor.TYPE_ENUM
            try:
                result[field.name] = field.enum_type.values_by_number[value].name
            except:
                result[field.name] = value
                
        elif isinstance(value, bytes):
            result[field.name] = binascii.hexlify(value).decode('utf-8') if value else ""
            
        else:
            result[field.name] = value

    return result


def extract_token_from_response(data, region):
    """Safely extract JWT token from API response."""
    if not isinstance(data, dict):
        return None
    
    # Try common token keys
    token = data.get("jwt_token") or data.get("token") or data.get("access_token")
    if token:
        return token
    
    # Sometimes nested in 'data'
    if "data" in data and isinstance(data["data"], dict):
        token = data["data"].get("token") or data["data"].get("jwt_token")
        if token:
            return token
    
    # Legacy region-specific checks (kept for compatibility)
    if data.get("success") is True and "token" in data:
        return data["token"]
    
    if region == "IND":
        if data.get('status') in ['success', 'live']:
            return data.get('token')
    elif region in ["BR", "US", "SAC", "BD", "PK", "VN", "ME", "TH"]:
        if 'token' in data:
            return data['token']
    else:
        if data.get('status') == 'success':
            return data.get('token')
    
    return None

def ensure_jwt_token_sync(region):
    """Ensure JWT token is available; fetch/refresh automatically if missing or expired."""
    global jwt_tokens, jwt_expiry
    current_time = time.time()

    # Normalize region: 'DEFAULT' -> use 'default' key
    if region.upper() == "DEFAULT":
        region = "default"

    # If token exists and is valid, return it
    if region in jwt_tokens and current_time < jwt_expiry.get(region, 0):
        return jwt_tokens[region]

    with jwt_lock:
        # double-check after acquiring lock
        if region in jwt_tokens and current_time < jwt_expiry.get(region, 0):
            return jwt_tokens[region]

        logger.info(f"[JWT] Token missing or expired for {region}. Fetching...")

        endpoints = {
            "IND": "https://ff-jwt-mocha.vercel.app/token?uid=7841289991&password=ORIGIN-RXSWASO1W-PANKAJ",
            "BR": "https://ff-jwt-mocha.vercel.app/token?uid=7889211120&password=ORIGIN-ELFTO0C5W-PANKAJ",
            "US": "https://ff-jwt-mocha.vercel.app/token?uid={uid}&password={password}",
            "SAC": "https://ff-jwt-mocha.vercel.app/token?uid={uid}&password={password}",
            "BD": "https://ff-jwt-mocha.vercel.app/token?uid=7871185725&password=ORIGIN-RXSWASO1W-PANKAJ",
            "ID": "https://ff-jwt-mocha.vercel.app/token?uid=7898209388&password=error_PPA8W_BY_DIVAN_SINGH_2Z77X",
            "PK": "https://ff-jwt-mocha.vercel.app/token?uid=7898223495&password=error_CJO0M_BY_DIVAN_SINGH_2JDZX",
            "VN": "https://jwt-phi-ten.vercel.app/token?uid=6994726488&password=1_JAHID_X_EMPIRE_yLAicWRP",
            "ME": "https://jwt-phi-ten.vercel.app/token?uid=6994726488&password=1_JAHID_X_EMPIRE_yLAicWRP",
            "TH": "https://jwt-phi-ten.vercel.app/token?uid=6994726488&password=1_JAHID_X_EMPIRE_yLAicWRP",
            "default": "https://jwt-phi-ten.vercel.app/token?uid=6994726488&password=1_JAHID_X_EMPIRE_yLAicWRP"
        }

        url = endpoints.get(region, endpoints["default"])

        try:
            response = http_session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            token = extract_token_from_response(data, region)
            if token:
                jwt_tokens[region] = token
                jwt_expiry[region] = current_time + 600  # 10 minutes
                logger.info(f"[JWT] Token for {region} updated.")
                return token
            else:
                logger.error(f"[JWT] Failed to extract token for {region}. Response: {data}")

        except Exception as e:
            logger.error(f"[JWT] Request error for {region}: {e}")

    return jwt_tokens.get(region)


def get_api_endpoint(region):
    endpoints = {
        "IND": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow",
        "BR": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "US": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "SAC": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "BD": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "ID": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "PK": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "VN": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "ME": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "TH": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow",
        "default": "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
    }
    return endpoints.get(region, endpoints["default"])

default_key = "Yg&tc%DEuh6%Zc^8"
default_iv = "6oyZDr22E3ychjM%"

def encrypt_aes(hex_data, key, iv):
    key = key.encode()[:16]
    iv = iv.encode()[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()

def apis(idd, region):
    token = ensure_jwt_token_sync(region)
    if not token:
        raise Exception(f"Failed to get JWT token for region {region}")
    
    endpoint = get_api_endpoint(region)
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'Authorization': f'Bearer {token}',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB54',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    
    try:
        data = bytes.fromhex(idd)
        response = http_session.post(endpoint, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        return response.content.hex()
    except requests.exceptions.RequestException as e:
        logger.error(f"[API] Request to {endpoint} failed: {e}")
        raise

# ------------------ Flask Routes ------------------
@app.route('/', methods=['GET'])
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FFtools.pro ACCOUNT INFO</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            :root {
                --silver-light: #f8fafc;
                --silver-mid: #cbd5e1;
                --silver-dark: #64748b;
                --silver-accent: #e2e8f0;
                --bg-dark: #090d16;
                --card-bg: rgba(15, 23, 42, 0.7);
                --glass-border: rgba(226, 232, 240, 0.15);
                --silver-glow: rgba(226, 232, 240, 0.25);
            }
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Outfit', sans-serif;
                background-color: var(--bg-dark);
                background-image: 
                    radial-gradient(at 0% 0%, rgba(30, 41, 59, 0.85) 0, transparent 55%), 
                    radial-gradient(at 50% 100%, rgba(15, 23, 42, 0.95) 0, transparent 50%), 
                    radial-gradient(at 100% 0%, rgba(51, 65, 85, 0.7) 0, transparent 50%);
                color: #f1f5f9;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                overflow: hidden;
            }
            .bg-animation {
                position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: -1;
                background-size: 45px 45px;
                background-image:
                  linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                  linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
            }
            .container {
                position: relative; 
                background: var(--card-bg);
                backdrop-filter: blur(20px); 
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid var(--glass-border); 
                padding: 3rem 2.5rem;
                border-radius: 28px; 
                text-align: center;
                box-shadow: 0 30px 60px -12px rgba(0, 0, 0, 0.75),
                            0 0 30px 0 rgba(226, 232, 240, 0.05);
                max-width: 580px; 
                width: 90%; 
                animation: float 6s ease-in-out infinite;
            }
            h1 {
                font-size: 2.6rem; 
                font-weight: 800; 
                margin-bottom: 0.6rem;
                background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 50%, #94a3b8 100%);
                -webkit-background-clip: text; 
                -webkit-text-fill-color: transparent;
                letter-spacing: -0.5px; 
                text-shadow: 0 0 30px rgba(255, 255, 255, 0.15);
                text-transform: uppercase;
            }
            .badge {
                display: inline-flex; align-items: center; gap: 8px;
                background: rgba(226, 232, 240, 0.08); 
                border: 1px solid rgba(226, 232, 240, 0.25);
                color: #e2e8f0; 
                padding: 8px 18px; 
                border-radius: 100px;
                font-size: 0.85rem; 
                font-weight: 600; 
                font-family: 'JetBrains Mono', monospace;
                margin-bottom: 2rem; 
                box-shadow: 0 0 20px rgba(226, 232, 240, 0.1);
                letter-spacing: 0.5px;
            }
            .dot {
                width: 8px; height: 8px; background-color: #38bdf8;
                border-radius: 50%; animation: pulse 2s infinite;
                box-shadow: 0 0 8px #38bdf8;
            }
            .code-box {
                background: rgba(0, 0, 0, 0.45); 
                border: 1px solid rgba(226, 232, 240, 0.12);
                border-radius: 14px; 
                padding: 1.25rem; 
                margin: 0 auto 1rem auto;
                font-family: 'JetBrains Mono', monospace; 
                font-size: 0.95rem;
                color: #cbd5e1; 
                word-break: break-all; 
                cursor: pointer; 
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            .code-box:last-of-type { margin-bottom: 2.2rem; }
            .code-box:hover { 
                border-color: rgba(226, 232, 240, 0.4); 
                background: rgba(255, 255, 255, 0.05);
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
                color: #ffffff;
            }
            .footer-links { 
                display: flex; 
                flex-direction: column; 
                gap: 12px; 
                margin-top: 1rem; 
            }
            .btn {
                text-decoration: none; 
                padding: 14px 22px; 
                border-radius: 14px;
                font-weight: 600; 
                font-size: 0.95rem;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
                display: flex;
                align-items: center; 
                justify-content: center; 
                gap: 12px;
                letter-spacing: 0.3px;
            }
            .btn-credit { 
                background: rgba(255, 255, 255, 0.04); 
                border: 1px solid rgba(226, 232, 240, 0.2); 
                color: #e2e8f0; 
            }
            .btn-credit:hover { 
                background: rgba(255, 255, 255, 0.1); 
                border-color: #ffffff;
                color: #ffffff;
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            }
            .btn-power {
                background: linear-gradient(135deg, #475569 0%, #1e293b 100%);
                border: 1px solid rgba(226, 232, 240, 0.3);
                color: #ffffff;
                box-shadow: 0 10px 20px -5px rgba(0, 0, 0, 0.5);
            }
            .btn-power:hover { 
                background: linear-gradient(135deg, #64748b 0%, #334155 100%);
                border-color: #ffffff;
                transform: translateY(-2px); 
                box-shadow: 0 15px 30px -10px rgba(226, 232, 240, 0.2); 
            }
            .btn-discord {
                background: linear-gradient(135deg, #5865F2 0%, #3b429f 100%);
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: #ffffff;
                box-shadow: 0 10px 20px -5px rgba(88, 101, 242, 0.4);
            }
            .btn-discord:hover {
                background: linear-gradient(135deg, #7983f5 0%, #4752c4 100%);
                border-color: #ffffff;
                transform: translateY(-2px);
                box-shadow: 0 15px 30px -10px rgba(88, 101, 242, 0.6);
            }
            @keyframes pulse {
                0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.7); }
                70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(56, 189, 248, 0); }
                100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
            }
            @keyframes float {
                0% { transform: translateY(0px); }
                50% { transform: translateY(-8px); }
                100% { transform: translateY(0px); }
            }
        </style>
    </head>
    <body>
        <div class="bg-animation"></div>
        <div class="container">
            <h1>Free Fire<br>PLAYER INFO API</h1>
            <div class="badge"><div class="dot"></div>API IS RUNNING</div>
            <div class="code-box" onclick="copyText('/info?uid={uid}')">/info?uid={uid}</div>
            <div class="code-box" onclick="copyText('/wishlist?uid={uid}')">/wishlist?uid={uid}</div>
            <div class="footer-links">
                <a href="https://FFtools.pro" target="_blank" class="btn btn-credit">
                    <i class="fas fa-globe"></i><span>Credit: FFtools.pro</span>
                </a>
                <a href="https://FFtools.pro" target="_blank" class="btn btn-power">
                    <i class="fas fa-bolt"></i><span>WEBSITE: FFtools.pro</span>
                </a>
                <a href="https://discord.gg/be36FunJ9Q" target="_blank" class="btn btn-discord">
                    <i class="fab fa-discord"></i><span>JOIN DISCORD</span>
                </a>
            </div>
        </div>
        <script>function copyText(text) { navigator.clipboard.writeText(text); }</script>
    </body>
    </html>
    """
    return html_content


@app.route('/info', methods=['GET'])
def get_player_info():
    try:
        uid = request.args.get('uid')
        region = request.args.get('region', 'BD').upper()
        custom_key = request.args.get('key', default_key)
        custom_iv = request.args.get('iv', default_iv)
        
        if not uid:
            return jsonify({"error": "UID parameter is required"}), 400
        
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        protobuf_data = message.SerializeToString()
        hex_data = binascii.hexlify(protobuf_data).decode()
        
        encrypted_hex = encrypt_aes(hex_data, custom_key, custom_iv)
        
        api_response = apis(encrypted_hex, region)
        if not api_response:
            return jsonify({"error": "Empty response from API"}), 400
        
        message = AccountPersonalShowInfo()
        message.ParseFromString(bytes.fromhex(api_response))
        
        result = proto_to_dict(message)
        return jsonify(result)
    
    except ValueError:
        return jsonify({"error": "Invalid UID format"}), 400
    except Exception as e:
        logger.error(f"[ERROR] Processing request: {e}")
        return jsonify({"error": f"Failure to process the data: {str(e)}"}), 500

@app.route('/wishlist', methods=['GET'])
def get_wishlist_info():
    try:
        uid = request.args.get('uid')
        region = request.args.get('region', 'BD').upper()
        custom_key = request.args.get('key', default_key)
        custom_iv = request.args.get('iv', default_iv)
        
        if not uid:
            return jsonify({"error": "UID parameter is required"}), 400

        req = GetWishListItems_pb2.CSGetWishListItemsReq()
        req.account_id = int(uid)
        
        protobuf_data = req.SerializeToString()
        hex_data = binascii.hexlify(protobuf_data).decode()
        encrypted_hex = encrypt_aes(hex_data, custom_key, custom_iv)
        
        base_endpoint = get_api_endpoint(region)
        wishlist_url = base_endpoint.replace("GetPlayerPersonalShow", "GetWishListItems")
        
        token = ensure_jwt_token_sync(region)
        headers = {
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
            'Connection': 'Keep-Alive',
            'Authorization': f'Bearer {token}',
            'X-Unity-Version': '2018.4.11f1',
            'X-GA': 'v1 1',
            'ReleaseVersion': 'OB54',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        response = http_session.post(wishlist_url, headers=headers, data=bytes.fromhex(encrypted_hex), timeout=10)
        response.raise_for_status()
        resp_hex = response.content.hex()
        
        res = GetWishListItems_pb2.CSGetWishListItemsRes()
        res.ParseFromString(bytes.fromhex(resp_hex))
        
        result = proto_to_dict(res)
        return jsonify(result)

    except Exception as e:
        logger.error(f"[ERROR] Wishlist request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/favicon.ico')
def favicon():
    return '', 404

# ------------------ Main ------------------
if __name__ == "__main__":
    # For production, use Gunicorn with multiple workers:
    # gunicorn -w 4 -b 0.0.0.0:1080 app:app
    app.run(host="0.0.0.0", port=1080, threaded=True)