import cv2
import numpy as np
from scipy.spatial import distance

def filter_nearby_centroids(centroids, min_distance):
    if not centroids: return []
    sorted_centroids = sorted(centroids, key=lambda c: c[0])
    filtered_centroids = []
    for c_new in sorted_centroids:
        is_too_close = False
        for c_filtered in filtered_centroids:
            if distance.euclidean(c_new, c_filtered) < min_distance:
                is_too_close = True; break
        if not is_too_close: filtered_centroids.append(c_new)
    return filtered_centroids

def count_fireflies_still(video_path: str) -> int:
    
    cap = cv2.VideoCapture(video_path) 
    if not cap.isOpened():
        return 0 # เปิดไฟล์ไม่ได้ คืนค่า 0

    # --------------------- PART 1: สร้าง Mask ---------------------
    CALIBRATION_FRAMES = 30
    bg_buffer = []

    for i in range(CALIBRATION_FRAMES):
        ret, frame = cap.read()
        if not ret: break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        bg_buffer.append(gray)

    if len(bg_buffer) == 0: 
        cap.release()
        return 0

    avg_bg = np.mean(bg_buffer, axis=0).astype(np.uint8)
    SKY_THRESHOLD = 30 
    _, sky_mask = cv2.threshold(avg_bg, SKY_THRESHOLD, 255, cv2.THRESH_BINARY)

    kernel_edge = np.ones((15, 15), np.uint8) 
    sky_and_edge_mask = cv2.dilate(sky_mask, kernel_edge, iterations=3) 
    working_area_mask = cv2.bitwise_not(sky_and_edge_mask)

    # --------------------- PART 2: Detection Loop ---------------------
    firefly_id = 0
    fireflies = {} 

    MIN_BRIGHTNESS = 40     
    MAX_BRIGHTNESS = 255
    MIN_AREA = 0.5
    MAX_AREA = 40
    TRACKING_DISTANCE = 50  
    MAX_MISSED_FRAMES = 999999 

    while True:
        ret, frame = cap.read()
        if not ret: break # จบวิดีโอ ให้ออกจากลูป

        masked_frame = cv2.bitwise_and(frame, frame, mask=working_area_mask)
        gray = cv2.cvtColor(masked_frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        mask = cv2.inRange(blurred, MIN_BRIGHTNESS, MAX_BRIGHTNESS)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        raw_centroids = []
        for c in contours:
            area = cv2.contourArea(c)
            if MIN_AREA < area < MAX_AREA:
                x, y, w, h = cv2.boundingRect(c)
                raw_centroids.append((int(x + w/2), int(y + h/2)))
        
        current_centroids = filter_nearby_centroids(raw_centroids, 10)

        updated_this_frame = {}
        for c in current_centroids:
            matched_id = None
            min_dist = TRACKING_DISTANCE
            
            for fid, info in fireflies.items():
                dist = distance.euclidean(c, info['centroid'])
                if dist < min_dist:
                    matched_id = fid
                    min_dist = dist
            
            if matched_id is not None:
                info = fireflies[matched_id]
                info['lifespan'] += 1 
                updated_this_frame[matched_id] = {'centroid': c, 'missed': 0, 'lifespan': info['lifespan']}
            else:
                firefly_id += 1 
                updated_this_frame[firefly_id] = {'centroid': c, 'missed': 0, 'lifespan': 1}

        final_dict = updated_this_frame.copy()
        for fid, info in fireflies.items():
            if fid not in updated_this_frame:
                info['missed'] += 1
                if info['missed'] <= MAX_MISSED_FRAMES:
                    final_dict[fid] = info
        
        fireflies = final_dict

    cap.release()
    
    # ส่งคืนตัวเลขจำนวนหิ่งห้อยทั้งหมด (Total Unique)
    return firefly_id

# =========================================================
# โค้ดส่วนวิเคราะห์แบบ Pan (เพิ่มเข้ามาใหม่)
# =========================================================

# Detection Params
MIN_BRIGHTNESS_PAN = 30      
MIN_AREA_PAN = 0.2              
MAX_AREA_PAN = 80           
TRACKING_DIST_PAN = 60       
MISSED_THRESHOLD_PAN = 60    
TARGET_WIDTH_PAN = 800       

# Optical Flow Params
FLOW_SCALE = 0.5         
FLOW_MIN_MAG = 0.5       

def get_centroids_pan(frame, scale_ratio):
   
    h, w = frame.shape[:2]
    new_h = int(h * scale_ratio)
    frame_res = cv2.resize(frame, (TARGET_WIDTH_PAN, new_h))
    
    gray = cv2.cvtColor(frame_res, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    mask = cv2.inRange(blurred, MIN_BRIGHTNESS_PAN, 255)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    cents = []
    for c in contours:
        area = cv2.contourArea(c)
        if MIN_AREA_PAN < area < MAX_AREA_PAN:
            x, y, w_b, h_b = cv2.boundingRect(c)
            cx, cy = x + w_b/2, y + h_b/2
            cents.append((cx, cy))
    return cents, frame_res, gray

def calculate_global_flow(prev_gray, curr_gray):
    
    h, w = prev_gray.shape
    small_h, small_w = int(h * FLOW_SCALE), int(w * FLOW_SCALE)
    
    prev_small = cv2.resize(prev_gray, (small_w, small_h))
    curr_small = cv2.resize(curr_gray, (small_w, small_h))

    flow = cv2.calcOpticalFlowFarneback(prev_small, curr_small, None, 
                                        0.5, 3, 15, 3, 5, 1.2, 0)
    
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    valid_mask = mag > FLOW_MIN_MAG
    
    if np.count_nonzero(valid_mask) > 0:
        dx = np.median(flow[..., 0][valid_mask])
        dy = np.median(flow[..., 1][valid_mask])
    else:
        dx, dy = 0.0, 0.0
        
    return dx / FLOW_SCALE, dy / FLOW_SCALE

def count_fireflies_pan(video_path: str) -> int:
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): 
        return 0
    
    ret, frame = cap.read()
    if not ret: 
        cap.release()
        return 0
    
    h_orig, w_orig = frame.shape[:2]
    scale_ratio = TARGET_WIDTH_PAN / w_orig
    new_h = int(h_orig * scale_ratio)
    
    _, _, prev_gray = get_centroids_pan(frame, scale_ratio)
    
    firefly_id = 0
    fireflies = {} 
    
    while True:
        ret, frame = cap.read()
        if not ret: break 
        
        # 1. Detection
        curr_cents, frame_res, curr_gray = get_centroids_pan(frame, scale_ratio)
        
        # 2. Optical Flow
        shift_x, shift_y = calculate_global_flow(prev_gray, curr_gray)
        
        # 3. Prediction
        for fid in fireflies:
            old_x, old_y = fireflies[fid]['centroid']
            pred_x = old_x + shift_x
            pred_y = old_y + shift_y
            fireflies[fid]['centroid'] = (pred_x, pred_y)

        # 4. Matching
        updated_ids = set()
        used_cents = set()
        
        for fid, info in fireflies.items():
            pred_pt = info['centroid']
            best_idx = -1
            min_dist = TRACKING_DIST_PAN
            
            for i, c in enumerate(curr_cents):
                if i in used_cents: continue
                d = distance.euclidean(pred_pt, c)
                if d < min_dist:
                    min_dist = d
                    best_idx = i
            
            if best_idx != -1:
                fireflies[fid]['centroid'] = curr_cents[best_idx]
                fireflies[fid]['missed'] = 0
                updated_ids.add(fid)
                used_cents.add(best_idx)

        # 5. New Detection
        for i, c in enumerate(curr_cents):
            if i not in used_cents:
                firefly_id += 1
                fireflies[firefly_id] = {'centroid': c, 'missed': 0}
                updated_ids.add(firefly_id)

        # 6. Cleanup
        cleanup_list = []
        for fid in list(fireflies.keys()):
            if fid not in updated_ids:
                fireflies[fid]['missed'] += 1
            
            cx, cy = fireflies[fid]['centroid']
            is_out_of_bounds = not (0 <= cx <= TARGET_WIDTH_PAN and 0 <= cy <= new_h)
            
            if fireflies[fid]['missed'] > MISSED_THRESHOLD_PAN or is_out_of_bounds:
                cleanup_list.append(fid)
        
        for fid in cleanup_list:
            del fireflies[fid]

        prev_gray = curr_gray.copy()

    cap.release()
    return firefly_id 