import os
import base64
import cv2
import numpy as np
import face_recognition
from flask import Flask, request, jsonify, render_template
from PIL import Image
import io
import json
from datetime import datetime
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure folders
app.config['DATABASE_FOLDER'] = 'database'
app.config['ATTENDANCE_FOLDER'] = 'attendance_logs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Create necessary folders
os.makedirs(app.config['DATABASE_FOLDER'], exist_ok=True)
os.makedirs(app.config['ATTENDANCE_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_base64_image(base64_string, filepath):
    try:
        if 'data:image' in base64_string:
            base64_string = base64_string.split(',')[1]
        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data))
        image.save(filepath)
        return True
    except Exception as e:
        logger.error(f"Error saving base64 image: {str(e)}")
        return False

def get_student_data():
    try:
        student_data = {}
        for student_folder in os.listdir(app.config['DATABASE_FOLDER']):
            folder_path = os.path.join(app.config['DATABASE_FOLDER'], student_folder)
            if os.path.isdir(folder_path):
                info_file = os.path.join(folder_path, 'info.json')
                if os.path.exists(info_file):
                    with open(info_file, 'r') as f:
                        info = json.load(f)
                        student_data[student_folder] = info
        return student_data
    except Exception as e:
        logger.error(f"Error getting student data: {str(e)}")
        return {}

def process_attendance_image(image_path):
    try:
        # Load student database
        known_faces = {}
        student_data = get_student_data()
        
        # First, load all known face encodings
        for student_id, info in student_data.items():
            student_folder = os.path.join(app.config['DATABASE_FOLDER'], student_id)
            encodings = []
            
            # Load encodings from all three angles
            for angle in ['front', 'left', 'right']:
                image_path_angle = os.path.join(student_folder, f'{angle}.jpg')
                if os.path.exists(image_path_angle):
                    face_image = face_recognition.load_image_file(image_path_angle)
                    face_encodings = face_recognition.face_encodings(face_image)
                    if face_encodings:
                        encodings.extend(face_encodings)
            
            if encodings:
                known_faces[student_id] = {
                    'encodings': encodings,
                    'info': info
                }

        logger.info(f"Loaded {len(known_faces)} students from database")

        # Load and process the attendance image
        attendance_image = face_recognition.load_image_file(image_path)
        
        # Find all faces in the image
        face_locations = face_recognition.face_locations(attendance_image, model="hog")
        face_encodings = face_recognition.face_encodings(attendance_image, face_locations)

        logger.info(f"Found {len(face_locations)} faces in attendance image")

        attendance = []
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Process each face found in the attendance image
        for idx, (face_encoding, face_location) in enumerate(zip(face_encodings, face_locations)):
            best_match = None
            best_distance = 1.0
            
            # Compare with each known student
            for student_id, data in known_faces.items():
                # Compare with all angles of the student
                distances = [face_recognition.face_distance([known_encoding], face_encoding)[0] 
                           for known_encoding in data['encodings']]
                min_distance = min(distances) if distances else 1.0
                
                if min_distance < best_distance and min_distance < 0.5:  # Threshold for face matching
                    best_distance = min_distance
                    best_match = (student_id, data['info'])

            # Record attendance
            if best_match:
                confidence = 1 - best_distance
                attendance.append({
                    'roll': best_match[1]['roll'],
                    'name': best_match[1]['name'],
                    'status': 'Present',
                    'confidence': f"{confidence:.2%}",
                    'time': current_time,
                    'face_number': idx + 1
                })
                logger.info(f"Matched face {idx + 1} with student {best_match[1]['name']}")
            else:
                attendance.append({
                    'roll': 'Unknown',
                    'name': 'Unknown',
                    'status': 'Unknown',
                    'confidence': '0%',
                    'time': current_time,
                    'face_number': idx + 1
                })
                logger.info(f"Face {idx + 1} not matched with any student")

        # Save attendance record
        date_str = datetime.now().strftime("%Y-%m-%d")
        attendance_file = os.path.join(app.config['ATTENDANCE_FOLDER'], f'attendance_{date_str}.csv')
        
        df = pd.DataFrame(attendance)
        if os.path.exists(attendance_file):
            existing_df = pd.read_csv(attendance_file)
            df = pd.concat([existing_df, df], ignore_index=True)
        df.to_csv(attendance_file, index=False)

        return {
            'total_faces': len(face_encodings),
            'present_count': len([a for a in attendance if a['status'] == 'Present']),
            'attendance': attendance,
            'success': True
        }

    except Exception as e:
        logger.error(f"Error processing attendance image: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register-page')
def register_page():
    return render_template('register.html')

@app.route('/attendance-page')
def attendance_page():
    return render_template('attendance.html')

@app.route('/register', methods=['POST'])
def register():
    try:
        name = request.form.get('name')
        roll = request.form.get('roll')
        
        if not name or not roll:
            return jsonify({'success': False, 'message': 'Name and roll number are required'})

        # Clean the roll number to avoid invalid characters in folder name
        roll = ''.join(e for e in roll if e.isalnum())
        student_folder = os.path.join(app.config['DATABASE_FOLDER'], roll)
        
        if os.path.exists(student_folder):
            return jsonify({'success': False, 'message': 'Student already registered'})

        os.makedirs(student_folder, exist_ok=True)

        # Save student info
        info = {'name': name, 'roll': roll}
        info_path = os.path.join(student_folder, 'info.json')
        with open(info_path, 'w') as f:
            json.dump(info, f)

        # Save face photos
        success = True
        for angle in ['front', 'left', 'right']:
            photo_data = request.form.get(f'{angle}_photo')
            if photo_data:
                try:
                    filepath = os.path.join(student_folder, f'{angle}.jpg')
                    # Remove header from base64 string if present
                    if 'base64,' in photo_data:
                        photo_data = photo_data.split('base64,')[1]
                    
                    # Decode and save image
                    img_data = base64.b64decode(photo_data)
                    with open(filepath, 'wb') as f:
                        f.write(img_data)
                    
                    # Verify the image was saved correctly
                    if not os.path.exists(filepath):
                        raise Exception(f"Failed to save {angle} photo")
                    
                    # Verify it's a valid image
                    img = face_recognition.load_image_file(filepath)
                    if img is None:
                        raise Exception(f"Invalid image for {angle} angle")
                    
                except Exception as e:
                    logger.error(f"Error saving {angle} photo: {str(e)}")
                    success = False
            else:
                success = False
                logger.error(f"Missing {angle} photo")

        if not success:
            # Clean up if there was an error
            if os.path.exists(student_folder):
                import shutil
                shutil.rmtree(student_folder)
            return jsonify({'success': False, 'message': 'Failed to save all photos'})

        logger.info(f"Successfully registered student: {name} ({roll})")
        return jsonify({'success': True, 'message': 'Student registered successfully'})

    except Exception as e:
        logger.error(f"Error registering student: {str(e)}")
        # Clean up if there was an error
        if 'student_folder' in locals() and os.path.exists(student_folder):
            import shutil
            shutil.rmtree(student_folder)
        return jsonify({'success': False, 'message': str(e)})

@app.route('/mark-attendance', methods=['POST'])
def mark_attendance():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})

    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Invalid file'})

    try:
        # Save uploaded file temporarily
        temp_path = 'temp.jpg'
        file.save(temp_path)

        # Process attendance
        results = process_attendance_image(temp_path)

        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return jsonify(results)

    except Exception as e:
        logger.error(f"Error marking attendance: {str(e)}")
        if os.path.exists('temp.jpg'):
            os.remove('temp.jpg')
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get-attendance-records', methods=['GET'])
def get_attendance_records():
    try:
        date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
        attendance_file = os.path.join(app.config['ATTENDANCE_FOLDER'], f'attendance_{date}.csv')
        
        if not os.path.exists(attendance_file):
            return jsonify({'success': False, 'message': 'No attendance records found for this date'})
        
        df = pd.read_csv(attendance_file)
        records = df.to_dict('records')
        
        return jsonify({
            'success': True,
            'date': date,
            'records': records
        })
    
    except Exception as e:
        logger.error(f"Error getting attendance records: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Unhandled error: {str(error)}")
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)