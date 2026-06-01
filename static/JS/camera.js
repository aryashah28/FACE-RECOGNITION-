const video = document.getElementById("video");

navigator.mediaDevices.getUserMedia({video:true})
.then(stream=>video.srcObject=stream);

function captureImage(){
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video,0,0);
    return canvas.toDataURL("image/jpeg");
}

function analyzeFace(){
    const image = captureImage();
    fetch("/analyze_face", {
        method:"POST",
        body:new URLSearchParams({ image:image })
    }).then(res=>res.json())
    .then(data=>{
        document.getElementById("result").innerHTML =
        `<b>Name:</b> ${data.name} <br>
         <b>Age:</b> ${data.age} <br>
         <b>Gender:</b> ${data.gender} <br>
         <b>Emotion:</b> ${data.emotion}`;
    });
}