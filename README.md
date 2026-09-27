# 🔥 newinfo — Free Fire Info API

> Lightweight REST API for Free Fire player data, built with Flask + Protocol Buffers, deployed on Vercel.

---

## 📁 Project Structure

newinfo/
├── app.py # Flask app — route definitions & request handling
├── data_pb2.py # Compiled protobuf — player/response data schema
├── GetWishListItems_pb2.py # Compiled protobuf — wishlist/item schema
├── uid_generator_pb2.py # Compiled protobuf — UID encoding/generation
├── requirements.txt # Python dependencies
└── vercel.json # Vercel serverless config


---

## 🚀 Quick Start

### 1. Clone

```bash
git clone https://github.com/Errorexe849/newinfo.git
cd newinfo
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run locally

```bash
python app.py
```

API runs at `http://localhost:5000`

---

## 🌐 Deployment (Vercel)

This project is configured for Vercel serverless deployment out of the box.

```bash
npm i -g vercel
vercel
```

`vercel.json` handles routing — Flask app is served as a serverless function.

---

## 📡 Endpoints

### `GET /`
Health check. Returns API status.

**Response:**
```json
{
  "status": "ok",
  "message": "Free Fire Info API is live"
}
```

---

### `GET /info?uid=<player_uid>&region=<region>`
Fetch player info by UID.

**Query Parameters:**

| Param    | Type   | Required | Description                              |
|----------|--------|----------|------------------------------------------|
| `uid`    | string | ✅       | Free Fire player UID                     |
| `region` | string | ✅       | Server region (`IND`, `BR`, `US`, `SG`, `ID`, `TW`, `TH`, `VN`, `ME`, `PK`, `CIS`, `BD`) |

**Example:**

GET /info?uid=123456789&region=IND


**Response:**
```json
{
  "uid": "123456789",
  "nickname": "PlayerName",
  "level": 72,
  "region": "IND",
  "likes": 4200,
  "exp": 980000,
  "badge_count": 14,
  "guild": {
    "id": "987654321",
    "name": "EliteSquad",
    "level": 5
  }
}
```

---

### `GET /wishlist?uid=<player_uid>&region=<region>`
Fetch player wishlist items.

**Query Parameters:**

| Param    | Type   | Required | Description           |
|----------|--------|----------|-----------------------|
| `uid`    | string | ✅       | Free Fire player UID  |
| `region` | string | ✅       | Server region code    |

**Example:**

GET /wishlist?uid=123456789&region=IND


**Response:**
```json
{
  "uid": "123456789",
  "wishlist": [
    { "item_id": "900000001", "item_name": "Skyler", "type": "character" },
    { "item_id": "200000042", "item_name": "Phantom Bear Bundle", "type": "bundle" }
  ]
}
```

---

## 🔧 Protobuf Schemas

The API uses compiled Protocol Buffers for efficient serialization when communicating with Free Fire's internal services.

| File                      | Purpose                                      |
|---------------------------|----------------------------------------------|
| `data_pb2.py`             | Player profile & stats message schema        |
| `GetWishListItems_pb2.py` | Wishlist item request/response schema        |
| `uid_generator_pb2.py`    | UID encoding for internal API requests       |

> **Note:** These are pre-compiled `.proto` files. Do not edit directly — recompile from `.proto` source using `protoc` if schema changes are needed.

```bash
protoc --python_out=. yourschema.proto
```

---

## 📦 Requirements

See `requirements.txt`. Key dependencies:

flask
requests
protobuf


Install all:

```bash
pip install -r requirements.txt
```

---

## 🌍 Supported Regions

| Code  | Region                  |
|-------|-------------------------|
| IND   | India                   |
| BR    | Brazil                  |
| US    | United States           |
| SG    | Singapore               |
| ID    | Indonesia               |
| TW    | Taiwan                  |
| TH    | Thailand                |
| VN    | Vietnam                 |
| ME    | Middle East             |
| PK    | Pakistan                |
| CIS   | CIS (Russia/post-Soviet)|
| BD    | Bangladesh              |

---

## ⚠️ Error Responses

| Status | Meaning                                      |
|--------|----------------------------------------------|
| 400    | Missing or invalid query parameters          |
| 404    | Player UID not found in the given region     |
| 500    | Internal error / upstream Free Fire API fail |

**Example error:**
```json
{
  "error": "Player not found",
  "code": 404
}
```

---

## 📝 Notes

- This API proxies Free Fire's internal endpoints using protobuf encoding. It is **unofficial** and not affiliated with Garena.
- Rate limiting depends on the upstream service. Cache responses where possible.
- UID must match the target region — cross-region lookups will return 404.

---

## 👤 Author

**Errorexe849** — [github.com/Errorexe849](https://github.com/Errorexe849)

---

## 📄 License

MIT — do what you want, ship what you build.
