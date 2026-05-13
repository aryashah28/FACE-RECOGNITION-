import face_recognition
import os
import pickle

dataset_path = "Dataset"

known_encodings = []
known_names = []

for file in os.listdir(dataset_path):

    image_path = os.path.join(dataset_path, file)

    if not file.lower().endswith((".jpg", ".jpeg", ".png")):
        continue

    # load image properly
    image = face_recognition.load_image_file(r"C:\face_recognition_web_app\Dataset\ARYA.jpg")
    encodings = face_recognition.face_encodings(image)

    if len(encodings) > 0:

        encoding = encodings[0]

        name = os.path.splitext(file)[0]

        known_encodings.append(encoding)
        known_names.append(name)

data = {
    "encodings": known_encodings,
    "names": known_names
}

with open("encodings/face_encodings.pkl", "wb") as f:
    pickle.dump(data, f)

print("Encodings generated successfully")   