# 1. Sử dụng Python chính thức bản nhẹ
FROM python:3.11-slim

# 2. Thiết lập thư mục làm việc trong container
WORKDIR /app

# 3. Copy file danh sách thư viện và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy toàn bộ code và dữ liệu vào container
COPY . .

# 5. Mở cổng 5501 (cổng mà server.py đang dùng)
EXPOSE 5501

# 6. Thiết lập biến môi trường (mặc định)
ENV FLASK_PORT=5501
ENV FLASK_HOST=0.0.0.0

# 7. Lệnh khởi chạy ứng dụng
CMD ["python", "server.py"]
