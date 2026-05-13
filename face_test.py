import face_recognition

image = face_recognition.load_image_file("C:\\Users\\aryas\\OneDrive\\Desktop\\face_recognition_web_app\\Dataset\\IMAGE 1.jpg")
encodings = face_recognition.face_encodings(image) 

if encodings:
    print("Face detected and encoded!")
else:
    print("No face found.")