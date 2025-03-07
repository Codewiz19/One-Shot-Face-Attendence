let stream;
let photosTaken = {
    front: null,
    left: null,
    right: null
};

async function startCamera() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        document.getElementById('video').srcObject = stream;
    } catch (err) {
        console.error('Error accessing camera:', err);
        alert('Error accessing camera');
    }
}

function stopCamera() {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
}

function takePhoto(angle) {
    const video = document.getElementById('video');
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    
    photosTaken[angle] = canvas.toDataURL('image/jpeg');
    document.getElementById(`${angle}-photo`).style.backgroundImage = `url(${photosTaken[angle]})`;
    
    checkPhotosComplete();
}

function checkPhotosComplete() {
    const isComplete = photosTaken.front && photosTaken.left && photosTaken.right;
    document.getElementById('submit-btn').disabled = !isComplete;
}

async function registerStudent() {
    const name = document.getElementById('name-input').value;
    const roll = document.getElementById('roll-input').value;
    
    if (!name || !roll) {
        alert('Please enter both name and roll number');
        return;
    }

    const formData = new FormData();
    formData.append('name', name);
    formData.append('roll', roll);
    formData.append('front_photo', photosTaken.front);
    formData.append('left_photo', photosTaken.left);
    formData.append('right_photo', photosTaken.right);

    try {
        const response = await fetch('/register', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        alert(result.message);
        if (result.success) {
            resetRegistration();
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error registering student');
    }
}

function resetRegistration() {
    photosTaken = {
        front: null,
        left: null,
        right: null
    };
    ['front', 'left', 'right'].forEach(angle => {
        document.getElementById(`${angle}-photo`).style.backgroundImage = '';
    });
    document.getElementById('submit-btn').disabled = true;
    document.getElementById('name-input').value = '';
    document.getElementById('roll-input').value = '';
}

async function markAttendance() {
    const fileInput = document.getElementById('attendance-input');
    if (!fileInput.files[0]) {
        alert('Please select an image');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const response = await fetch('/mark-attendance', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        displayAttendanceResults(result);
    } catch (error) {
        console.error('Error:', error);
        alert('Error marking attendance');
    }
}

function displayAttendanceResults(data) {
    const resultsDiv = document.getElementById('attendance-results');
    resultsDiv.innerHTML = `
        <h3>Attendance Results:</h3>
        <p>Total faces detected: ${data.total_faces}</p>
        <p>Students marked present: ${data.present_count}</p>
        <table class="attendance-table">
            <thead>
                <tr>
                    <th>Roll Number</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody>
                ${data.attendance.map(entry => `
                    <tr>
                        <td>${entry.roll}</td>
                        <td>${entry.name}</td>
                        <td>${entry.status}</td>
                        <td>${entry.time}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}