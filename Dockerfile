FROM animcogn/face_recognition:cpu

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .

# Install dependencies. Since face_recognition, dlib, and numpy are pre-installed
# in the base image, pip will verify them instantly and install the rest of requirements.
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
