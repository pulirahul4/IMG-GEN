import os
import subprocess
import time
import requests
from flask import Flask, jsonify, request, send_file, render_template_string, redirect, url_for, session
import sys
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps
import random
import base64
import uuid

NGROK_AUTH_TOKEN = "2xBAfbu33PAuxduxERGZXfcWzB8_4f5oZkcVFnJGGdcu1bozb"

# Try to find ngrok in common locations
possible_ngrok_paths = [
    # Current directory and subdirectories
    os.path.join(os.getcwd(), "ngrok.exe"),
    os.path.join(os.getcwd(), "ngrok", "ngrok.exe"),
    # Common installation paths
    r"C:\flask_ngrok_app\ngrok.exe",
    r"C:\ngrok\ngrok.exe",
    r"C:\tools\ngrok\ngrok.exe",
    os.path.expanduser("~/ngrok.exe"),
    os.path.expanduser("~/.ngrok/ngrok.exe"),
    os.path.expanduser("~/AppData/Local/ngrok/ngrok.exe"),
    "ngrok.exe"  # If it's in PATH
]

def find_ngrok():
    for path in possible_ngrok_paths:
        if os.path.exists(path):
            return path
    return None

NGROK_PATH = find_ngrok()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for session

# In-memory storage as a fallback if session is not working properly
global_image_storage = {}

# HTML template for the image upload interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Image Processor</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #6e8efb, #a777e3);
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #333;
        }
        .container {
            background-color: rgba(255, 255, 255, 0.9);
            border-radius: 20px;
            box-shadow: 0 15px 30px rgba(0, 0, 0, 0.2);
            padding: 30px;
            max-width: 800px;
            width: 90%;
            text-align: center;
            margin: 20px 0;
        }
        h1 {
            color: #5c67d9;
            margin-bottom: 25px;
        }
        .upload-area {
            border: 3px dashed #a777e3;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            transition: all 0.3s;
            background-color: rgba(167, 119, 227, 0.1);
        }
        .upload-area:hover {
            background-color: rgba(167, 119, 227, 0.2);
        }
        .btn {
            background: linear-gradient(135deg, #6e8efb, #a777e3);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 50px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
            margin: 10px;
            text-transform: uppercase;
            font-weight: bold;
            letter-spacing: 1px;
        }
        .btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        select {
            padding: 10px 15px;
            border-radius: 8px;
            border: 2px solid #a777e3;
            font-size: 16px;
            margin: 10px 0;
            width: 100%;
            max-width: 300px;
        }
        .result-section {
            display: {{ 'block' if original_image else 'none' }};
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #eee;
        }
        .image-container {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 20px;
            margin-top: 20px;
        }
        .image-box {
            flex: 1;
            min-width: 250px;
            max-width: 350px;
            margin-bottom: 15px;
            border: 1px solid #ddd;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }
        .image-box img {
            width: 100%;
            height: auto;
            display: block;
        }
        .image-title {
            background-color: #f8f9fa;
            padding: 10px;
            border-bottom: 1px solid #ddd;
            font-weight: bold;
            color: #5c67d9;
        }
        .effect-form {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .effect-form h3 {
            margin-top: 0;
            color: #5c67d9;
        }
        @media (max-width: 768px) {
            .container {
                width: 95%;
                padding: 20px;
            }
            .image-box {
                min-width: 200px;
            }
        }
        #file-name {
            margin-top: 10px;
            font-style: italic;
        }
        .btn-group {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 10px;
            margin: 15px 0;
        }
        /* Footer styles */
        .footer {
            margin-top: 40px;
            padding: 20px;
            text-align: center;
            border-top: 2px solid rgba(167, 119, 227, 0.3);
        }
        .footer-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
            background: linear-gradient(to right, #ff7675, #fd79a8, #a777e3, #6e8efb);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: inline-block;
        }
        .footer-text {
            font-size: 14px;
            color: #666;
        }
        .heart {
            color: #fd79a8;
            font-size: 18px;
            animation: heartbeat 1.5s infinite;
        }
        @keyframes heartbeat {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.2); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Image Processor</h1>
        
        <!-- Upload Form (only shown if no image is currently processed) -->
        {% if not original_image %}
        <form action="/upload" method="post" enctype="multipart/form-data">
            <div class="upload-area">
                <p>Upload an image to transform it</p>
                <input type="file" name="image" id="image-upload" style="display: none;" accept="image/*" required onchange="updateFileName()">
                <label for="image-upload" class="btn">Choose Image</label>
                <div id="file-name">No file chosen</div>
            </div>
            
            <div>
                <label for="effect">Choose an effect:</label>
                <select name="effect" id="effect">
                    <option value="cartoon">Cartoon Effect</option>
                    <option value="vintage">Vintage Look</option>
                    <option value="neon">Neon Glow</option>
                    <option value="posterize">Posterize</option>
                    <option value="pencil">Pencil Sketch</option>
                    <option value="gible">Gible Style</option>
                    <option value="pixel">Pixel Art</option>
                </select>
            </div>
            
            <button type="submit" class="btn">Process Image</button>
        </form>
        {% endif %}
        
        <!-- Results Section -->
        <div class="result-section" style="display: {{ 'block' if original_image else 'none' }};">
            <h2>Results</h2>
            
            <!-- Form to change effect without re-uploading -->
            {% if original_image %}
            <div class="effect-form">
                <h3>Try Different Effects</h3>
                <form action="/change-effect" method="post">
                    <select name="effect" id="change-effect">
                        <option value="cartoon" {{ 'selected' if current_effect == 'cartoon' else '' }}>Cartoon Effect</option>
                        <option value="vintage" {{ 'selected' if current_effect == 'vintage' else '' }}>Vintage Look</option>
                        <option value="neon" {{ 'selected' if current_effect == 'neon' else '' }}>Neon Glow</option>
                        <option value="posterize" {{ 'selected' if current_effect == 'posterize' else '' }}>Posterize</option>
                        <option value="pencil" {{ 'selected' if current_effect == 'pencil' else '' }}>Pencil Sketch</option>
                        <option value="gible" {{ 'selected' if current_effect == 'gible' else '' }}>Gible Style</option>
                        <option value="pixel" {{ 'selected' if current_effect == 'pixel' else '' }}>Pixel Art</option>
                    </select>
                    <button type="submit" class="btn">Apply Effect</button>
                </form>
            </div>
            {% endif %}
            
            <div class="image-container">
                {% if original_image %}
                <div class="image-box">
                    <div class="image-title">Original Image</div>
                    <img src="data:image/jpeg;base64,{{ original_image }}" alt="Original Image">
                </div>
                {% endif %}
                
                {% if processed_image %}
                <div class="image-box">
                    <div class="image-title">Processed Image ({{ current_effect }})</div>
                    <img src="data:image/jpeg;base64,{{ processed_image }}" alt="Processed Image">
                </div>
                {% endif %}
            </div>
            
            <div class="btn-group">
                {% if processed_image %}
                <a href="/download" class="btn">Download Result</a>
                {% endif %}
                
                <a href="/reset" class="btn" style="background: linear-gradient(135deg, #ff7675, #fd79a8);">
                    Upload New Image
                </a>
            </div>
        </div>
        
        <!-- Footer section -->
        <div class="footer">
            <div class="footer-title">Image Processor Studio</div>
            <div class="footer-text">Made with <span class="heart">♥</span> by Puli Rahul</div>
        </div>
    </div>
    
    <script>
        function updateFileName() {
            const input = document.getElementById('image-upload');
            const fileNameDisplay = document.getElementById('file-name');
            
            if (input.files.length > 0) {
                fileNameDisplay.textContent = input.files[0].name;
            } else {
                fileNameDisplay.textContent = 'No file chosen';
            }
        }
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, 
                               original_image=None, 
                               processed_image=None,
                               current_effect=None)

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return redirect(url_for('home'))
    
    file = request.files['image']
    if file.filename == '':
        return redirect(url_for('home'))
    
    # Generate a unique ID for this image session
    session_id = str(uuid.uuid4())
    session['image_session_id'] = session_id
    
    # Get the effect type
    effect = request.form.get('effect', 'cartoon')
    session['current_effect'] = effect
    
    # Read the image
    img = Image.open(file.stream)
    
    # Store original image
    original_buffer = io.BytesIO()
    img.save(original_buffer, format='JPEG')
    original_buffer.seek(0)
    original_data = original_buffer.getvalue()
    
    # Store in both session and global dict (belt and suspenders approach)
    global_image_storage[session_id] = {
        'original': original_data,
        'filename': file.filename
    }
    
    # Process the image based on the selected effect
    processed_img = apply_effect(img, effect)
    
    # Store processed image
    processed_buffer = io.BytesIO()
    processed_img.save(processed_buffer, format='JPEG')
    processed_buffer.seek(0)
    processed_data = processed_buffer.getvalue()
    
    # Store processed result
    global_image_storage[session_id]['processed'] = processed_data
    
    # Prepare base64 encoded images for display
    original_b64 = base64.b64encode(original_data).decode('utf-8')
    processed_b64 = base64.b64encode(processed_data).decode('utf-8')
    
    return render_template_string(HTML_TEMPLATE, 
                               original_image=original_b64, 
                               processed_image=processed_b64,
                               current_effect=effect)

@app.route('/change-effect', methods=['POST'])
def change_effect():
    # Get session ID
    session_id = session.get('image_session_id')
    
    if not session_id or session_id not in global_image_storage:
        return redirect(url_for('home'))
    
    # Get new effect
    effect = request.form.get('effect', 'cartoon')
    session['current_effect'] = effect
    
    # Get original image
    original_data = global_image_storage[session_id]['original']
    
    # Open image from bytes
    img = Image.open(io.BytesIO(original_data))
    
    # Process with new effect
    processed_img = apply_effect(img, effect)
    
    # Store new processed image
    processed_buffer = io.BytesIO()
    processed_img.save(processed_buffer, format='JPEG')
    processed_buffer.seek(0)
    processed_data = processed_buffer.getvalue()
    
    # Update storage
    global_image_storage[session_id]['processed'] = processed_data
    
    # Prepare base64 encoded images for display
    original_b64 = base64.b64encode(original_data).decode('utf-8')
    processed_b64 = base64.b64encode(processed_data).decode('utf-8')
    
    return render_template_string(HTML_TEMPLATE, 
                               original_image=original_b64, 
                               processed_image=processed_b64,
                               current_effect=effect)

@app.route('/download')
def download_image():
    session_id = session.get('image_session_id')
    
    if not session_id or session_id not in global_image_storage:
        return redirect(url_for('home'))
    
    processed_data = global_image_storage[session_id]['processed']
    original_filename = global_image_storage[session_id].get('filename', 'image.jpg')
    
    # Generate a sensible filename
    effect = session.get('current_effect', 'processed')
    filename = f"{os.path.splitext(original_filename)[0]}_{effect}.jpg"
    
    return send_file(
        io.BytesIO(processed_data),
        mimetype='image/jpeg',
        download_name=filename,
        as_attachment=True
    )

@app.route('/reset')
def reset():
    # Clear current session
    if 'image_session_id' in session:
        session_id = session['image_session_id']
        if session_id in global_image_storage:
            del global_image_storage[session_id]
        session.pop('image_session_id', None)
        session.pop('current_effect', None)
    
    return redirect(url_for('home'))

@app.route('/generate-image', methods=['GET', 'POST'])
def generate_image():
    # Get the prompt from the request (either query param or form data)
    prompt = request.args.get('prompt') or request.form.get('prompt') or "Default Image"
    
    # Create a new image with a random background color
    width, height = 500, 300
    r, g, b = random.randint(0, 200), random.randint(0, 200), random.randint(0, 200)
    
    # Create the image
    img = Image.new('RGB', (width, height), color=(r, g, b))
    draw = ImageDraw.Draw(img)
    
    # Try to use a font, fall back to default if not available
    try:
        # Try to find a font
        font_path = "arial.ttf"  # Default Windows font
        if os.path.exists("C:/Windows/Fonts/Arial.ttf"):
            font_path = "C:/Windows/Fonts/Arial.ttf"
        
        font = ImageFont.truetype(font_path, 30)
    except Exception:
        # Fall back to default font
        font = ImageFont.load_default()
    
    # Add text to the image
    text_width = draw.textlength(prompt, font=font)
    text_position = ((width - text_width) // 2, height // 2 - 15)
    draw.text(text_position, prompt, fill="white", font=font)
    
    # Save the image to a bytes buffer
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png')

def apply_effect(image, effect_type):
    # Create a copy to work with
    img = image.copy()
    
    # Apply different effects based on selection
    if effect_type == 'cartoon':
        # Enhanced cartoon effect
        # Step 1: Simplify colors more aggressively
        img = img.quantize(colors=6).convert('RGB')
        
        # Step 2: Apply bilateral filter effect (simulated)
        img = img.filter(ImageFilter.SMOOTH_MORE)
        
        # Step 3: Create stronger edges
        edges = img.filter(ImageFilter.FIND_EDGES)
        edges = ImageOps.invert(edges.convert('L'))
        edges = edges.filter(ImageFilter.GaussianBlur(radius=0.5))  # Reduced blur for sharper edges
        edges = ImageOps.invert(edges)
        
        # Step 4: Enhance contrast of edges
        enhancer = ImageEnhance.Contrast(edges)
        edges = enhancer.enhance(2.0)
        
        # Step 5: Blend with higher weight to make effect more noticeable
        img = Image.blend(img, edges.convert('RGB'), 0.4)
        
        # Step 6: Enhance color saturation 
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.4)
        
    elif effect_type == 'vintage':
        # Enhanced vintage effect
        # Step 1: Apply sepia tone with more pronounced effect
        width, height = img.size
        pixels = img.load()
        for py in range(height):
            for px in range(width):
                r, g, b = img.getpixel((px, py))
                tr = int(0.439 * r + 0.769 * g + 0.189 * b)  # Increased red component
                tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                pixels[px, py] = (min(tr, 255), min(tg, 255), min(tb, 255))
        
        # Step 2: Add a subtle yellow tint to highlight
        overlay = Image.new('RGB', img.size, (255, 240, 200))
        img = Image.blend(img, overlay, 0.1)
        
        # Step 3: Add vignette effect (darkened corners)
        # Create a radial gradient mask
        mask = Image.new('L', img.size, 0)
        draw = ImageDraw.Draw(mask)
        center_x, center_y = img.size[0] // 2, img.size[1] // 2
        max_radius = min(center_x, center_y)
        for r in range(max_radius, 0, -1):
            value = int(255 * (r / max_radius) ** 2)
            draw.ellipse((center_x-r, center_y-r, center_x+r, center_y+r), fill=value)
        
        # Apply vignette
        black = Image.new('RGB', img.size, (0, 0, 0))
        img = Image.composite(img, black, mask)
        
        # Step 4: Reduce contrast and add slight noise
        contrast = ImageEnhance.Contrast(img)
        img = contrast.enhance(0.85)
        
    elif effect_type == 'neon':
        # Enhanced neon glow effect
        # Step 1: Brighten the image
        brightness = ImageEnhance.Brightness(img)
        img = brightness.enhance(1.2)
        
        # Step 2: Apply more intense color saturation
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(2.5)  # Increased from 2.0
        
        # Step 3: Apply gaussian blur for glow
        glow = img.filter(ImageFilter.GaussianBlur(radius=2.5))
        
        # Step 4: Add strong edge detection
        edges = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
        edges = ImageEnhance.Brightness(edges).enhance(1.3)
        
        # Step 5: Blend glow with edges
        img = Image.blend(glow, edges, 0.6)
        
        # Step 6: Add final brightness pop
        brightness = ImageEnhance.Brightness(img)
        img = brightness.enhance(1.2)
        
    elif effect_type == 'posterize':
        # Enhanced posterize effect
        # Step 1: Enhance contrast first
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        
        # Step 2: Intensify colors
        color_enhancer = ImageEnhance.Color(img)
        img = color_enhancer.enhance(1.4)
        
        # Step 3: Reduce to fewer colors (more dramatic)
        img = ImageOps.posterize(img, 2)  # Reduced from 3 for more dramatic effect
        
        # Step 4: Add subtle edge enhancement
        img = img.filter(ImageFilter.EDGE_ENHANCE)
        
    elif effect_type == 'pencil':
        # Enhanced pencil sketch effect
        # Step 1: Convert to grayscale
        gray = img.convert('L')
        
        # Step 2: Invert
        inverted = ImageOps.invert(gray)
        
        # Step 3: Apply stronger blur for pencil effect
        blur = inverted.filter(ImageFilter.GaussianBlur(radius=12))  # Increased blur
        
        # Step 4: Blend using dodge blend mode (simulated)
        def dodge(a, b):
            return min(int(a * 255 / (256 - b)), 255) if b < 256 else 255
        
        # Apply dodge blending
        width, height = gray.size
        sketch = Image.new("L", (width, height))
        for x in range(width):
            for y in range(height):
                a = gray.getpixel((x, y))
                b = blur.getpixel((x, y))
                sketch.putpixel((x, y), dodge(a + 5, b))
        
        # Step 5: Enhance contrast for more defined lines
        enhancer = ImageEnhance.Contrast(sketch)
        img = enhancer.enhance(2.0)
        
    elif effect_type == 'gible':
        # Gible-inspired effect (blue dragon Pokemon style)
        # Step 1: Enhance blues and create a bluish tint
        width, height = img.size
        pixels = img.load()
        
        # Apply blue-tinted color transformation
        for py in range(height):
            for px in range(width):
                r, g, b = img.getpixel((px, py))
                # Boost blues, reduce reds slightly
                new_r = int(r * 0.85)
                new_g = int(g * 0.95)
                new_b = min(255, int(b * 1.3))  # Enhance blues
                pixels[px, py] = (new_r, new_g, new_b)
        
        # Step 2: Apply cartoon-like effect
        img = img.quantize(colors=16).convert('RGB')
        
        # Step 3: Add edge detection with blue tint
        edges = img.filter(ImageFilter.FIND_EDGES)
        edges = edges.convert('RGB')
        
        # Tint the edges blue
        width, height = edges.size
        pixels = edges.load()
        for py in range(height):
            for px in range(width):
                r, g, b = edges.getpixel((px, py))
                if r > 30 or g > 30 or b > 30:  # If it's an edge
                    pixels[px, py] = (0, 40, 100)  # Dark blue edge
        
        # Step 4: Blend with original quantized image
        img = Image.blend(img, edges, 0.3)
        
        # Step 5: Add a subtle blue gradient overlay
        gradient = Image.new('RGB', img.size, (30, 60, 170))
        img = Image.blend(img, gradient, 0.15)
        
        # Step 6: Enhance contrast and saturation
        contrast = ImageEnhance.Contrast(img)
        img = contrast.enhance(1.2)
        saturation = ImageEnhance.Color(img)
        img = saturation.enhance(1.3)
    
    elif effect_type == 'pixel':
        # Pixelated effect
        # Determine pixel size based on image dimensions
        width, height = img.size
        pixel_size = max(width, height) // 50  # Adjust divisor for pixel size
        
        # Create a small version and then resize it back up to create pixelation
        small = img.resize((width // pixel_size, height // pixel_size), Image.NEAREST)
        img = small.resize(img.size, Image.NEAREST)
        
        # Enhance colors to make the pixelated effect more vibrant
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.3)
    
    return img

def check_ngrok_installation():
    if not NGROK_PATH:
        print("Error: ngrok not found in any of these locations:")
        for path in possible_ngrok_paths:
            print(f"- {path}")
        print("\nPlease:")
        print("1. Download ngrok from https://ngrok.com/download")
        print("2. Extract the ngrok.exe file")
        print("3. Place it in the same directory as this script or add it to your PATH")
        sys.exit(1)
    else:
        print(f"Using ngrok from: {NGROK_PATH}")

def start_ngrok():
    check_ngrok_installation()
    
    try:
        # Save the auth token
        result = subprocess.run(
            [NGROK_PATH, "authtoken", NGROK_AUTH_TOKEN],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error setting ngrok authtoken: {result.stderr}")
            sys.exit(1)

        # Start ngrok tunnel on port 5000
        ngrok_process = subprocess.Popen(
            [NGROK_PATH, "http", "5000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for ngrok to initialize
        time.sleep(3)

        # Check if ngrok process is still running
        if ngrok_process.poll() is not None:
            stdout, stderr = ngrok_process.communicate()
            print(f"ngrok failed to start: {stderr.decode()}")
            sys.exit(1)

        # Get the public URL
        try:
            response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
            response.raise_for_status()
            tunnels = response.json()
            if not tunnels.get('tunnels'):
                raise ValueError("No tunnels available")
            
            public_url = tunnels['tunnels'][0]['public_url']
            print(f" * ngrok tunnel started at: {public_url}")
            print(f" * Open this URL in your browser to access the image processor")
            
        except requests.RequestException as e:
            print(f"Error getting ngrok public URL: {e}")
            ngrok_process.terminate()
            sys.exit(1)

        return ngrok_process

    except Exception as e:
        print(f"Unexpected error starting ngrok: {e}")
        sys.exit(1)

if __name__ == '__main__':
    print("Starting ngrok tunnel...")
    ngrok_proc = start_ngrok()
    
    try:
        print("Starting Flask application...")
        app.run(port=5000)
    except Exception as e:
        print(f"Error running Flask application: {e}")
    finally:
        print("Shutting down ngrok...")
        ngrok_proc.terminate()
        ngrok_proc.wait() 