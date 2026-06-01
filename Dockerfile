FROM animcogn/face_recognition:cpu

WORKDIR /app

# Install system libraries needed by opencv-python
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .

# Install dependencies. Since face_recognition, dlib, and numpy are pre-installed
# in the base image, pip will verify them instantly and install the rest of requirements.
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]