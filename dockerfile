FROM python:3.10

WORKDIR /app

COPY . /app

RUN apt-get update && apt-get install -y \
    cmake \
    libgl1 \
    libglib2.0-0 \
    build-essential

RUN pip install --upgrade pip

RUN pip install flask
RUN pip install opencv-python
RUN pip install numpy
RUN pip install face_recognition

EXPOSE 5000

CMD ["python", "app.py"]