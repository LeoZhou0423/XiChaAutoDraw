import cv2
import numpy as np
import pyautogui
import time
import os
import sys
import tempfile
import json
from pynput import keyboard
import argparse
from skimage.morphology import skeletonize

# 获取应用程序路径
base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS

# 获取系统AppData路径用于存储配置文件
app_data_path = os.getenv('APPDATA')
if app_data_path:
    config_path = os.path.join(app_data_path, 'XiChaDrawingTool')
else:
    # 如果AppData不可用，回退到当前目录
    config_path = os.path.join(base_path, 'config')

# 创建配置目录（如果不存在）
os.makedirs(config_path, exist_ok=True)

# 创建输出目录（如果不存在）
output_path = os.path.join(config_path, 'output')
os.makedirs(output_path, exist_ok=True)

# 全局变量控制退出
should_exit = False

# 全局变量控制绘制暂停/继续
is_paused = False

# 改进的键盘监听函数，确保ESC键和空格键被正确捕获
def on_press(key):
    global should_exit, is_paused
    try:
        # 捕获ESC键 - 退出程序
        if key == keyboard.Key.esc:
            print("\n🔴 检测到ESC键！正在停止绘制...")
            should_exit = True
            # 立即抬起鼠标按键，确保停止所有绘制操作
            pyautogui.mouseUp()
            return False  # 停止监听器
        # 捕获空格键 - 暂停/继续绘制
        elif key == keyboard.Key.space:
            is_paused = not is_paused
            if is_paused:
                print("\n⏸️  绘制已暂停！按空格键继续...")
                # 暂停时立即抬起鼠标，防止拖动产生线条
                pyautogui.mouseUp()
            else:
                print("\n▶️  绘制继续进行...")
    except Exception as e:
        # 打印异常以调试
        print(f"键盘事件处理异常: {e}")
        pass

# 额外的安全中断机制 - 定期检查should_exit标志
def check_exit_condition():
    """检查是否应该退出程序"""
    return should_exit

def extend_short_path(path, threshold=7, target_length=6):
    """
    扩展过短的路径使其满足绘制条件
    threshold: 判断是否需要延长的阈值（max(x)-min(x)或max(y)-min(y)的最小值）
    target_length: 延长后的目标长度（max(x)-min(x)或max(y)-min(y)需要达到的值）
    优先沿原路径方向延长，保持视觉自然性
    """
    if not path or len(path) < 2:
        return path  # 无效路径直接返回
    
    # 计算原始路径的边界
    xs = [p[0] for p in path]
    ys = [p[1] for p in path]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    
    # 如果已经满足条件，直接返回
    if width >= threshold or height >= threshold:
        return path
    
    # 计算路径的主方向（从起点到终点）
    start = path[0]
    end = path[-1]
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    
    # 计算当前路径长度
    current_length = (dx**2 + dy**2)**0.5
    
    # 计算单位方向向量（避免除以零）
    if current_length < 0.001:
       exit("路径长度为0，无法计算方向向量")
    else:
        ux = dx / current_length
        uy = dy / current_length
    
    # 计算原始宽高比
    aspect_ratio = width / height if height > 0 else 1.0
    
    # 计算需要达到的最小宽度或高度
    # 我们需要延长直到width或height达到min_length
    # 基于原路径方向，计算需要延长的总长度
    # 延长后的宽高将是原宽高 + 延长部分在x/y轴上的投影
    
    # 计算当前宽高与目标的差距
    width_gap = max(0, target_length - width)
    height_gap = max(0, target_length - height)
    
    # 根据原路径方向，计算需要延长的总长度
    # 延长部分在x轴的投影：extension * |ux|
    # 延长部分在y轴的投影：extension * |uy|
    # 我们需要延长直到投影部分加上原宽高达到min_length
    
    # 计算需要的延长长度（单边延长）
    extension = 0
    if abs(ux) > 0.01:  # 路径有x方向分量
        required_x_extension = width_gap / abs(ux)
        extension = max(extension, required_x_extension)
    if abs(uy) > 0.01:  # 路径有y方向分量
        required_y_extension = height_gap / abs(uy)
        extension = max(extension, required_y_extension)
    
    # 确保延长长度至少为1px
    extension = max(extension, 1.0)
    
    # 两端分别延长
    extended_start = (
        int(start[0] - ux * extension),
        int(start[1] - uy * extension)
    )
    extended_end = (
        int(end[0] + ux * extension),
        int(end[1] + uy * extension)
    )
    
    # 构建新路径
    new_path = [extended_start] + path[1:-1] + [extended_end]
    
    # 计算延长后的宽高
    new_xs = [p[0] for p in new_path]
    new_ys = [p[1] for p in new_path]
    new_width = max(new_xs) - min(new_xs)
    new_height = max(new_ys) - min(new_ys)
    
    # 计算扩展方向（用角度表示）
    direction_angle = np.arctan2(dy, dx) * 180 / np.pi
    
    # 输出短路径信息
    print(f"[短路径处理] 起点={start}, 终点={end}, 当前宽={width:.1f}px, 当前高={height:.1f}px, 延长长度={extension:.2f}px/端, 方向={direction_angle:.1f}°, 延长后宽={new_width:.1f}px, 延长后高={new_height:.1f}px")
    
    return new_path

def get_line_width(contour):
    """
    估算轮廓的平均宽度（像素）
    方法：使用最小外接矩形的宽高比 + 面积估算
    添加了合理的最大宽度限制，避免异常大的值
    """
    if len(contour) < 3:
        return 1
    
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    
    # 对于大型轮廓（可能是背景），限制最大宽度
    # 如果是大面积轮廓，周长较小，很可能是填充区域而非线条
    if area > 10000:  # 面积过大的轮廓
        return min(20, int(max(1, 2 * area / perimeter)))
    
    # 最小外接矩形
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    box = np.int32(box)
    
    # 计算长边和短边
    points = np.array(box)
    distances = []
    for i in range(4):
        d = np.linalg.norm(points[i] - points[(i+1)%4])
        distances.append(d)
    widths = sorted(distances)
    width = min(widths[0], widths[1])  # 较短边作为宽度估计
    
    # 如果是曲线，用面积 / 长度 估算宽度
    if perimeter > 0:
        estimated_width = 2 * area / perimeter
        width = max(width, estimated_width)
    
    # 设置最大宽度限制，避免异常值
    max_reasonable_width = 50  # 最大合理宽度，根据实际需要调整
    return int(max(1, min(width, max_reasonable_width)))


def detect_brush_size_slider(canvas_top_left, canvas_size):
    """
    检测画笔大小滑块上的5个圆点位置
    返回: [(x1, y1), (x2, y2), ..., (x5, y5)] 坐标列表
    """
    # 定义滑块区域相对于画布的位置
    # 假设滑块位于画布上方，距离画布顶部有一定距离
    slider_region_height = 100  # 滑块区域高度
    slider_region_y = canvas_top_left[1] - slider_region_height  # 滑块区域Y坐标
    
    # 确保Y坐标不为负
    slider_region_y = max(0, slider_region_y)
    
    # 截取滑块区域
    try:
        # 滑块区域宽度与画布相同，高度为设定值
        slider_screenshot = pyautogui.screenshot(region=(
            canvas_top_left[0], 
            slider_region_y, 
            canvas_size[0], 
            slider_region_height
        ))
        
        # 转换为OpenCV格式
        img = cv2.cvtColor(np.array(slider_screenshot), cv2.COLOR_RGB2BGR)
        
        # 转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 高斯模糊降噪
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 二值化，突出圆点
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # 查找轮廓
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 筛选圆形轮廓
        circle_points = []
        for contour in contours:
            # 计算轮廓面积
            area = cv2.contourArea(contour)
            
            # 计算轮廓周长
            perimeter = cv2.arcLength(contour, True)
            
            # 跳过面积过小的轮廓
            if area < 10:
                continue
            
            # 计算圆形度（圆形度接近1表示越圆）
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                
                # 如果轮廓接近圆形且面积适中
                if 0.5 < circularity < 1.5 and 10 < area < 100:
                    # 获取轮廓中心
                    M = cv2.moments(contour)
                    if M["m00"] > 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        # 转换为屏幕坐标
                        screen_x = canvas_top_left[0] + cx
                        screen_y = slider_region_y + cy
                        circle_points.append((screen_x, screen_y))
        
        # 如果找到的点不足5个，使用备用方法
        if len(circle_points) < 5:
            print(f"警告：只找到 {len(circle_points)} 个圆点，使用备用方法")
            # 备用方法：假设滑块在画布上方居中位置，手动计算5个点的位置
            slider_center_x = canvas_top_left[0] + canvas_size[0] // 2
            slider_center_y = slider_region_y + slider_region_height // 2
            slider_length = canvas_size[0] * 0.8  # 滑块长度为画布宽度的80%
            
            circle_points = []
            for i in range(5):
                # 等间距分布5个点
                x = int(slider_center_x - slider_length // 2 + (slider_length / 4) * i)
                y = slider_center_y
                circle_points.append((x, y))
        else:
            # 按X坐标排序，确保从左到右顺序
            circle_points.sort(key=lambda p: p[0])
            # 只保留最左边的5个点
            circle_points = circle_points[:5]
        
        # 保存检测到的滑块位置
        with open('brush_slider_positions.txt', 'w') as f:
            for point in circle_points:
                f.write(f"{point[0]},{point[1]}\n")
        
        print(f"已检测并保存 {len(circle_points)} 个滑块圆点位置到 brush_slider_positions.txt")
        return circle_points
        
    except Exception as e:
        print(f"检测滑块位置时出错: {e}")
        # 返回默认位置
        default_positions = [(100, 100), (200, 100), (300, 100), (400, 100), (500, 100)]
        return default_positions

def load_brush_slider_positions():
    """
    从内置数据加载画笔滑块位置
    直接嵌入captured_coordinates.json的内容，避免文件读取错误
    """
    try:
        # 直接嵌入captured_coordinates.json的坐标数据
        positions = [
            (1453, 967),  # 画笔档位1
            (1539, 966),  # 画笔档位2
            (1624, 966),  # 画笔档位3
            (1702, 966),  # 画笔档位4
            (1785, 966)   # 画笔档位5
        ]
        
        print(f"✅ 已加载{len(positions)}个画笔档位位置")
        return positions
    except Exception as e:
        print(f"❌ 加载画笔滑块位置失败: {str(e)}")
        return None

def save_brush_slider_positions(positions):
    """
    保存画笔滑块位置到文件
    positions: [(x1, y1), (x2, y2), ..., (x5, y5)] 坐标列表
    """
    try:
        config_file = os.path.join(config_path, 'brush_slider_positions.txt')
        with open(config_file, 'w') as f:
            for point in positions:
                f.write(f"{point[0]},{point[1]}\n")
        print(f"✅ 已保存 {len(positions)} 个滑块位置到 {config_file}")
        return True
    except Exception as e:
        print(f"❌ 保存滑块位置时出错: {e}")
        return False

def map_width_to_brush_size(width):
    if width <= 8:
        return 1
    elif width <= 20:
        return 2
    else:
        return 3

def filter_short_paths(paths, min_points=3):
    """过滤点数太少的路径（通常是噪点）"""
    filtered = []
    for path in paths:
        if len(path) >= min_points:
            filtered.append(path)
        else:
            print(f"[过滤] 路径过短 ({len(path)} 点)，已丢弃: {path[:3]}...")
    return filtered

def extract_skeleton_paths(binary_img):
    """
    从二值图像中提取骨架路径（中心线），适用于实心笔画绘制
    返回: [(path1), (path2), ...] 每个 path 是 [(x,y), ...]
    """
    # 确保输入是二值图（0 和 255），转为 0/1
    bw = (binary_img > 0).astype(np.uint8)

    # 骨架化（细化）
    skeleton = skeletonize(bw).astype(np.uint8) * 255

    # 查找骨架中的连通路径（使用 RETR_LIST + CHAIN_APPROX_NONE）
    contours, _ = cv2.findContours(skeleton, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    paths = []
    for contour in contours:
        if len(contour) < 2:
            continue
        path = [(int(pt[0][0]), int(pt[0][1])) for pt in contour]
        # 去除闭合环的重复终点（骨架通常是开曲线）
        if len(path) > 2 and path[0] == path[-1]:
            path = path[:-1]
        
        # 过滤极小的路径：max(x)-min(x)<1 and max(y)-min(y)<1
        if len(path) > 0:
            x_coords = [pt[0] for pt in path]
            y_coords = [pt[1] for pt in path]
            if ((max(x_coords) - min(x_coords) <= 3) and (max(y_coords) - min(y_coords) <= 3) or (max(x_coords) - min(x_coords) <= 1) or (max(y_coords) - min(y_coords) <= 1)):
                continue
                
        paths.append(path)

    # 过滤短路径
    paths = filter_short_paths(paths, min_points=1)  # 至少6个点才保留

    # 可选：按起始点排序
    paths.sort(key=lambda p: (p[0][1], p[0][0]))
    return paths, skeleton

def switch_brush_to_size(size_index, slider_positions):
    """
    模拟点击画笔大小滑块上的指定档位
    size_index: 档位索引 (1~5)
    slider_positions: 滑块上5个点的坐标列表
    """
    if not slider_positions or len(slider_positions) < 5:
        print("错误：滑块位置信息不完整")
        return False
    
    # 确保索引在有效范围内
    index = max(0, min(size_index - 1, 4))
    target_x, target_y = slider_positions[index]
    
    try:
        # 输出正在切换画笔的提示
        print(f"正在切换画笔到大小档位 {size_index}")
        # 移动到目标位置并点击
        pyautogui.moveTo(target_x, target_y, duration=0.1)
        pyautogui.click()
        time.sleep(0.2)  # 等待系统响应
        print(f"已切换到画笔大小档位 {size_index}")
        return True
    except Exception as e:
        print(f"切换画笔大小时出错: {e}")
        return False

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.001  # 极小延迟，提升绘制速度

import json

def load_captured_coordinates():
    """从captured_coordinates.json加载捕获的坐标点"""
    config_file = os.path.join(config_path, 'captured_coordinates.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'coordinates' in data:
                print(f"✅ 已从{config_file}加载{len(data['coordinates'])}个坐标点")
                # 返回绝对坐标点列表
                return [(coord['absolute']['x'], coord['absolute']['y']) for coord in data['coordinates']]
        except Exception as e:
            print(f"从{config_file}加载坐标时出错: {e}")
    return []

def load_canvas_coordinates():
    """从文件加载画布坐标"""
    config_file = os.path.join(config_path, 'canvas_coordinates.txt')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                top_left = eval(lines[0].split(': ')[1])
                size_str = lines[1].split(': ')[1]
                width, height = map(int, size_str.split(' x '))
                bottom_right = eval(lines[2].split(': ')[1])
                print(f"✅ 已从{config_file}加载画布坐标")
                return top_left, (width, height), bottom_right
        except Exception as e:
            print(f"从{config_file}加载坐标时出错: {e}")
    
    print(f"❌ 未找到有效的画布坐标文件: {config_file}")
    return None, None, None

def extract_strict_strokes(image_path):
    """
    从图像中提取骨架路径（中心线）和宽度信息，将整个白色区域视为线条
    流程：先处理原始图像得到processed_binary.png，再对其白色部分进行骨架化
    """
    # 第一步：处理原始图像，生成processed_binary.png（保持原有处理逻辑）
    # 使用numpy fromfile解决中文路径问题
    try:
        img_data = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
        if img is None:
            print(f"❌ 无法读取图像: {image_path}")
            return [], None, []
    except Exception as e:
        print(f"❌ 读取图像时发生错误: {image_path}, 错误信息: {e}")
        return [], None, []
    
    # 转为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 使用OTSU阈值自动确定最佳阈值
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 更强的开运算（去除小噪点）
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)
    
    # 再做一次闭运算（连接断裂但重要的线条）
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)
    
    # 设置面积阈值，过滤掉特别小的细节部分
    min_area_threshold = 3  # 像素面积阈值
    
    # 使用更强的形态学开运算过滤小区域（先腐蚀后膨胀）
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    filtered_binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    
    # 计算过滤掉的像素数量
    total_white_pixels = cv2.countNonZero(binary)
    filtered_white_pixels = cv2.countNonZero(filtered_binary)
    small_contours_count = total_white_pixels - filtered_white_pixels
    
    # 打印过滤信息
    print(f"已过滤 {small_contours_count} 个过小的细节轮廓（面积小于{min_area_threshold}像素）")
    
    # 保存processed_binary.png（这是处理后的二值图像）到临时目录
    try:
        # 使用临时目录存储处理后的文件
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
        
        success, encoded_img = cv2.imencode('.png', filtered_binary)
        if success:
            encoded_img.tofile(temp_path)
            print(f"✅ 已生成 processed_binary.png")
        else:
            print(f"❌ 保存 processed_binary.png 失败")
            os.unlink(temp_path)
            return [], None, []
    except Exception as e:
        print(f"❌ 保存 processed_binary.png 时发生错误: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        return [], None, []
    
    # 第二步：读取processed_binary.png，并对其白色部分进行骨架化处理
    # 使用numpy fromfile解决中文路径问题
    try:
        processed_img_data = np.fromfile(temp_path, dtype=np.uint8)
        processed_img = cv2.imdecode(processed_img_data, cv2.IMREAD_GRAYSCALE)
        os.unlink(temp_path)  # 读取后删除临时文件
        if processed_img is None:
            print(f"❌ 无法读取 processed_binary.png")
            return [], None, []
    except Exception as e:
        print(f"❌ 读取 processed_binary.png 时发生错误: {e}")
        return [], None, []
    
    # 确保图像是二值化的
    _, processed_binary = cv2.threshold(processed_img, 127, 255, cv2.THRESH_BINARY)
    
    # 获取骨架路径（中心线）- 将整个白色区域视为线条
    strokes, skeleton = extract_skeleton_paths(processed_binary)

    # 估算每条路径的宽度（使用距离变换）
    dist_transform = cv2.distanceTransform(processed_binary, cv2.DIST_L2, 5)
    stroke_widths = []
    
    # 打印骨架信息
    print(f"找到 {len(strokes)} 条骨架路径")
    
    for i, path in enumerate(strokes):
        widths = []
        for x, y in path:
            if 0 <= x < dist_transform.shape[1] and 0 <= y < dist_transform.shape[0]:
                widths.append(int(dist_transform[y, x] * 2))  # 直径 = 2 * 半径
        
        avg_width = max(1, int(np.mean(widths))) if widths else 1
        stroke_widths.append(avg_width)
        
        # 调试信息
        if i < 5 or i % 50 == 0:  # 只打印部分路径信息
            print(f"路径 {i}: 点数={len(path)}, 平均宽度={avg_width}px")

    # 保存中间结果用于调试
    try:
        success, encoded_img = cv2.imencode('.png', skeleton)
        if success:
            encoded_img.tofile(os.path.join(output_path, 'skeleton.png'))
        
        success, encoded_img = cv2.imencode('.png', (dist_transform * 10).astype(np.uint8))
        if success:
            encoded_img.tofile(os.path.join(output_path, 'distance_transform.png'))
    except Exception as e:
        print(f"❌ 保存中间结果时发生错误: {e}")
    
    # 保存笔画宽度信息
    stroke_widths_path = os.path.join(config_path, 'stroke_widths.txt')
    with open(stroke_widths_path, 'w') as f:
        for width in stroke_widths:
            f.write(f"{width}\n")
    
    # 统计宽度范围
    if stroke_widths:
        min_width = min(stroke_widths)
        max_width = max(stroke_widths)
    else:
        min_width = max_width = 0
    
    print(f"✅ 提取 {len(strokes)} 条中心线路径，支持实心绘制")
    print(f"笔画宽度范围: 最小={min_width}px, 最大={max_width}px")
    return strokes, binary, stroke_widths

def draw_on_canvas(traced_paths, canvas_top_left, canvas_size, stroke_widths=None, scale_factor=1.0):
    """在画布上逐条绘制笔触，根据线条宽度自动切换画笔大小"""
    global should_exit, is_paused
    screen_width, screen_height = pyautogui.size()
    safe_margin = 30
    
    # 初始化画笔大小
    current_brush_size = 1
    slider_positions = None
    
    # 加载已保存的滑块位置（从最细到最粗的画笔坐标）
    slider_positions = load_brush_slider_positions()
    
    # 验证加载的位置数量
    if slider_positions and len(slider_positions) == 5:
        print("已成功加载5个画笔档位位置，按最细到最粗顺序使用")
    else:
        print("警告：未找到有效滑块位置或位置数量不正确")
        print("请确保brush_slider_positions.txt文件包含5个坐标，顺序为最细到最粗")
    
    # 计算缩放因子和偏移
    min_x = min(min(p[0] for p in path) for path in traced_paths)
    min_y = min(min(p[1] for p in path) for path in traced_paths)
    max_x = max(max(p[0] for p in path) for path in traced_paths)
    max_y = max(max(p[1] for p in path) for path in traced_paths)
    
    # 计算图像实际宽度和高度
    img_width = max_x - min_x
    img_height = max_y - min_y
    
    canvas_width, canvas_height = canvas_size
    
    # 计算缩放因子
    scale_x = canvas_width / img_width if img_width > 0 else 1
    scale_y = canvas_height / img_height if img_height > 0 else 1
    scale_factor = min(scale_x, scale_y) * 0.9
    
    # 计算偏移量
    offset_x = (canvas_width - img_width * scale_factor) // 2
    offset_y = (canvas_height - img_height * scale_factor) // 2
    
    # 打印调试信息
    print(f"图像范围: X({min_x}-{max_x}), Y({min_y}-{max_y})")
    print(f"画布位置: 左上角({canvas_top_left[0]}, {canvas_top_left[1]})")
    print(f"缩放因子: {scale_factor:.4f}")
    print(f"偏移量: X={offset_x}, Y={offset_y}")
    
    # 启动键盘监听，使用非阻塞模式
    print("提示: 按ESC键随时中断绘制过程")
    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True  # 设置为守护进程，主程序结束时自动停止
    listener.start()
    
    # 给监听器一些初始化时间
    time.sleep(0.1)

    print("正在绘制... 请等待...")
    print(f"准备绘制 {len(traced_paths)} 条笔触")
    time.sleep(1)

    total_paths = len(traced_paths)
    drawn_paths = 0
    total_points = sum(len(path) for path in traced_paths)
    drawn_points = 0

    pen_is_down = False  # 初始状态：笔是抬起的
    
    # 为不同粗细线条优化的移动参数（已提速）
    thin_line_delay = 0.001  # 细线条使用更快的速度
    medium_line_delay = 0.002  # 中等线条速度
    thick_line_delay = 0.003  # 粗线条使用更快的速度
    
    for path_idx, path in enumerate(traced_paths):
        if should_exit:
            break
            
        # 检查是否暂停
        while is_paused:
            if should_exit:
                break
            time.sleep(0.1)
        if should_exit:
            break
            
        # 获取当前笔画的宽度
        width = 1  # 默认宽度
        if stroke_widths and path_idx < len(stroke_widths):
            width = stroke_widths[path_idx]
        
        # 映射宽度到画笔大小档位
        target_brush_size = map_width_to_brush_size(width)
        
        # 切换画笔大小（如果需要）- 优先处理宽度变化
        if target_brush_size != current_brush_size and slider_positions:
            print(f"发现线条宽度变化，需要切换画笔大小: 当前{current_brush_size}档 -> 目标{target_brush_size}档")
            print("正在切换画笔大小")
            # 确保笔是抬起的状态
            if pen_is_down:
                pyautogui.mouseUp(button='left')
                pen_is_down = False
                time.sleep(0.02)
            # 切换画笔大小
            switch_brush_to_size(target_brush_size, slider_positions)
            current_brush_size = target_brush_size
            print(f"画笔大小已切换到档位 {current_brush_size}")
            # 切换后不立即移动，因为后面会专门移动到绘制起点
        
        # 根据线条宽度选择延迟参数
        if width <= 2:
            current_delay = thin_line_delay
            line_type = "极细线条"
        elif width <= 7:
            current_delay = medium_line_delay
            line_type = "中等线条"
        else:
            current_delay = thick_line_delay
            line_type = "粗线条"
        
        # 扩展过短路径，确保在画布上可见
        extended_path = extend_short_path(path, threshold=20, target_length=23)
        
        # 如果是点路径（空列表），直接跳过绘制
        if not extended_path:
            continue
        
        # 转换坐标
        scaled_path = []
        for p in extended_path:
            # 映射到画布坐标
            x = int(canvas_top_left[0] + offset_x + (p[0] - min_x) * scale_factor)
            y = int(canvas_top_left[1] + offset_y + (p[1] - min_y) * scale_factor)
            
            # 确保坐标在安全范围内
            x = max(canvas_top_left[0], min(x, canvas_top_left[0] + canvas_width - 1))
            y = max(canvas_top_left[1], min(y, canvas_top_left[1] + canvas_height - 1))
            
            scaled_path.append((x, y))
        
        # 输出第一个点的坐标用于调试
        if path_idx == 0:
            print(f"第一个绘制点: ({scaled_path[0][0]}, {scaled_path[0][1]})")
        
        # 确保笔是抬起的状态 - 加强状态管理
        if pen_is_down:
            pyautogui.mouseUp(button='left')  # 明确指定左键抬笔
            pen_is_down = False
            time.sleep(0.02)  # 增加延迟确保抬笔完全生效
        
        # 确保当前鼠标位置不是在点击状态
        # 抬笔状态下移动到起点 - 使用更快的移动
        pyautogui.moveTo(scaled_path[0][0], scaled_path[0][1], duration=0.02)  # 更快移动
        time.sleep(0.005)  # 减少延迟
        
        # 调试信息
        if path_idx < 5 or path_idx % 50 == 0:
            print(f"绘制笔触 {path_idx+1}: 点数={len(path)}, 宽度={width}px, 画笔档位={current_brush_size}, 类型={line_type}")
        
        # 落笔开始绘制 - 确保只在起点位置进行一次点击
        pyautogui.mouseDown(button='left')  # 明确指定左键
        pen_is_down = True
        time.sleep(0.01)  # 给一个极小延迟确保点击状态稳定

        # 绘制整条路径 - 根据线条类型调整速度（已提速）
        for x, y in scaled_path[1:]:
            # 在每次移动前检查是否应该退出
            if check_exit_condition():
                break
                
            # 检查是否暂停
            while is_paused:
                if check_exit_condition():
                    break
                time.sleep(0.1)
            if check_exit_condition():
                break
                
            # 使用更精确的移动方法
            pyautogui.moveTo(x, y, duration=current_delay*0.3)  # 进一步缩短移动时间
            drawn_points += 1
            if drawn_points % 1000 == 0:
                print(f"已绘制点: {drawn_points}/{total_points}")
                
        # 再次检查是否应该退出
        if check_exit_condition():
            break

        # 绘制完成，抬笔
        pyautogui.mouseUp(button='left')
        pen_is_down = False
        
        # 每个笔画之间的等待时间根据线条宽度调整（已大幅缩短）
        if width <= 2:
            time.sleep(0.05)  # 细线条之间更短的间隔
        elif width <= 7:
            time.sleep(0.08)  # 中等线条更短的间隔
        else:
            time.sleep(0.1)  # 粗线条更短的间隔

        drawn_paths += 1
        progress = int(drawn_paths / total_paths * 100)
        if progress % 5 == 0 or drawn_paths == total_paths:
            print(f"进度: {progress}% ({drawn_paths}/{total_paths} 条笔触)")

    # 确保停止监听器
    if hasattr(listener, 'stop'):
        listener.stop()
        listener.join(timeout=1.0)  # 等待监听器线程结束
    
    # 确保鼠标抬起
    pyautogui.mouseUp()
    
    # 根据退出状态显示不同信息
    if should_exit:
        print(f"\n🔴 程序已被用户中断！已处理 {drawn_points} 个像素点")
        print(f"已完成 {drawn_paths}/{total_paths} 条笔触 (约 {int(drawn_paths/total_paths*100)}%)")
    else:
        print(f"\n✅ 绘制完成！总共处理 {drawn_points} 个像素点")
        print("查看生成的contours_visualization.png和processed_binary.png以检查细节提取效果")
    
    # 重置退出和暂停标志，确保下次运行正常
    should_exit = False
    is_paused = False

def main():
    global should_exit, is_paused
    # 重置退出标志，确保每次运行都从头开始
    should_exit = False
    # 重置暂停标志，确保每次运行都从非暂停状态开始
    is_paused = False
    
    parser = argparse.ArgumentParser(description='高精细度一笔画绘制')
    parser.add_argument('-i', '--image', required=True, help='输入图像路径')
    parser.add_argument('-m', '--mode', choices=['draw', 'click'], default='draw', 
                        help='运行模式: draw-绘制图像, click-点击坐标点 (默认: draw)')
    args = parser.parse_args()
    
    # 确保图像路径使用正确的编码
    image_path = os.path.abspath(args.image)

    print("=== 高精细度一笔画绘制工具（支持智能画笔大小切换）===")
    print(f"当前运行模式: {args.mode}")
    
    # 如果选择点击模式且存在捕获的坐标
    if args.mode == 'click':
        captured_coords = load_captured_coordinates()
        if captured_coords:
            print("💡 使用captured_coordinates.json中的坐标点进行绘制")
            
            # 绘制这些坐标点
            print(f"准备点击 {len(captured_coords)} 个坐标点")
            
            # 确保画笔处于初始状态
            slider_positions = load_brush_slider_positions()
            if slider_positions and len(slider_positions) >= 1:
                print("将画笔设置为最细档位")
                switch_brush_to_size(1, slider_positions)
            
            # 依次点击每个坐标点
            for i, (x, y) in enumerate(captured_coords):
                print(f"点击坐标点 {i+1}/{len(captured_coords)}: ({x}, {y})")
                pyautogui.moveTo(x, y, duration=0.1)
                pyautogui.click()
                time.sleep(0.5)  # 点击间隔
            
            print("✅ 所有坐标点点击完成！")
            return
        else:
            print("❌ 未找到captured_coordinates.json或文件中没有坐标点，切换到正常绘画模式")
    
    # 默认执行正常的图像绘制流程
    print("🎨 开始正常图像绘制模式")
    
    # 加载画布坐标
    top_left, size, bottom_right = load_canvas_coordinates()
    if not top_left:
        print("错误：未找到画布坐标！")
        return

    if not os.path.exists(image_path):
        print(f"错误：图片不存在！路径：{image_path}")
        return

    print(f"处理图像: {image_path}")

    # 高效处理图像并提取笔触和宽度信息
    strokes, binary, stroke_widths = extract_strict_strokes(image_path)

    if len(strokes) == 0:
        print("未找到有效线条！")
        return

    print(f"共生成 {len(strokes)} 条笔触，开始绘制...")
    print("系统将根据线条粗细自动切换画笔大小")

    # 绘制 - strokes已经是高质量的路径，包含宽度信息
    draw_on_canvas(strokes, top_left, size, stroke_widths)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被中断")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        pyautogui.mouseUp()
        print("程序结束")