import cv2
import os

# Ask user name
username = input("Enter user name: ")

# Create folder to store face images
dataset_path = "dataset"
user_folder = os.path.join(dataset_path, username)
os.makedirs(user_folder, exist_ok=True)

# Load Haar Cascade for face detection
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
if face_cascade.empty():
    print("Error: Haar Cascade not loaded")

# Open webcam
camera = cv2.VideoCapture(0)

count = 0
print("Capturing face images... Press 'q' to stop")

while True:
    ret, frame = camera.read()
    if not ret:
        break

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect faces FIRST
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=6,
        minSize=(60, 60)
    )

    print("Faces detected:", len(faces))

    # NOW you can use faces
    cv2.putText(frame, f"Faces: {len(faces)}", (20,40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

    for (x, y, w, h) in faces:
        count += 1

        face_img = gray[y:y+h, x:x+w]
        file_name = os.path.join(user_folder, f"{count}.jpg")
        cv2.imwrite(file_name, face_img)

        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

    cv2.imshow("Face Capture", frame)

    if count >= 1:
        break

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break


    # Convert to grayscale (ONLY once)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect faces
    faces = face_cascade.detectMultiScale(
    gray,
    scaleFactor=1.1,
    minNeighbors=6,
    minSize=(60, 60)
)

    for (x, y, w, h) in faces:
        count += 1

        # Crop face
        face_img = gray[y:y+h, x:x+w]

        # Save face image
        file_name = os.path.join(user_folder, f"{count}.jpg")
        cv2.imwrite(file_name, face_img)

        # Draw rectangle on color frame
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

    # Show camera
    cv2.imshow("Face Capture", frame)

    # Stop after capturing 1 image
    if count >= 1:
        break

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

camera.release()
cv2.destroyAllWindows()

print("Face capture completed!")