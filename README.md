# 🌍 Megacity AQI — Dashboard AI

Dashboard giám sát chất lượng không khí thời gian thực cho khu vực TP.HCM, Bình Dương, Bà Rịa - Vũng Tàu, với AI chatbot hỗ trợ phân tích.

## ✨ Tính năng

- 🗺️ **Bản đồ tương tác** — Click bất kỳ đâu để xem AQI nội suy (IDW)
- 🔥 **Heatmap** — Bản đồ nhiệt chất lượng không khí toàn megacity
- 💨 **Wind Visualization** — Mũi tên gió + luồng hạt (particle flow)
- ⏱ **Timeline** — Xem diễn biến AQI 24 giờ qua
- 🔀 **Compare** — So sánh 2 điểm bất kỳ trên bản đồ
- 🤖 **AI Chat** — Hỏi đáp chuyên gia AQI (Groq/Llama 3.1)
- 📈 **24h Trend** — Biểu đồ xu hướng theo trạm
- 🏫 **POI Alert** — Cảnh báo trường học/bệnh viện khi AQI cao

## 📊 Dữ liệu

| Nguồn | Mục đích |
|---|---|
| [aqi.in](https://aqi.in) | AQI, PM2.5, PM10, NO₂, O₃, CO, SO₂, thời tiết |
| [Groq API](https://groq.com) | AI chat (Llama 3.1 8B Instant) |
| [OpenStreetMap](https://overpass-api.de) | Tìm trường học, bệnh viện (Overpass API) |
| [Nominatim](https://nominatim.openstreetmap.org) | Geocoding tìm kiếm địa điểm |

**12 trạm**: 7 core (HCM 4 + Bình Dương 1 + Bà Rịa-Vũng Tàu 2) + 5 buffer (Long An 3 + Tây Ninh 2)

## 🚀 Cài đặt

### Yêu cầu
- Python 3.10+
- Token từ [aqi.in](https://aqi.in)
- (Tùy chọn) API key từ [Groq](https://console.groq.com)

### Chạy local

```bash
# 1. Clone repo
git clone <repo-url>
cd aqi_app

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Cấu hình
cp .env.example .env
# Mở .env và điền AUTH_TOKEN + GROQ_API_KEY

# 4. Chạy server
python server.py
```

Mở trình duyệt: **http://localhost:5501**

### Chạy bằng Docker

```bash
# Build và chạy
docker-compose up -d

# Xem logs
docker-compose logs -f
```

## 🧪 Testing

```bash
python -m pytest tests/ -v
```

## 📁 Cấu trúc dự án

```
aqi_app/
├── server.py              # Flask backend (API + proxy)
├── .env.example           # Template cấu hình
├── requirements.txt       # Python dependencies
├── stations_url.txt       # Danh sách 12 trạm AQI
├── geoBoundaries-*.geojson # Ranh giới 3 tỉnh megacity
├── Dockerfile             # Docker build
├── docker-compose.yml     # Docker deploy
├── data/                  # Cache (auto-generated)
├── tests/                 # Unit tests
│   ├── test_server.py
│   └── test_map_logic.py
└── web/                   # Frontend
    ├── map.html           # Dashboard chính
    ├── css/style.css      # Custom CSS (glassmorphism)
    └── js/
        ├── core.js        # Constants, IDW, utilities
        ├── wind.js        # Wind arrows + flow field
        ├── features.js    # Timeline, Compare, POI
        └── app.js         # Map init, rendering, chat
```

## 👥 API Endpoints

| Route | Method | Mô tả |
|---|---|---|
| `/` | GET | Dashboard |
| `/api/stations` | GET | Tất cả trạm (cached 15 phút) |
| `/api/refresh` | GET | Force refresh (cooldown 60s) |
| `/api/history/<slug>` | GET | Lịch sử 24h (`?sensor=aqi\|pm25\|...`) |
| `/api/poi` | GET | Trường/BV gần đó (`?lat=&lng=&radius=`) |
| `/api/chat` | POST | AI chat (`{message, context}`) |
| `/api/health` | GET | Server health check |
