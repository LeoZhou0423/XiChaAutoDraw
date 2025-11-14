import pygetwindow as gw
import pyautogui
import time
from PIL import Image
import os
import sys
import cv2
import numpy as np

# 获取系统AppData路径用于存储配置文件
app_data_path = os.getenv('APPDATA')
if app_data_path:
    config_path = os.path.join(app_data_path, 'XiChaDrawingTool')
    output_path = os.path.join(app_data_path, 'XiChaDrawingTool', 'output')
else:
    # 如果AppData不可用，回退到相对路径
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output')

# 创建配置目录和输出目录（如果不存在）
os.makedirs(config_path, exist_ok=True)
os.makedirs(output_path, exist_ok=True)


        
def main():
    """主函数，执行窗口检测并保存画布坐标"""
    # 获取所有窗口标题
    windows = gw.getAllTitles()
    print("所有窗口标题:", windows)

    # 根据窗口标题获取窗口对象（模糊匹配）
    # 尝试匹配"定制喜贴"或"喜茶GO"
    target_window = None
    for title in ['定制喜贴', '喜茶GO']:
        windows = gw.getWindowsWithTitle(title)
        if windows:
            target_window = windows[0]
            break

    if target_window:
        win = target_window
        print(f"找到窗口: {win.title}")
        print(f"位置: ({win.left}, {win.top})")
        print(f"大小: {win.width} x {win.height}")

        # 激活窗口到前台
        win.activate()
        time.sleep(1)  # 等待窗口完全激活
        
        # 调整窗口大小为固定的450 x 1089
        target_width = 450
        target_height = 1089
        print(f"调整窗口大小为: {target_width} x {target_height}")
        win.resizeTo(target_width, target_height)
        time.sleep(1)  # 等待窗口大小调整完成
        # 自动将窗口移动到指定位置(1371, 0)
        target_left = 1371
        target_top = 0
        print(f"将窗口移动到指定位置: ({target_left}, {target_top})")
        win.moveTo(target_left, target_top)
        time.sleep(0.5)  # 等待窗口位置调整完成
        
        # 通过颜色识别检测灰色区域
        print("\n开始通过颜色检测灰色区域...")
        try:
            # 先截取整个窗口
            window_screenshot = pyautogui.screenshot(region=(int(win.left), int(win.top), int(win.width), int(win.height)))
            
            # 将PIL图像转换为OpenCV格式
            img = cv2.cvtColor(np.array(window_screenshot), cv2.COLOR_RGB2BGR)
            
            # 直接搜索固定颜色 #EEEEEE 的灰色区域，扩大颜色范围
            # 创建颜色匹配掩码（扩大误差范围）
            lower_color = np.array([220, 220, 220])  # 降低下限
            upper_color = np.array([240,240,240])  # 提高上限
            mask = cv2.inRange(img, lower_color, upper_color)
            
            print("搜索固定颜色 #EEEEEE (BGR: [238,238,238]) 的灰色区域")
            
            # 保存掩码图像用于调试
            try:
                success, encoded_img = cv2.imencode('.png', mask)
                if success:
                    output_file = os.path.join(output_path, 'gray_mask.png')
                    encoded_img.tofile(output_file)
                    print(f"灰色区域掩码已保存为 {output_file}")
            except Exception as e:
                print(f"保存灰色区域掩码时发生错误: {e}")
            
            # 查找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            print(f"找到的轮廓数量: {len(contours)}")
            
            # 寻找最大的轮廓，假设这是我们要找的灰色区域
            if contours:
                # 计算所有轮廓的面积
                contour_areas = [cv2.contourArea(c) for c in contours]
                print(f"轮廓面积列表: {contour_areas}")
                
                # 按面积排序轮廓
                contours = sorted(contours, key=cv2.contourArea, reverse=True)
                
                # 取面积最大的轮廓
                largest_contour = contours[0]
                
                # 获取边界框
                x, y, w, h = cv2.boundingRect(largest_contour)
                
                # 计算在屏幕上的实际坐标
                left = int(win.left + x)
                top = int(win.top + y)
                canvas_width = int(w)
                canvas_height = int(h)
                
                print(f"通过颜色检测到的灰色区域位置: ({left}, {top})")
                print(f"通过颜色检测到的灰色区域大小: {canvas_width} x {canvas_height}")
                
                # 绘制边界框到原图上
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                # 保存带边界框的图像
                try:
                    success, encoded_img = cv2.imencode('.png', img)
                    if success:
                        output_file = os.path.join(output_path, 'color_detection_result.png')
                        encoded_img.tofile(output_file)
                        print(f"颜色检测结果已保存为 {output_file}")
                except Exception as e:
                    print(f"保存颜色检测结果时发生错误: {e}")
                
                # 截取灰色区域
                try:
                    # 截图区域：(left, top, width, height) - 必须是整数元组
                    screenshot = pyautogui.screenshot(region=(left, top, canvas_width, canvas_height))
                    
                    # 保存截图
                    output_file = os.path.join(output_path, 'canvas_screenshot.png')
                    screenshot.save(output_file)
                    print(f"灰色区域截图已保存为 {output_file}")
                    
                    # 显示截图信息
                    print(f"截图尺寸: {screenshot.width} x {screenshot.height}")
                    
                    # 可选：显示截图（已禁用自动显示）
                    # screenshot.show()
                    
                    # 记录灰色区域坐标到文件（指定utf-8编码避免乱码）
                    config_file = os.path.join(config_path, 'canvas_coordinates.txt')
                    with open(config_file, 'w', encoding='utf-8') as f:
                        f.write(f"灰色区域左上角坐标: ({left}, {top})\n")
                        f.write(f"灰色区域尺寸: {canvas_width} x {canvas_height}\n")
                        f.write(f"灰色区域右下角坐标: ({left + canvas_width}, {top + canvas_height})\n")
                    print(f"灰色区域坐标已记录到 {config_file} 文件中")
                    
                    # 提示用户可以运行 analyze_lines.py 来分析线条宽度
                    print("\n提示：如果需要分析画笔宽度，请运行 python analyze_lines.py")
                    
                except Exception as e:
                    print(f"截图过程中出错: {e}")
                    return False
            else:
                print("未检测到灰色区域，使用默认位置估算...")
                # 保存原图用于调试
                try:
                    success, encoded_img = cv2.imencode('.png', img)
                    if success:
                        output_file = os.path.join(output_path, 'debug_window.png')
                        encoded_img.tofile(output_file)
                        print(f"窗口截图已保存为 {output_file}")
                except Exception as e:
                    print(f"保存调试窗口截图时发生错误: {e}")
                # 如果无法通过颜色检测到灰色区域，使用原有的位置估算方法
                margin_left = win.width * 0.1  # 左侧边距约为窗口宽度的10%
                margin_top = win.height * 0.2   # 顶部边距约为窗口高度的20%
                canvas_width = win.width * 0.8   # 画布宽度约为窗口宽度的80%
                canvas_height = win.height * 0.6 # 画布高度约为窗口高度的60%
                
                # 计算截图的左上角坐标并转换为整数
                left = int(win.left + margin_left)
                top = int(win.top + margin_top)
                canvas_width = int(canvas_width)
                canvas_height = int(canvas_height)
                
                print(f"灰色区域位置估算: ({left}, {top})")
                print(f"灰色区域大小估算: {canvas_width} x {canvas_height}")
                
                # 截取灰色区域
                try:
                    screenshot = pyautogui.screenshot(region=(left, top, canvas_width, canvas_height))
                    output_file = os.path.join(output_path, 'canvas_screenshot.png')
                    screenshot.save(output_file)
                    print(f"灰色区域截图已保存为 {output_file}")
                    
                    # 记录灰色区域坐标到文件（指定utf-8编码避免乱码）
                    config_file = os.path.join(config_path, 'canvas_coordinates.txt')
                    with open(config_file, 'w', encoding='utf-8') as f:
                        f.write(f"灰色区域左上角坐标: ({left}, {top})\n")
                        f.write(f"灰色区域尺寸: {canvas_width} x {canvas_height}\n")
                        f.write(f"灰色区域右下角坐标: ({left + canvas_width}, {top + canvas_height})\n")
                    print(f"灰色区域坐标已记录到 {config_file} 文件中")
                    
                except Exception as e:
                    print(f"截图过程中出错: {e}")
                    return False
            
        except Exception as e:
            print(f"处理过程中出错: {e}")
            print("尝试直接截取整个窗口...")
            # 如果无法截取指定区域，尝试截取整个窗口
            full_screenshot = pyautogui.screenshot(region=(int(win.left), int(win.top), int(win.width), int(win.height)))
            output_file = os.path.join(output_path, 'full_window_screenshot.png')
            full_screenshot.save(output_file)
            print(f"整个窗口截图已保存为 {output_file}")
            return False
        
    else:
        print("未找到匹配的窗口！")
        return False
    
    # 检查是否存在存储的画笔宽度数据
    config_file = os.path.join(config_path, 'brush_widths.txt')
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            brush_widths = list(map(int, f.read().split(',')))
        print(f"\n已读取存储的画笔宽度数据: {brush_widths} px")
    else:
        print(f"\n未找到画笔宽度数据文件: {config_file}。运行 python analyze_lines.py 来分析线条宽度。")
    
    return True

# 如果直接运行此脚本
if __name__ == "__main__":
    main()