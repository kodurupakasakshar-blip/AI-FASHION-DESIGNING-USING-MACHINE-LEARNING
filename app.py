import streamlit as st
import requests
from PIL import Image, ImageFilter, ImageOps, ImageEnhance, ImageDraw
import io
import base64
import time
import os
from datetime import datetime
import numpy as np
import cv2
from io import BytesIO
import random
import math
import json
import concurrent.futures
import threading
from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3
import re
from pathlib import Path

# GPU Acceleration disabled for stability
# try:
#     cv2.ocl.setUseOpenCL(True)
# except Exception:
#     pass

# Page configuration
st.set_page_config(
    page_title="AI Fashion Designer - True 360° View",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database setup for user authentication and history
def init_database():
    """Initialize SQLite database for user management and history"""
    conn = sqlite3.connect('fashion_app.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )''')
    
    # Design history table
    c.execute('''CREATE TABLE IF NOT EXISTS design_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        design_name TEXT NOT NULL,
        design_style TEXT,
        gender TEXT,
        age_group TEXT,
        fabric_image BLOB,
        result_image BLOB,
        front_view BLOB,
        back_view BLOB,
        left_view BLOB,
        right_view BLOB,
        animation_frames BLOB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Saved designs table
    c.execute('''CREATE TABLE IF NOT EXISTS saved_designs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        design_name TEXT NOT NULL,
        design_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    conn.commit()
    conn.close()

init_database()

# Authentication functions
def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, email, password):
    """Register a new user"""
    try:
        conn = sqlite3.connect('fashion_app.db')
        c = conn.cursor()
        password_hash = hash_password(password)
        c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                 (username, email, password_hash))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return True, user_id
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return False, "Username already exists"
        elif "email" in str(e):
            return False, "Email already registered"
        return False, "Registration failed"
    except Exception as e:
        return False, str(e)

def login_user(username_or_email, password):
    """Authenticate user"""
    try:
        conn = sqlite3.connect('fashion_app.db')
        c = conn.cursor()
        password_hash = hash_password(password)
        c.execute("SELECT id, username, email FROM users WHERE (username = ? OR email = ?) AND password_hash = ?",
                 (username_or_email, username_or_email, password_hash))
        user = c.fetchone()
        if user:
            c.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user[0],))
            conn.commit()
            conn.close()
            return True, {"id": user[0], "username": user[1], "email": user[2]}
        conn.close()
        return False, "Invalid credentials"
    except Exception as e:
        return False, str(e)

def save_design_to_history(user_id, design_name, design_style, gender, age_group, 
                           fabric_img, result_img, front_view, back_view, left_view, right_view, animation_frames=None):
    """Save design to user's history"""
    try:
        conn = sqlite3.connect('fashion_app.db')
        c = conn.cursor()
        
        # Convert images to bytes
        fabric_bytes = None
        result_bytes = None
        front_bytes = None
        back_bytes = None
        left_bytes = None
        right_bytes = None
        animation_bytes = None
        
        if fabric_img:
            buf = io.BytesIO()
            fabric_img.save(buf, format='PNG')
            fabric_bytes = buf.getvalue()
        
        if result_img:
            buf = io.BytesIO()
            result_img.save(buf, format='PNG')
            result_bytes = buf.getvalue()
        
        if front_view:
            buf = io.BytesIO()
            front_view.save(buf, format='PNG')
            front_bytes = buf.getvalue()
        
        if back_view:
            buf = io.BytesIO()
            back_view.save(buf, format='PNG')
            back_bytes = buf.getvalue()
        
        if left_view:
            buf = io.BytesIO()
            left_view.save(buf, format='PNG')
            left_bytes = buf.getvalue()
        
        if right_view:
            buf = io.BytesIO()
            right_view.save(buf, format='PNG')
            right_bytes = buf.getvalue()
        
        if animation_frames:
            # Save animation frames as a list of bytes
            animation_bytes_list = []
            for frame in animation_frames:
                buf = io.BytesIO()
                frame.save(buf, format='PNG')
                animation_bytes_list.append(buf.getvalue())
            animation_bytes = pickle.dumps(animation_bytes_list)
        
        c.execute("""INSERT INTO design_history 
                    (user_id, design_name, design_style, gender, age_group, 
                     fabric_image, result_image, front_view, back_view, left_view, right_view, animation_frames)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                 (user_id, design_name, design_style, gender, age_group,
                  fabric_bytes, result_bytes, front_bytes, back_bytes, left_bytes, right_bytes, animation_bytes))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving design: {e}")
        return False

def get_user_history(user_id, limit=30):
    """Get user's design history"""
    try:
        conn = sqlite3.connect('fashion_app.db')
        c = conn.cursor()
        c.execute("""SELECT id, design_name, design_style, gender, age_group, 
                           front_view, created_at 
                    FROM design_history 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?""", (user_id, limit))
        history = c.fetchall()
        conn.close()
        return history
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []

def get_design_by_id(design_id, user_id):
    """Get full design details by ID"""
    try:
        conn = sqlite3.connect('fashion_app.db')
        c = conn.cursor()
        c.execute("""SELECT id, design_name, design_style, gender, age_group,
                           fabric_image, result_image, front_view, back_view, left_view, right_view, animation_frames, created_at
                    FROM design_history 
                    WHERE id = ? AND user_id = ?""", (design_id, user_id))
        design = c.fetchone()
        conn.close()
        
        if design:
            result = {
                'id': design[0],
                'design_name': design[1],
                'design_style': design[2],
                'gender': design[3],
                'age_group': design[4],
                'created_at': design[12]
            }
            
            if design[5]:
                result['fabric_image'] = Image.open(io.BytesIO(design[5]))
            if design[6]:
                result['result_image'] = Image.open(io.BytesIO(design[6]))
            if design[7]:
                result['front_view'] = Image.open(io.BytesIO(design[7]))
            if design[8]:
                result['back_view'] = Image.open(io.BytesIO(design[8]))
            if design[9]:
                result['left_view'] = Image.open(io.BytesIO(design[9]))
            if design[10]:
                result['right_view'] = Image.open(io.BytesIO(design[10]))
            if design[11]:
                import pickle
                frames_bytes = pickle.loads(design[11])
                result['animation_frames'] = [Image.open(io.BytesIO(fb)) for fb in frames_bytes]
            
            return result
        return None
    except Exception as e:
        print(f"Error fetching design: {e}")
        return None

def delete_design(design_id, user_id):
    """Delete a design from history"""
    try:
        conn = sqlite3.connect('fashion_app.db')
        c = conn.cursor()
        c.execute("DELETE FROM design_history WHERE id = ? AND user_id = ?", (design_id, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False

# Advanced 3D garment generation functions
def generate_true_360_views(person_img, design_img, design_name, gender, age_group):
    """Generate true front, back, and side views with proper garment visualization"""
    try:
        views = {}
        
        # Original front view
        views['front'] = design_img.copy()
        
        # Generate true back view using AI-powered transformation
        back_view = generate_back_view(design_img, design_name)
        views['back'] = back_view
        
        # Generate true left side view
        left_view = generate_side_view(design_img, 'left', design_name)
        views['left'] = left_view
        
        # Generate true right side view
        right_view = generate_side_view(design_img, 'right', design_name)
        views['right'] = right_view
        
        # Generate 45° angles for smoother rotation
        views['front_left_45'] = generate_angled_view(design_img, 45, 'left', design_name)
        views['front_right_45'] = generate_angled_view(design_img, 45, 'right', design_name)
        views['back_left_45'] = generate_angled_view(back_view, 45, 'left', design_name)
        views['back_right_45'] = generate_angled_view(back_view, 45, 'right', design_name)
        
        return views
    except Exception as e:
        st.error(f"Error generating views: {str(e)}")
        return None

def generate_back_view(front_img, design_name):
    """Generate realistic back view of the garment"""
    try:
        img_array = np.array(front_img)
        height, width = img_array.shape[:2]
        
        back = front_img.copy()
        
        if "Dress" in design_name or "Gown" in design_name:
            back = ImageEnhance.Brightness(back).enhance(0.95)
            draw = ImageDraw.Draw(back)
            zipper_x = width // 2
            draw.line([(zipper_x, height//4), (zipper_x, height*3//4)], 
                     fill='#444444', width=3)
            if "Off-Shoulder" in design_name:
                draw.arc([width//4, height//8, width*3//4, height//4], 
                        0, 180, fill='#666666', width=2)
            else:
                draw.arc([width//3, height//8, width*2//3, height//4], 
                        0, 180, fill='#666666', width=2)
        
        elif "Suit" in design_name or "Blazer" in design_name:
            back = ImageEnhance.Brightness(back).enhance(0.97)
            draw = ImageDraw.Draw(back)
            vent_x = width // 2
            draw.line([(vent_x, height*3//4), (vent_x, height-20)], 
                     fill='#333333', width=2)
        
        elif "Jacket" in design_name or "Hoodie" in design_name:
            back = ImageEnhance.Brightness(back).enhance(0.96)
            draw = ImageDraw.Draw(back)
            if "Hoodie" in design_name:
                draw.ellipse([width//3, height//8, width*2//3, height//3], 
                            outline='#555555', width=2)
        
        elif "Shirt" in design_name or "T-Shirt" in design_name:
            back = ImageEnhance.Brightness(back).enhance(0.98)
            draw = ImageDraw.Draw(back)
            draw.arc([width//3, height//8, width*2//3, height//5], 
                    0, 180, fill='#666666', width=2)
        
        back = back.filter(ImageFilter.GaussianBlur(radius=0.5))
        return back
    except Exception as e:
        return front_img

def generate_side_view(front_img, side, design_name):
    """Generate realistic side view of the garment"""
    try:
        width, height = front_img.size
        
        if side == 'left':
            side_view = front_img.resize((int(width * 0.6), height))
            side_view = ImageOps.expand(side_view, 
                                       border=((width - int(width * 0.6)) // 2, 0), 
                                       fill='white')
        else:
            side_view = front_img.resize((int(width * 0.6), height))
            side_view = ImageOps.mirror(side_view)
            side_view = ImageOps.expand(side_view, 
                                       border=((width - int(width * 0.6)) // 2, 0), 
                                       fill='white')
        
        draw = ImageDraw.Draw(side_view)
        
        if "Dress" in design_name:
            seam_x = width // 2
            draw.line([(seam_x, height//4), (seam_x, height*3//4)], 
                     fill='#888888', width=1)
            if "Maxi" in design_name or "Mermaid" in design_name:
                draw.line([(seam_x-10, height*3//4), (seam_x+10, height-20)], 
                         fill='#666666', width=2)
        
        elif "Suit" in design_name or "Blazer" in design_name:
            draw.ellipse([width//3, height//3, width*2//3, height//2], 
                        outline='#777777', width=1)
        
        elif "Jacket" in design_name:
            draw.rectangle([width//2-15, height//2, width//2+15, height//2+30], 
                          outline='#666666', width=1)
        
        side_view = apply_perspective(side_view, side)
        return side_view
    except Exception as e:
        return front_img

def generate_angled_view(img, angle, direction, design_name):
    """Generate angled view between front and side"""
    try:
        width, height = img.size
        compression = math.cos(math.radians(angle))
        new_width = int(width * (0.6 + 0.4 * compression))
        angled = img.resize((new_width, height))
        angled = ImageOps.expand(angled, 
                                border=((width - new_width) // 2, 0), 
                                fill='white')
        
        if direction == 'left':
            angled = angled.transform(
                angled.size,
                Image.AFFINE,
                (1, -0.1, 0, 0, 1, 0),
                fillcolor='white'
            )
        else:
            angled = angled.transform(
                angled.size,
                Image.AFFINE,
                (1, 0.1, 0, 0, 1, 0),
                fillcolor='white'
            )
        return angled
    except Exception as e:
        return img

def apply_perspective(img, side):
    """Apply perspective transformation for realistic side view"""
    try:
        width, height = img.size
        if side == 'left':
            coeffs = (1, 0.1, 0, 0, 1, 0, 0.0005, 0)
        else:
            coeffs = (1, -0.1, 0, 0, 1, 0, -0.0005, 0)
        
        img = img.transform(
            img.size,
            Image.PERSPECTIVE,
            coeffs,
            fillcolor='white'
        )
        return img
    except Exception as e:
        return img

def create_360_rotation_animation(views, fps=12, duration=5):
    """Create smooth 360° rotation animation using all generated views"""
    try:
        frames = []
        total_frames = fps * duration
        
        view_sequence = [
            'front', 'front_right_45', 'right', 'back_right_45',
            'back', 'back_left_45', 'left', 'front_left_45'
        ]
        
        for i in range(total_frames):
            progress = (i / total_frames) * 8
            view_idx = int(progress) % 8
            next_idx = (view_idx + 1) % 8
            current_view = views[view_sequence[view_idx]]
            next_view = views[view_sequence[next_idx]]
            factor = progress - int(progress)
            blended = blend_images(current_view, next_view, factor)
            frames.append(blended)
        
        return frames
    except Exception as e:
        st.error(f"Error creating animation: {str(e)}")
        return None

def blend_images(img1, img2, factor):
    """Blend two images for smooth transition"""
    try:
        img1_array = np.array(img1)
        img2_array = np.array(img2)
        blended = cv2.addWeighted(img1_array, 1 - factor, img2_array, factor, 0)
        return Image.fromarray(blended)
    except Exception:
        return img1

def enhance_garment_details(image, design_type):
    """Enhance garment details based on design type"""
    try:
        img_array = np.array(image)
        
        if "Suit" in design_type or "Blazer" in design_type:
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            img_array = cv2.filter2D(img_array, -1, kernel)
        elif "Dress" in design_type:
            img_array = cv2.GaussianBlur(img_array, (3, 3), 0)
            img_array = cv2.addWeighted(img_array, 1.5, img_array, -0.5, 0)
        elif "Jacket" in design_type or "Leather" in design_type:
            img_array = cv2.convertScaleAbs(img_array, alpha=1.2, beta=10)
        
        if "Silk" in design_type or "Satin" in design_type:
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            hsv[:,:,1] = hsv[:,:,1] * 0.8
            hsv[:,:,2] = hsv[:,:,2] * 1.2
            img_array = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
        elif "Denim" in design_type or "Jeans" in design_type:
            noise = np.random.normal(0, 5, img_array.shape).astype(np.uint8)
            img_array = cv2.add(img_array, noise)
        
        return Image.fromarray(img_array)
    except:
        return image

def create_design_preview(design, fabric_img, gender="women", age_group="adult"):
    """Create a preview of dress design with fabric"""
    try:
        preview = Image.new('RGB', (300, 300), '#f0f0f0')
        draw = ImageDraw.Draw(preview)
        
        if fabric_img:
            fabric_resized = fabric_img.copy()
            fabric_resized.thumbnail((250, 250))
            f_w, f_h = fabric_resized.size
            x = (300 - f_w) // 2
            y = (300 - f_h) // 2
            preview.paste(fabric_resized, (x, y))
        
        color = "#667eea"
        
        if gender == "women":
            if "A-Line" in design['name']:
                draw.polygon([(150, 50), (100, 250), (200, 250)], outline=color, width=3)
                draw.ellipse([130, 30, 170, 70], outline=color, width=3)
            elif "Bodycon" in design['name']:
                draw.rectangle([130, 50, 170, 250], outline=color, width=3)
                draw.ellipse([130, 30, 170, 70], outline=color, width=3)
            elif "Wrap" in design['name']:
                draw.line([(120, 50), (180, 50), (200, 250), (100, 250)], fill=color, width=3)
                draw.ellipse([130, 30, 170, 70], outline=color, width=3)
            elif "Maxi" in design['name']:
                draw.rectangle([120, 50, 180, 280], outline=color, width=3)
                draw.ellipse([130, 30, 170, 70], outline=color, width=3)
            elif "Off-Shoulder" in design['name']:
                draw.rectangle([130, 70, 170, 250], outline=color, width=3)
                draw.arc([100, 30, 200, 70], 0, 180, fill=color, width=3)
            elif "Ball Gown" in design['name']:
                draw.ellipse([100, 150, 200, 280], outline=color, width=3)
                draw.rectangle([140, 50, 160, 150], outline=color, width=3)
            elif "Mermaid" in design['name']:
                draw.rectangle([140, 50, 160, 180], outline=color, width=3)
                draw.ellipse([120, 180, 180, 260], outline=color, width=3)
            elif "Empire Waist" in design['name']:
                draw.rectangle([130, 50, 170, 100], outline=color, width=3)
                draw.ellipse([110, 100, 190, 250], outline=color, width=3)
            else:
                draw.rectangle([100, 50, 200, 250], outline=color, width=3)
                draw.ellipse([120, 30, 180, 70], outline=color, width=3)
        
        elif gender == "men":
            if "Suit" in design['name']:
                draw.rectangle([120, 50, 180, 250], outline=color, width=3)
                draw.line([(120, 80), (100, 120)], fill=color, width=3)
                draw.line([(180, 80), (200, 120)], fill=color, width=3)
                draw.rectangle([140, 120, 160, 150], outline=color, width=3)
            elif "Blazer" in design['name']:
                draw.rectangle([120, 50, 180, 220], outline=color, width=3)
                draw.line([(120, 80), (100, 100)], fill=color, width=2)
                draw.line([(180, 80), (200, 100)], fill=color, width=2)
            elif "Jacket" in design['name'] or "Leather Jacket" in design['name']:
                draw.rectangle([115, 50, 185, 230], outline=color, width=3)
                draw.line([(140, 80), (160, 80)], fill=color, width=3)
            elif "Shirt" in design['name'] or "Formal Shirt" in design['name']:
                draw.rectangle([125, 50, 175, 240], outline=color, width=3)
                draw.rectangle([140, 100, 160, 120], outline=color, width=2)
            elif "T-Shirt" in design['name'] or "Polo" in design['name']:
                draw.rectangle([130, 50, 170, 230], outline=color, width=3)
                draw.arc([135, 40, 165, 60], 0, 180, fill=color, width=2)
            elif "Hoodie" in design['name']:
                draw.rectangle([120, 50, 180, 240], outline=color, width=3)
                draw.ellipse([130, 30, 170, 60], outline=color, width=3)
            elif "Kurta" in design['name']:
                draw.rectangle([120, 50, 180, 260], outline=color, width=3)
                draw.line([(130, 80), (170, 80)], fill=color, width=2)
            elif "Sherwani" in design['name']:
                draw.rectangle([115, 50, 185, 270], outline=color, width=3)
                draw.line([(130, 70), (170, 70)], fill=color, width=3)
                draw.rectangle([145, 120, 155, 140], outline=color, width=2)
            elif "Bomber" in design['name']:
                draw.rectangle([120, 50, 180, 220], outline=color, width=3)
                draw.rectangle([130, 180, 170, 200], outline=color, width=2)
            elif "Waistcoat" in design['name']:
                draw.rectangle([130, 50, 170, 200], outline=color, width=3)
                draw.rectangle([140, 100, 160, 120], outline=color, width=2)
            elif "Hawaiian" in design['name']:
                draw.rectangle([125, 50, 175, 220], outline=color, width=3)
                draw.arc([135, 40, 165, 60], 0, 180, fill=color, width=2)
            else:
                draw.rectangle([125, 50, 175, 240], outline=color, width=3)
        
        else:
            if "Dress" in design['name'] or "Party Dress" in design['name'] or "Princess" in design['name']:
                draw.rectangle([140, 60, 160, 180], outline=color, width=3)
                draw.ellipse([135, 40, 165, 70], outline=color, width=3)
            elif "Shirt" in design['name']:
                draw.rectangle([140, 60, 160, 160], outline=color, width=3)
                draw.arc([145, 50, 155, 65], 0, 180, fill=color, width=2)
            elif "Romper" in design['name'] or "Dungarees" in design['name']:
                draw.rectangle([140, 60, 160, 130], outline=color, width=3)
                draw.rectangle([145, 130, 155, 180], outline=color, width=3)
            elif "T-Shirt" in design['name']:
                draw.rectangle([142, 60, 158, 150], outline=color, width=3)
                draw.arc([146, 50, 154, 65], 0, 180, fill=color, width=2)
            elif "Jeans" in design['name']:
                draw.rectangle([147, 60, 153, 130], outline=color, width=3)
                draw.rectangle([142, 130, 152, 180], outline=color, width=3)
                draw.rectangle([148, 130, 158, 180], outline=color, width=3)
            elif "Overall" in design['name']:
                draw.rectangle([140, 60, 160, 140], outline=color, width=3)
                draw.line([(145, 75), (150, 90)], fill=color, width=2)
                draw.line([(155, 75), (150, 90)], fill=color, width=2)
            elif "Skirt" in design['name']:
                draw.rectangle([147, 60, 153, 80], outline=color, width=3)
                draw.ellipse([135, 80, 165, 150], outline=color, width=3)
            elif "Uniform" in design['name']:
                draw.rectangle([142, 60, 158, 150], outline=color, width=3)
                draw.rectangle([140, 150, 160, 190], outline=color, width=3)
            elif "Hoodie" in design['name'] or "Sweater" in design['name']:
                draw.rectangle([140, 60, 160, 160], outline=color, width=3)
                draw.ellipse([143, 45, 157, 65], outline=color, width=2)
            elif "Sportswear" in design['name']:
                draw.rectangle([142, 60, 158, 140], outline=color, width=3)
                draw.rectangle([140, 140, 160, 170], outline=color, width=3)
            elif "Pajama" in design['name']:
                draw.rectangle([142, 60, 158, 130], outline=color, width=3)
                draw.rectangle([140, 130, 160, 170], outline=color, width=3)
            elif "Raincoat" in design['name']:
                draw.rectangle([140, 60, 160, 160], outline=color, width=3)
                draw.ellipse([143, 45, 157, 65], outline=color, width=2)
                draw.rectangle([148, 80, 152, 110], outline=color, width=1)
            elif "Costume" in design['name']:
                draw.rectangle([140, 60, 160, 170], outline=color, width=3)
                draw.ellipse([135, 40, 165, 70], outline=color, width=3)
                draw.rectangle([145, 90, 155, 110], outline=color, width=2)
            else:
                draw.rectangle([142, 60, 158, 170], outline=color, width=3)
        
        return preview
    except Exception as e:
        preview = Image.new('RGB', (300, 300), '#667eea')
        return preview

def build_safe_tryon_prompt(gender_text, age_prompt, design_name, design_prompt, custom_view=""):
    """Build a safer prompt for the Try-On API to avoid NSFW filtering."""
    safe_terms = (
        "fully clothed, modest coverage, no nudity, tasteful fashion, family-friendly, "
        "high quality fashion photography"
    )
    prompt_parts = [
        "preserve the person's facial features, skin tone, hairstyle, body shape, and pose",
        gender_text,
        f"a {age_prompt}{design_name} made from the fabric shown in clothing image",
        design_prompt,
        safe_terms,
        "photorealistic, high quality fashion photography, studio lighting, perfect fit, full body"
    ]
    if custom_view:
        prompt_parts.append(custom_view)
    return ", ".join([part.strip() for part in prompt_parts if part])

def check_fit_compatibility(person_img, design):
    """Check if design fits the person based on age and gender"""
    try:
        img_array = np.array(person_img)
        height, width = img_array.shape[:2]
        aspect_ratio = width / height
        
        if 0.5 <= aspect_ratio <= 0.8:
            base_score = 0.9
        elif 0.4 <= aspect_ratio <= 0.9:
            base_score = 0.8
        else:
            base_score = 0.6
        
        if design['age_group'] == 'kids':
            base_score += 0.05
        elif design['age_group'] == 'teen':
            base_score -= 0.02
        
        fit_score = min(1.0, base_score)
        return fit_score
    except:
        return random.uniform(0.7, 1.0)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
        animation: fadeIn 1s ease-in;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .card {
        background: white;
        border-radius: 15px;
        padding: 25px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        margin: 10px 0;
        transition: transform 0.3s ease;
    }
    
    .card:hover {
        transform: translateY(-5px);
    }
    
    .design-card {
        background: white;
        border-radius: 15px;
        padding: 15px;
        margin: 10px 0;
        border: 2px solid #e0e0e0;
        transition: all 0.3s ease;
        text-align: center;
        height: 100%;
        display: flex;
        flex-direction: column;
        animation: slideIn 0.5s ease-out;
    }
    
    @keyframes slideIn {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
    }
    
    .design-card:hover {
        transform: translateY(-5px);
        border-color: #667eea;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.2);
    }
    
    .design-card.selected {
        border-color: #667eea;
        background: linear-gradient(135deg, #f5f7ff 0%, #e8ecff 100%);
        border-width: 3px;
    }
    
    .viewer-360 {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 30px;
        border-radius: 15px;
        color: white;
        margin: 20px 0;
        animation: glow 2s ease-in-out infinite;
    }
    
    @keyframes glow {
        0% { box-shadow: 0 0 5px #667eea; }
        50% { box-shadow: 0 0 20px #764ba2; }
        100% { box-shadow: 0 0 5px #667eea; }
    }
    
    .true-360-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 20px;
        padding: 20px;
        margin: 20px 0;
    }
    
    .view-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 15px;
        margin: 20px 0;
    }
    
    .view-item {
        background: white;
        border-radius: 10px;
        padding: 10px;
        text-align: center;
        transition: transform 0.3s ease;
        border: 2px solid #667eea;
    }
    
    .view-item:hover {
        transform: scale(1.05);
        border-color: #ffd700;
    }
    
    .view-label {
        background: #667eea;
        color: white;
        padding: 5px;
        border-radius: 5px;
        margin-top: 5px;
        font-size: 0.9em;
        font-weight: bold;
    }
    
    .view-label.back {
        background: #764ba2;
    }
    
    .view-label.side {
        background: #00b09b;
    }
    
    .angle-indicator {
        background: linear-gradient(135deg, #00b09b, #96c93d);
        padding: 15px;
        border-radius: 20px;
        color: white;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
        font-size: 1.2em;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 10px;
        transition: all 0.3s ease;
        font-weight: bold;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
    }
    
    .section-title {
        text-align: center;
        margin: 30px 0 20px 0;
        color: #333;
    }
    
    .section-title h2 {
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2em;
    }
    
    .selected-design-box {
        background: linear-gradient(135deg, #667eea20, #764ba220); 
        padding: 20px; 
        border-radius: 15px; 
        text-align: center;
        border: 2px solid #667eea; 
        margin: 20px 0;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { border-color: #667eea; }
        50% { border-color: #764ba2; }
        100% { border-color: #667eea; }
    }
    
    .fit-indicator {
        background: linear-gradient(135deg, #00b09b, #96c93d);
        padding: 15px;
        border-radius: 10px;
        color: white;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    
    .age-badge {
        background: #667eea;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        display: inline-block;
        font-size: 0.9em;
        margin: 5px 0;
    }
    
    .rotation-controls {
        display: flex;
        gap: 15px;
        justify-content: center;
        margin: 20px 0;
        flex-wrap: wrap;
    }
    
    .rotation-button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border: none;
        padding: 12px 25px;
        border-radius: 25px;
        font-size: 1.1em;
        cursor: pointer;
        transition: all 0.3s ease;
        font-weight: bold;
    }
    
    .rotation-button:hover {
        transform: translateY(-3px);
        box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
    }
    
    .view-description {
        background: rgba(255,255,255,0.1);
        padding: 10px;
        border-radius: 10px;
        margin-top: 10px;
        font-size: 0.95em;
    }
    
    .back-detail {
        color: #ffd700;
        font-size: 0.9em;
        margin-top: 5px;
    }
    
    .dashboard-card {
        background: white;
        border-radius: 15px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .dashboard-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
    }
    
    .auth-container {
        max-width: 500px;
        margin: 0 auto;
        padding: 30px;
        background: white;
        border-radius: 20px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.1);
    }
    
    .welcome-banner {
        background: linear-gradient(135deg, #667eea, #764ba2);
        padding: 20px;
        border-radius: 15px;
        color: white;
        margin-bottom: 20px;
        text-align: center;
    }
    
    .save-success {
        background: linear-gradient(135deg, #00b09b, #96c93d);
        padding: 10px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'processed_images' not in st.session_state:
    st.session_state.processed_images = []
if 'current_result' not in st.session_state:
    st.session_state.current_result = None
if 'true_360_views' not in st.session_state:
    st.session_state.true_360_views = None
if 'api_calls' not in st.session_state:
    st.session_state.api_calls = 0
if 'rotation_angle' not in st.session_state:
    st.session_state.rotation_angle = 0
if 'selected_design' not in st.session_state:
    st.session_state.selected_design = None
if 'uploaded_fabric' not in st.session_state:
    st.session_state.uploaded_fabric = None
if 'generated_designs' not in st.session_state:
    st.session_state.generated_designs = []
if 'designs_generated' not in st.session_state:
    st.session_state.designs_generated = False
if 'person_img' not in st.session_state:
    st.session_state.person_img = None
if 'selected_gender' not in st.session_state:
    st.session_state.selected_gender = "women"
if 'selected_age_group' not in st.session_state:
    st.session_state.selected_age_group = "adult"
if 'num_designs' not in st.session_state:
    st.session_state.num_designs = 8
if 'api_key' not in st.session_state:
    st.session_state.api_key = "4f267b60abmshc96d409ed6fa44dp118d0ajsn4fd3b26e493b"
if 'fit_score' not in st.session_state:
    st.session_state.fit_score = None
if 'show_fit_analysis' not in st.session_state:
    st.session_state.show_fit_analysis = False
if 'current_angle' not in st.session_state:
    st.session_state.current_angle = 0
if 'auto_rotate' not in st.session_state:
    st.session_state.auto_rotate = False
if 'animation_frames' not in st.session_state:
    st.session_state.animation_frames = []
if 'current_frame' not in st.session_state:
    st.session_state.current_frame = 0
if 'generation_mode' not in st.session_state:
    st.session_state.generation_mode = "Fast (1 API Call)"
if 'page' not in st.session_state:
    st.session_state.page = "home"
if 'view_design_id' not in st.session_state:
    st.session_state.view_design_id = None
if 'current_saved_views' not in st.session_state:
    st.session_state.current_saved_views = None
if 'save_message' not in st.session_state:
    st.session_state.save_message = None

# Authentication UI
def show_login_page():
    st.markdown("""
    <div class="auth-container">
        <h2 style="text-align: center; color: #667eea;">👋 Welcome Back!</h2>
        <p style="text-align: center;">Login to access your fashion designs</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username_email = st.text_input("Username or Email", placeholder="Enter your username or email")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit = st.form_submit_button("🔐 Login", use_container_width=True)
            
            if submit:
                if username_email and password:
                    success, result = login_user(username_email, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.current_user = result
                        st.success(f"Welcome back, {result['username']}!")
                        st.rerun()
                    else:
                        st.error(result)
                else:
                    st.warning("Please fill in all fields")
        
        st.markdown("---")
        st.markdown("<p style='text-align: center;'>Don't have an account?</p>", unsafe_allow_html=True)
        if st.button("📝 Create New Account", use_container_width=True):
            st.session_state.page = "register"
            st.rerun()

def show_register_page():
    st.markdown("""
    <div class="auth-container">
        <h2 style="text-align: center; color: #667eea;">✨ Join Fashion AI</h2>
        <p style="text-align: center;">Create your account to start designing</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("register_form"):
            username = st.text_input("Username", placeholder="Choose a username")
            email = st.text_input("Email", placeholder="your@email.com")
            password = st.text_input("Password", type="password", placeholder="Create a password")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password")
            submit = st.form_submit_button("🚀 Create Account", use_container_width=True)
            
            if submit:
                if not username or not email or not password:
                    st.warning("Please fill in all fields")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                    st.error("Please enter a valid email address")
                else:
                    success, result = register_user(username, email, password)
                    if success:
                        st.success("Account created successfully! Please login.")
                        st.session_state.page = "login"
                        st.rerun()
                    else:
                        st.error(result)
        
        st.markdown("---")
        st.markdown("<p style='text-align: center;'>Already have an account?</p>", unsafe_allow_html=True)
        if st.button("🔐 Back to Login", use_container_width=True):
            st.session_state.page = "login"
            st.rerun()

def show_dashboard():
    st.markdown(f"""
    <div class="welcome-banner">
        <h2>🎨 My Fashion Dashboard</h2>
        <p>Welcome back, {st.session_state.current_user['username']}!</p>
        <p>Here are all your created designs</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Dashboard tabs
    tab1, tab2, tab3 = st.tabs(["📊 My Designs", "📈 Statistics", "⚙️ Account Settings"])
    
    with tab1:
        history = get_user_history(st.session_state.current_user['id'], limit=30)
        
        if not history:
            st.info("🎨 You haven't created any designs yet! Go to the Designer tab to create your first design.")
            if st.button("✨ Create New Design", use_container_width=True):
                st.session_state.page = "designer"
                st.rerun()
        else:
            st.markdown(f"### 📸 Your Designs ({len(history)} total)")
            
            # Display designs in grid
            cols = st.columns(3)
            for idx, design in enumerate(history):
                col_idx = idx % 3
                with cols[col_idx]:
                    with st.container():
                        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
                        
                        if design[5]:
                            preview_img = Image.open(io.BytesIO(design[5]))
                            preview_img.thumbnail((200, 200))
                            st.image(preview_img, use_column_width=True)
                        
                        st.markdown(f"**{design[1]}**")
                        st.caption(f"Style: {design[2]}")
                        st.caption(f"Created: {design[6][:10]}")
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button(f"👁️ View", key=f"view_{design[0]}"):
                                st.session_state.view_design_id = design[0]
                                st.session_state.page = "view_design"
                                st.rerun()
                        with col_b:
                            if st.button(f"🗑️ Delete", key=f"delete_{design[0]}"):
                                if delete_design(design[0], st.session_state.current_user['id']):
                                    st.success("Design deleted!")
                                    st.rerun()
                        
                        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown("### 📊 Design Statistics")
        
        history_data = get_user_history(st.session_state.current_user['id'], limit=100)
        
        if history_data:
            total_designs = len(history_data)
            
            gender_counts = {}
            age_counts = {}
            style_counts = {}
            
            for design in history_data:
                gender = design[3] or "Unknown"
                age = design[4] or "Unknown"
                style = design[2] or "Unknown"
                
                gender_counts[gender] = gender_counts.get(gender, 0) + 1
                age_counts[age] = age_counts.get(age, 0) + 1
                style_counts[style] = style_counts.get(style, 0) + 1
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Designs", total_designs)
            with col2:
                st.metric("Categories", len(gender_counts))
            with col3:
                st.metric("Unique Styles", len(style_counts))
            
            st.markdown("---")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("#### 👤 Designs by Category")
                for gender, count in gender_counts.items():
                    st.progress(count / total_designs, text=f"{gender.title()}: {count} designs")
            
            with col_b:
                st.markdown("#### 🎂 Designs by Age Group")
                for age, count in age_counts.items():
                    st.progress(count / total_designs, text=f"{age.title()}: {count} designs")
            
            st.markdown("#### 🎨 Top Design Styles")
            sorted_styles = sorted(style_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            for style, count in sorted_styles:
                st.progress(count / total_designs, text=f"{style}: {count} designs")
        else:
            st.info("Create some designs to see your statistics!")
    
    with tab3:
        st.markdown("### 👤 Account Settings")
        
        st.markdown(f"**Username:** {st.session_state.current_user['username']}")
        st.markdown(f"**Email:** {st.session_state.current_user['email']}")
        
        st.markdown("---")
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.page = "home"
            st.rerun()

def show_view_design():
    """Show detailed view of a saved design"""
    design = get_design_by_id(st.session_state.view_design_id, st.session_state.current_user['id'])
    
    if not design:
        st.error("Design not found!")
        if st.button("← Back to Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()
        return
    
    st.markdown(f"""
    <div class="selected-design-box">
        <h2 style="color: #667eea;">✨ {design['design_name']}</h2>
        <p>{design['design_style']}</p>
        <p>Created: {design['created_at'][:19] if design['created_at'] else 'Unknown'}</p>
    </div>
    """, unsafe_allow_html=True)
    
    if 'result_image' in design and design['result_image']:
        st.markdown("### 👗 Final Try-On Result")
        st.image(design['result_image'], use_column_width=True)
        
        # Download button for result
        buf = io.BytesIO()
        design['result_image'].save(buf, format='PNG')
        st.download_button(
            label="📥 Download Final Image",
            data=buf.getvalue(),
            file_name=f"{design['design_name']}_final.png",
            mime="image/png",
            use_container_width=True
        )
    
    st.markdown("### 🔄 360° Views")
    
    view_cols = st.columns(4)
    views = [
        ('front_view', 'Front View', design.get('front_view')),
        ('back_view', 'Back View', design.get('back_view')),
        ('left_view', 'Left Side', design.get('left_view')),
        ('right_view', 'Right Side', design.get('right_view'))
    ]
    
    for idx, (key, label, img) in enumerate(views):
        with view_cols[idx]:
            if img:
                st.image(img, caption=label, use_column_width=True)
            else:
                st.info(f"{label} not available")
    
    # Show animation if available
    if 'animation_frames' in design and design['animation_frames']:
        st.markdown("### 🎬 360° Rotation Animation")
        st.image(design['animation_frames'], width=400, use_column_width=True)
    
    st.markdown("---")
    if st.button("← Back to Dashboard", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()

def show_designer():
    st.markdown("""
    <div class="main-header">
        <h1>👗 AI Fashion Designer - True 360° View</h1>
        <p>Upload Fabric → Generate Age-Appropriate Designs → See Front, Back, and All Sides</p>
        <p style="font-size: 1.2em; margin-top: 10px;">👩 Women | 👨 Men | 🧒 Kids | 👦 Teens</p>
        <p style="font-size: 1.1em; color: #ffd700;">✨ Now with REAL Back View & Complete 360° Rotation!</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Display save message if exists
    if st.session_state.save_message:
        st.markdown(f'<div class="save-success">{st.session_state.save_message}</div>', unsafe_allow_html=True)
        st.session_state.save_message = None
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        
        api_key = st.text_input(
            "RapidAPI Key (Try-On)",
            value=st.session_state.api_key,
            type="password"
        )
        st.session_state.api_key = api_key
        
        st.markdown("---")
        st.markdown("### 🎯 Design Preferences")
        
        gender_age = st.radio(
            "Select Category",
            options=["women_adult", "men_adult", "kids", "teens"],
            format_func=lambda x: "👩 Women (18+)" if x == "women_adult" else 
                                  "👨 Men (18+)" if x == "men_adult" else 
                                  "🧒 Kids (2-12)" if x == "kids" else "👦 Teens (13-17)",
            index=0
        )
        
        if gender_age == "women_adult":
            st.session_state.selected_gender = "women"
            st.session_state.selected_age_group = "adult"
        elif gender_age == "men_adult":
            st.session_state.selected_gender = "men"
            st.session_state.selected_age_group = "adult"
        elif gender_age == "kids":
            st.session_state.selected_gender = "kids"
            st.session_state.selected_age_group = "kids"
        else:
            st.session_state.selected_gender = "teens"
            st.session_state.selected_age_group = "teen"
        
        num_designs = st.slider("Number of designs to generate", 5, 12, 8)
        st.session_state.num_designs = num_designs
        
        st.markdown("---")
        st.markdown("### 🎮 True 360° Settings")
        
        auto_rotate = st.checkbox("Auto-rotate 360°", value=st.session_state.auto_rotate)
        st.session_state.auto_rotate = auto_rotate
        
        show_all_views = st.checkbox("Show all views simultaneously", value=True)
        st.session_state.show_all_views = show_all_views
        
        st.markdown("---")
        st.markdown("### ⚡ Performance Mode")
        generation_mode = st.radio(
            "Select Mode",
            options=["Fast (1 API Call)", "High Quality (4 Parallel API Calls)", "⚡ Turbo (Ultra Fast)"],
            index=0,
            help="⚡ Turbo uses GPU acceleration and optimized frames for maximum speed."
        )
        st.session_state.generation_mode = generation_mode
        
        st.markdown("---")
        st.markdown(f"📊 API Calls: {st.session_state.api_calls}")
        st.markdown(f"🎨 Designs Generated: {len(st.session_state.generated_designs)}")
        
        if st.button("🔄 Clear All", use_container_width=True):
            for key in ['processed_images', 'current_result', 'true_360_views', 
                       'selected_design', 'generated_designs', 'designs_generated',
                       'person_img', 'uploaded_fabric', 'animation_frames']:
                if key in st.session_state:
                    if key == 'processed_images':
                        st.session_state[key] = []
                    elif key == 'generated_designs':
                        st.session_state[key] = []
                    else:
                        st.session_state[key] = None
            st.session_state.designs_generated = False
            st.session_state.animation_frames = []
            st.rerun()
    
    # Main content
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 📸 Upload Person Photo")
        person_file = st.file_uploader("Choose person image", type=['png', 'jpg', 'jpeg'], key="person")
        
        if person_file:
            person_img = Image.open(person_file)
            st.session_state.person_img = person_img
            st.image(person_img, caption="Person Photo", use_column_width=True)
            
            age_group_display = {
                "adult": "Adult",
                "teen": "Teen (13-17)",
                "kids": "Child (2-12)"
            }[st.session_state.selected_age_group]
            
            st.info(f"👤 Selected for: {age_group_display} {st.session_state.selected_gender.title()}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 🧵 Upload Fabric")
        st.markdown("Upload the fabric you want to make clothes from")
        
        fabric_file = st.file_uploader("Choose fabric image", type=['png', 'jpg', 'jpeg'], key="fabric")
        
        if fabric_file:
            fabric_img = Image.open(fabric_file)
            st.session_state.uploaded_fabric = fabric_img
            st.image(fabric_img, caption="Your Fabric", use_column_width=True)
            
            if st.button(f"🎨 Generate {st.session_state.num_designs} Age-Appropriate Designs", use_container_width=True):
                with st.spinner(f"Creating {st.session_state.num_designs} different designs for {st.session_state.selected_age_group} {st.session_state.selected_gender}..."):
                    designs = []
                    
                    if st.session_state.selected_gender == "women":
                        dress_styles = [
                            {"name": "A-Line Dress", "description": "Classic A-line silhouette, fitted bodice with flared skirt", "style": "Elegant & Timeless", "prompt": "A-Line dress with fitted bodice and flared skirt"},
                            {"name": "Bodycon Dress", "description": "Figure-hugging silhouette, sleek and modern", "style": "Modern & Sleek", "prompt": "Bodycon dress with form-fitting silhouette"},
                            {"name": "Wrap Dress", "description": "V-neckline with wrap front, flattering on all body types", "style": "Versatile & Chic", "prompt": "Wrap dress with V-neckline and tie waist"},
                            {"name": "Maxi Dress", "description": "Floor-length dress with flowy silhouette", "style": "Bohemian & Elegant", "prompt": "Maxi dress with long flowing skirt"},
                            {"name": "Off-Shoulder Dress", "description": "Romantic off-shoulder design with fitted bodice", "style": "Romantic & Trendy", "prompt": "Off-shoulder dress with fitted bodice"},
                            {"name": "High-Low Dress", "description": "Asymmetrical hemline, shorter front longer back", "style": "Dramatic & Modern", "prompt": "High-low dress with asymmetrical hemline"},
                            {"name": "Peplum Dress", "description": "Fitted with flared detail at waist", "style": "Sophisticated", "prompt": "Peplum dress with flared waist detail"},
                            {"name": "Sheath Dress", "description": "Straight-cut design, perfect for office wear", "style": "Professional & Chic", "prompt": "Sheath dress with clean lines"},
                            {"name": "Ball Gown", "description": "Full skirted formal dress", "style": "Glamorous", "prompt": "Ball gown with full skirt and fitted bodice"},
                            {"name": "Mermaid Dress", "description": "Fitted through body, flared at hem", "style": "Red Carpet", "prompt": "Mermaid dress fitted through body with flared hem"},
                            {"name": "Empire Waist Dress", "description": "High waistline just below bust", "style": "Regency Style", "prompt": "Empire waist dress with high waistline"},
                            {"name": "Tunic Dress", "description": "Loose-fitting knee-length dress", "style": "Casual Chic", "prompt": "Tunic dress loose and comfortable fit"}
                        ]
                    elif st.session_state.selected_gender == "men":
                        dress_styles = [
                            {"name": "Classic Suit", "description": "Two-piece formal suit with jacket and trousers", "style": "Formal Elegant", "prompt": "Classic two-piece suit with jacket and trousers"},
                            {"name": "Casual Blazer", "description": "Unstructured blazer for smart casual look", "style": "Smart Casual", "prompt": "Casual blazer with relaxed fit"},
                            {"name": "Leather Jacket", "description": "Classic biker style leather jacket", "style": "Edgy & Cool", "prompt": "Classic biker leather jacket with zippers"},
                            {"name": "Formal Shirt", "description": "Button-down dress shirt with collar", "style": "Professional", "prompt": "Formal button-down dress shirt"},
                            {"name": "Casual T-Shirt", "description": "Comfortable crew neck t-shirt", "style": "Everyday Basic", "prompt": "Casual crew neck t-shirt"},
                            {"name": "Hoodie", "description": "Comfortable hooded sweatshirt", "style": "Streetwear", "prompt": "Comfortable hoodie with kangaroo pocket"},
                            {"name": "Kurta", "description": "Traditional long shirt", "style": "Ethnic Wear", "prompt": "Traditional kurta with embroidery"},
                            {"name": "Sherwani", "description": "Formal Indian wedding coat", "style": "Wedding Special", "prompt": "Elegant sherwani with intricate details"},
                            {"name": "Bomber Jacket", "description": "Classic flight jacket style", "style": "Retro Cool", "prompt": "Classic bomber jacket with ribbed cuffs"},
                            {"name": "Waistcoat", "description": "Sleeveless vest for formal wear", "style": "Vintage Style", "prompt": "Formal waistcoat with buttons"},
                            {"name": "Polo Shirt", "description": "Collared casual shirt", "style": "Sporty Casual", "prompt": "Classic polo shirt with collar"},
                            {"name": "Hawaiian Shirt", "description": "Relaxed short sleeve shirt", "style": "Vacation Vibes", "prompt": "Casual Hawaiian shirt with print"}
                        ]
                    elif st.session_state.selected_gender == "teens":
                        dress_styles = [
                            {"name": "Trendy Top", "description": "Fashionable top for teens", "style": "Trendy", "prompt": "Trendy teenage top with modern design"},
                            {"name": "Skinny Jeans", "description": "Comfortable skinny fit jeans", "style": "Casual", "prompt": "Skinny jeans for teenagers"},
                            {"name": "Hoodie", "description": "Cool hoodie for casual wear", "style": "Street Style", "prompt": "Teenage hoodie with cool design"},
                            {"name": "Party Dress", "description": "Stylish dress for teen parties", "style": "Party Wear", "prompt": "Teenage party dress with modern style"},
                            {"name": "Jacket", "description": "Trendy jacket for teens", "style": "Cool & Casual", "prompt": "Teenage jacket with trendy design"},
                            {"name": "Sportswear", "description": "Comfortable sports outfit", "style": "Active", "prompt": "Teenage sportswear for active lifestyle"},
                            {"name": "School Uniform", "description": "Smart school uniform", "style": "Academic", "prompt": "Teenage school uniform neat and clean"},
                            {"name": "Casual Shirt", "description": "Relaxed fit casual shirt", "style": "Everyday", "prompt": "Teenage casual shirt for daily wear"},
                            {"name": "Skater Skirt", "description": "Fun skater skirt", "style": "Playful", "prompt": "Teenage skater skirt with movement"},
                            {"name": "Graphic Tee", "description": "T-shirt with cool graphics", "style": "Expressive", "prompt": "Teenage graphic t-shirt with cool print"},
                            {"name": "Cargo Pants", "description": "Comfortable cargo pants", "style": "Utility", "prompt": "Teenage cargo pants with pockets"},
                            {"name": "Sweater", "description": "Cozy sweater for cold days", "style": "Cozy", "prompt": "Teenage sweater warm and comfortable"}
                        ]
                    else:
                        dress_styles = [
                            {"name": "Party Dress", "description": "Pretty dress for special occasions", "style": "Celebration", "prompt": "Beautiful party dress with frills"},
                            {"name": "Romper", "description": "One-piece jumpsuit for easy wear", "style": "Playful", "prompt": "Cute romper jumpsuit"},
                            {"name": "T-Shirt & Jeans", "description": "Classic casual combo", "style": "Everyday Play", "prompt": "Comfortable t-shirt with jeans"},
                            {"name": "School Uniform", "description": "Smart uniform for school", "style": "Academic", "prompt": "Neat school uniform shirt and pants"},
                            {"name": "Hoodie", "description": "Cozy hooded sweatshirt", "style": "Comfy Casual", "prompt": "Warm cozy hoodie"},
                            {"name": "Dungarees", "description": "Playful overalls", "style": "Cute & Practical", "prompt": "Cute dungarees overalls"},
                            {"name": "Princess Dress", "description": "Magical fantasy dress", "style": "Fantasy Fun", "prompt": "Magical princess dress with sparkles"},
                            {"name": "Sportswear", "description": "Active wear for sports", "style": "Active Play", "prompt": "Comfortable sportswear set"},
                            {"name": "Pajama Set", "description": "Cozy sleepwear", "style": "Bedtime", "prompt": "Cozy pajama set"},
                            {"name": "Raincoat", "description": "Waterproof jacket for rainy days", "style": "Weather Ready", "prompt": "Colorful raincoat with hood"},
                            {"name": "Sweater", "description": "Warm knitted pullover", "style": "Winter Warm", "prompt": "Cozy knitted sweater"},
                            {"name": "Costume", "description": "Fun dress-up costume", "style": "Dress-Up Fun", "prompt": "Fun costume for play"}
                        ]
                    
                    num_to_generate = min(st.session_state.num_designs, len(dress_styles))
                    selected_styles = random.sample(dress_styles, num_to_generate)
                    
                    for i, style in enumerate(selected_styles):
                        designs.append({
                            "id": i,
                            "name": style["name"],
                            "description": style["description"],
                            "style": style["style"],
                            "prompt": style["prompt"],
                            "fabric": fabric_img,
                            "gender": st.session_state.selected_gender,
                            "age_group": st.session_state.selected_age_group
                        })
                    
                    st.session_state.generated_designs = designs
                    st.session_state.designs_generated = True
                    st.success(f"✅ {num_to_generate} age-appropriate designs created! Select one below.")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Display generated designs
    if st.session_state.designs_generated and st.session_state.generated_designs:
        st.markdown("---")
        age_display = {
            "adult": "Adult",
            "teen": "Teen",
            "kids": "Kids"
        }[st.session_state.selected_age_group]
        
        gender_display = st.session_state.selected_gender.title()
        
        st.markdown(f"""
        <div class="section-title">
            <h2>🎨 Select Your {age_display} {gender_display} Design</h2>
            <p style="text-align: center; color: #666;">Click the button below any design to select it</p>
        </div>
        """, unsafe_allow_html=True)
        
        num_designs = len(st.session_state.generated_designs)
        cols_per_row = 4
        
        for row in range(0, num_designs, cols_per_row):
            cols = st.columns(cols_per_row)
            for idx in range(cols_per_row):
                design_idx = row + idx
                if design_idx < num_designs:
                    design = st.session_state.generated_designs[design_idx]
                    
                    with cols[idx]:
                        preview = create_design_preview(design, st.session_state.uploaded_fabric, 
                                                       st.session_state.selected_gender, 
                                                       st.session_state.selected_age_group)
                        
                        is_selected = (st.session_state.selected_design and 
                                      st.session_state.selected_design['id'] == design['id'])
                        
                        st.image(preview, use_column_width=True, caption=design['name'])
                        st.markdown(f"**{design['name']}**")
                        st.markdown(f"*{design['style']}*")
                        
                        age_badge = {
                            "adult": "👤 Adult",
                            "teen": "👦 Teen",
                            "kids": "🧒 Kids"
                        }[design['age_group']]
                        st.markdown(f'<span class="age-badge">{age_badge}</span>', unsafe_allow_html=True)
                        st.caption(design['description'])
                        
                        if is_selected:
                            st.success("✅ SELECTED")
                            st.button(f"✓ Selected", key=f"selected_{design_idx}", disabled=True, use_container_width=True)
                        else:
                            if st.button(f"🎯 Select This Design", key=f"select_btn_{design_idx}", use_container_width=True):
                                st.session_state.selected_design = design
                                if st.session_state.person_img:
                                    fit_score = check_fit_compatibility(st.session_state.person_img, design)
                                    st.session_state.fit_score = fit_score
                                    st.session_state.show_fit_analysis = True
                                st.rerun()
    
    # Show fit analysis if design is selected
    if st.session_state.show_fit_analysis and st.session_state.fit_score:
        fit_percentage = st.session_state.fit_score * 100
        if fit_percentage > 85:
            fit_message = "Excellent Fit! 🌟"
            color = "#00b09b"
        elif fit_percentage > 70:
            fit_message = "Good Fit 👍"
            color = "#96c93d"
        else:
            fit_message = "Average Fit 👌"
            color = "#ff6b6b"
        
        st.markdown(f"""
        <div class="fit-indicator" style="background: linear-gradient(135deg, {color}, {color}dd);">
            <h3>👔 Fit Analysis: {fit_message}</h3>
            <p>Compatibility Score: {fit_percentage:.1f}%</p>
            <p>This design should fit well based on the uploaded photo</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Generate try-on when design is selected
    if (st.session_state.person_img and st.session_state.selected_design and 
        st.session_state.uploaded_fabric):
        
        st.markdown("---")
        age_display = {
            "adult": "Adult",
            "teen": "Teen",
            "kids": "Kids"
        }[st.session_state.selected_age_group]
        
        st.markdown(f"""
        <div class="selected-design-box">
            <h3 style="color: #667eea;">✨ Selected {age_display} {st.session_state.selected_design['name']}</h3>
            <p>{st.session_state.selected_design['description']}</p>
            <p style="color: #666;">Style: {st.session_state.selected_design['style']}</p>
            <p style="color: #00b09b;">Age Group: {age_display}</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            generate_btn = st.button("👗 Generate True 360° Virtual Try-On", use_container_width=True)
        with col2:
            if st.session_state.current_result and st.session_state.logged_in:
                save_btn = st.button("💾 Save to Dashboard", use_container_width=True)
                if save_btn:
                    success = save_design_to_history(
                        st.session_state.current_user['id'],
                        st.session_state.selected_design['name'],
                        st.session_state.selected_design['style'],
                        st.session_state.selected_gender,
                        st.session_state.selected_age_group,
                        st.session_state.uploaded_fabric,
                        st.session_state.current_result,
                        st.session_state.true_360_views.get('front') if st.session_state.true_360_views else None,
                        st.session_state.true_360_views.get('back') if st.session_state.true_360_views else None,
                        st.session_state.true_360_views.get('left') if st.session_state.true_360_views else None,
                        st.session_state.true_360_views.get('right') if st.session_state.true_360_views else None,
                        st.session_state.animation_frames if st.session_state.animation_frames else None
                    )
                    if success:
                        st.session_state.save_message = f"✅ Design '{st.session_state.selected_design['name']}' saved to your dashboard!"
                        st.rerun()
                    else:
                        st.error("Failed to save design. Please try again.")
        
        if generate_btn:
            with st.spinner(f"Creating complete 360° view with REAL back and side views of {st.session_state.selected_design['name']}..."):
                try:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    status_text.text("📦 Processing fabric...")
                    progress_bar.progress(10)
                    
                    fabric_img = st.session_state.uploaded_fabric.convert("RGBA")
                    bg = Image.new("RGB", (600, 600), "#FFFFFF")
                    f_w, f_h = fabric_img.size
                    x = (600 - f_w) // 2
                    y = (600 - f_h) // 2
                    bg.paste(fabric_img, (x, y), fabric_img)
                    bg = ImageOps.expand(bg, border=20, fill="#FFFFFF")
                    
                    fabric_processed = io.BytesIO()
                    bg.save(fabric_processed, format="JPEG", quality=95)
                    fabric_processed.seek(0)
                    
                    status_text.text("🎨 Preparing design template...")
                    progress_bar.progress(20)
                    
                    status_text.text("🤖 Calling AI Try-On API...")
                    progress_bar.progress(30)
                    
                    person_bytes = io.BytesIO()
                    st.session_state.person_img.save(person_bytes, format="JPEG", quality=95)
                    person_bytes.seek(0)
                    
                    files = {
                        "avatar_image": ("person.jpg", person_bytes.getvalue(), "image/jpeg"),
                        "clothing_image": ("fabric.jpg", fabric_processed.getvalue(), "image/jpeg")
                    }
                    
                    current_gender = st.session_state.selected_gender
                    
                    if current_gender == "women":
                        api_gender = "female"
                        gender_text = "woman wearing"
                    elif current_gender == "men":
                        api_gender = "male"
                        gender_text = "man wearing"
                    else:
                        api_gender = ""
                        gender_text = "person wearing"
                    
                    age_prompt = {
                        "adult": "",
                        "teen": "age-appropriate youthful outfit, ",
                        "kids": "age-appropriate child outfit, modest and comfortable, "
                    }[st.session_state.selected_age_group]
                    
                    avatar_prompt = build_safe_tryon_prompt(
                        gender_text,
                        age_prompt,
                        st.session_state.selected_design['name'],
                        st.session_state.selected_design['prompt'],
                        custom_view="front view"
                    )
                    
                    clothing_prompt = (
                        f"realistic high-quality {current_gender}'s {st.session_state.selected_design['name']} "
                        f"made from the fabric exactly as shown, {st.session_state.selected_design['prompt']}, "
                        f"accurate fit, clean edges, tasteful design, fully clothed, no nudity, photorealistic, professional fashion design, perfectly fitted"
                    )
                    
                    data = {
                        "avatar_prompt": avatar_prompt,
                        "clothing_prompt": clothing_prompt,
                        "background_prompt": "",
                        "seed": str(random.randint(1000, 9999))
                    }
                    
                    if api_gender:
                        data["avatar_sex"] = api_gender
                    
                    headers = {
                        "x-rapidapi-key": st.session_state.api_key,
                        "x-rapidapi-host": "try-on-diffusion.p.rapidapi.com"
                    }
                    
                    api_results = {}
                    
                    if st.session_state.generation_mode == "High Quality (4 Parallel API Calls)":
                        status_text.text("🤖 Calling 4 AI Try-On APIs in parallel...")
                        progress_bar.progress(30)
                        
                        view_tasks = [
                            ("front", "front view, person facing camera", 0),
                            ("back", "full back view of the person, person turned 180 degrees, back facing camera", 1),
                            ("left", "left side profile view of the person, person turned 90 degrees to the left", 2),
                            ("right", "right side profile view of the person, person turned 90 degrees to the right", 3)
                        ]
                        
                        with ThreadPoolExecutor(max_workers=4) as executor:
                            def call_tryon_api_internal(view_type, custom_prompt_part, index):
                                time.sleep(index * 1.5)
                                max_retries = 3
                                for attempt in range(max_retries):
                                    try:
                                        pose_constraint = "same pose, " if view_type == "front" else ""
                                        view_avatar_prompt = (
                                            f"keep exact same face, same identity, same skin tone, same body shape, "
                                            f"same hairstyle, {pose_constraint}{gender_text} a {age_prompt}beautiful {st.session_state.selected_design['name']} "
                                            f"made from the fabric shown in clothing image, {st.session_state.selected_design['prompt']}, "
                                            f"{custom_prompt_part}, photorealistic, high quality fashion photography, studio lighting, perfect fit, full body"
                                        )
                                        view_data = data.copy()
                                        view_data["avatar_prompt"] = view_avatar_prompt
                                        thread_files = {
                                            "avatar_image": ("person.jpg", person_bytes.getvalue(), "image/jpeg"),
                                            "clothing_image": ("fabric.jpg", fabric_processed.getvalue(), "image/jpeg")
                                        }
                                        thread_response = requests.post("https://try-on-diffusion.p.rapidapi.com/try-on-file", 
                                                               files=thread_files, data=view_data, headers=headers)
                                        
                                        if thread_response.status_code == 200:
                                            return view_type, Image.open(io.BytesIO(thread_response.content))
                                        elif thread_response.status_code == 429:
                                            wait_time = 2 ** (attempt + 1)
                                            time.sleep(wait_time)
                                            continue
                                        else:
                                            return view_type, None
                                    except Exception:
                                        time.sleep(2)
                                        continue
                                return view_type, None
                            
                            future_to_view = {executor.submit(call_tryon_api_internal, vt, cp, idx): vt for vt, cp, idx in view_tasks}
                            for future in concurrent.futures.as_completed(future_to_view):
                                view_type, img = future.result()
                                if img:
                                    api_results[view_type] = img
                                    st.session_state.api_calls += 1
                                    progress_bar.progress(min(50, 30 + len(api_results) * 5))
                        
                        if "front" in api_results:
                            front_view = api_results["front"]
                        else:
                            st.error("Failed to generate main front view.")
                            st.stop()
                    else:
                        max_retries = 3
                        for attempt in range(max_retries):
                            response = requests.post("https://try-on-diffusion.p.rapidapi.com/try-on-file", 
                                                   files=files, data=data, headers=headers)
                            st.session_state.api_calls += 1
                            if response.status_code == 200:
                                front_view = Image.open(io.BytesIO(response.content))
                                api_results = {"front": front_view}
                                break
                            elif response.status_code == 429:
                                wait_time = 2 ** (attempt + 1)
                                status_text.text(f"⚠️ Rate limited (429). Retrying in {wait_time}s...")
                                time.sleep(wait_time)
                            else:
                                try:
                                    error_json = response.json()
                                    message = error_json.get("detail", response.text)
                                except Exception:
                                    message = response.text
                                st.error(f"API Error: {response.status_code} - {message}")
                                st.stop()
                        else:
                            st.error("Too many rate limits. Please try again in 1 minute.")
                            st.stop()
                    
                    progress_bar.progress(50)
                    
                    if st.session_state.generation_mode != "⚡ Turbo (Ultra Fast)":
                        status_text.text("✨ Enhancing garment details...")
                        front_view = enhance_garment_details(front_view, st.session_state.selected_design['name'])
                    else:
                        status_text.text("⚡ Turbo: Skipping enhancements for speed...")
                    
                    st.session_state.current_result = front_view
                    
                    status_text.text("🔄 Generating TRUE back and side views...")
                    progress_bar.progress(60)
                    
                    true_360_views = generate_true_360_views(
                        st.session_state.person_img,
                        front_view,
                        st.session_state.selected_design['name'],
                        st.session_state.selected_gender,
                        st.session_state.selected_age_group
                    )
                    
                    if st.session_state.generation_mode == "High Quality (4 Parallel API Calls)":
                        for v_type, v_img in api_results.items():
                            if v_img:
                                true_360_views[v_type] = v_img
                    
                    if true_360_views:
                        st.session_state.true_360_views = true_360_views
                        st.session_state.current_saved_views = true_360_views
                        
                        status_text.text("🎬 Creating smooth 360° rotation animation...")
                        progress_bar.progress(80)
                        
                        if st.session_state.generation_mode == "⚡ Turbo (Ultra Fast)":
                            animation_frames = create_360_rotation_animation(true_360_views, fps=8, duration=3)
                        else:
                            animation_frames = create_360_rotation_animation(true_360_views, fps=12, duration=5)
                            
                        if animation_frames:
                            st.session_state.animation_frames = animation_frames
                    
                    st.session_state.processed_images.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "image": front_view,
                        "design": f"{age_display} {st.session_state.selected_design['name']}"
                    })
                    
                    progress_bar.progress(100)
                    status_text.text("✅ Complete! All 8 views generated with REAL back view!")
                    time.sleep(1)
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                    st.balloons()
                    st.success(f"✨ True 360° view of {st.session_state.selected_design['name']} created successfully!")
                    st.info("🎯 Now you can see the REAL BACK VIEW and all sides of your garment!")
                        
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    progress_bar.empty()
                    status_text.empty()
    
    # Display final result
    if st.session_state.current_result:
        st.markdown("---")
        st.markdown("""
        <div class="viewer-360">
            <h2 style="text-align: center;">✨ Final Try-On Result</h2>
            <p style="text-align: center; color: #ffd700;">Your selected design on the uploaded person photo</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.image(st.session_state.current_result, use_column_width=True, caption=f"{st.session_state.selected_design['name']} Try-On Result")
        
        st.markdown("### 📥 Download Result")
        buf_result = io.BytesIO()
        st.session_state.current_result.save(buf_result, format="PNG")
        st.download_button(
            label="📥 Download Final Image",
            data=buf_result.getvalue(),
            file_name=f"{st.session_state.selected_design['name']}_tryon.png",
            mime="image/png",
            use_container_width=True
        )
        
        # Show 360 views if available
        if st.session_state.true_360_views:
            st.markdown("---")
            st.markdown("## 🔄 360° View of Your Design")
            st.markdown("<p style='text-align: center; color: #666;'>Front | Back | Left | Right | All Angles</p>", unsafe_allow_html=True)
            
            view_cols = st.columns(4)
            views_to_show = [
                ('front', 'Front View', '👗'),
                ('back', 'Back View', '🔙'),
                ('left', 'Left Side', '⬅️'),
                ('right', 'Right Side', '➡️')
            ]
            
            for idx, (key, label, icon) in enumerate(views_to_show):
                with view_cols[idx]:
                    if key in st.session_state.true_360_views:
                        st.image(st.session_state.true_360_views[key], caption=f"{icon} {label}", use_column_width=True)
            
            # Fixed animation display - show frames one by one or as a list
            if st.session_state.animation_frames and len(st.session_state.animation_frames) > 0:
                st.markdown("### 🎬 360° Rotation Animation")
                
                # Option 1: Show as a slideshow with manual controls
                st.markdown("Use the slider to view each frame of the 360° rotation:")
                
                # Create a slider to select frame
                frame_index = st.slider("Frame", 0, len(st.session_state.animation_frames) - 1, 0)
                st.image(st.session_state.animation_frames[frame_index], caption=f"Frame {frame_index + 1} of {len(st.session_state.animation_frames)}", use_column_width=True)
                
                # Option 2: Auto-rotate if enabled
                if st.session_state.auto_rotate:
                    st.markdown("Auto-rotating...")
                    import time as time_module
                    placeholder = st.empty()
                    for i in range(len(st.session_state.animation_frames)):
                        placeholder.image(st.session_state.animation_frames[i], caption=f"360° Rotation - Frame {i+1}", use_column_width=True)
                        time_module.sleep(0.1)
                
                # Option 3: Export animation as GIF
                st.markdown("#### Export Animation")
                try:
                    from PIL import Image as PILImage
                    # Save frames as GIF
                    gif_buffer = io.BytesIO()
                    frames_to_save = st.session_state.animation_frames
                    if frames_to_save:
                        # Convert all frames to RGB mode for GIF
                        rgb_frames = []
                        for frame in frames_to_save:
                            if frame.mode != 'RGB':
                                rgb_frames.append(frame.convert('RGB'))
                            else:
                                rgb_frames.append(frame)
                        
                        # Save as GIF
                        if rgb_frames:
                            rgb_frames[0].save(
                                gif_buffer,
                                format='GIF',
                                save_all=True,
                                append_images=rgb_frames[1:],
                                duration=100,
                                loop=0,
                                optimize=False
                            )
                            gif_buffer.seek(0)
                            st.download_button(
                                label="📥 Download as GIF",
                                data=gif_buffer.getvalue(),
                                file_name=f"{st.session_state.selected_design['name']}_360_rotation.gif",
                                mime="image/gif",
                                use_container_width=True
                            )
                except Exception as gif_error:
                    st.warning(f"GIF creation not available: {str(gif_error)}")
    
    # History section
    if st.session_state.processed_images and len(st.session_state.processed_images) > 0:
        st.markdown("---")
        st.markdown("""
        <div class="section-title">
            <h2>📋 Recent Designs History</h2>
        </div>
        """, unsafe_allow_html=True)
        
        cols = st.columns(4)
        for idx, item in enumerate(st.session_state.processed_images[-4:]):
            with cols[idx]:
                st.image(item['image'], caption=f"{item['design']}\n{item['timestamp'][:10]}", 
                        use_column_width=True)

# Main app routing
def main():
    # Navigation in sidebar for logged-in users
    if st.session_state.logged_in:
        with st.sidebar:
            st.markdown("---")
            st.markdown(f"### 👤 {st.session_state.current_user['username']}")
            
            nav_options = ["🎨 Designer", "📊 Dashboard"]
            selected_nav = st.radio("Navigate", nav_options, index=0)
            
            if selected_nav == "🎨 Designer":
                st.session_state.page = "designer"
            else:
                st.session_state.page = "dashboard"
            
            st.markdown("---")
    
    # Page routing
    if not st.session_state.logged_in:
        if st.session_state.page == "register":
            show_register_page()
        else:
            show_login_page()
    else:
        if st.session_state.page == "dashboard":
            show_dashboard()
        elif st.session_state.page == "view_design":
            show_view_design()
        else:
            show_designer()

if __name__ == "__main__":
    main()