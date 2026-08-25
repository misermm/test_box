#!/usr/bin/env python3
"""
将多张图片合并成一个PDF文件，每张图片一页。
支持常见的图片格式：JPG, PNG, BMP, TIFF, GIF 等。
"""

import os
import sys
import io
import zipfile
import argparse
from pathlib import Path

def _filter_valid_images(image_paths):
    """过滤出存在的图片文件路径"""
    valid_images = []
    for img_path in image_paths:
        if not os.path.exists(img_path):
            print(f"警告: 文件不存在，已跳过 - {img_path}")
            continue
        if not os.path.isfile(img_path):
            print(f"警告: 不是文件，已跳过 - {img_path}")
            continue
        valid_images.append(img_path)
    return valid_images


def convert_images_to_zip(image_paths, output_zip_path):
    """
    将每张图片各自转换成一个单页PDF，打包进一个ZIP文件

    参数:
        image_paths: 图片文件路径列表
        output_zip_path: 输出ZIP文件路径
    """
    try:
        from PIL import Image
    except ImportError:
        print("错误: 需要安装 Pillow 库。请运行: pip install Pillow")
        sys.exit(1)

    valid_images = _filter_valid_images(image_paths)

    if not valid_images:
        print("错误: 没有有效的图片文件")
        return False

    os.makedirs(os.path.dirname(os.path.abspath(output_zip_path)), exist_ok=True)

    try:
        used_names = set()
        with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, img_path in enumerate(valid_images, 1):
                img = Image.open(img_path)
                # 转换为RGB模式（确保兼容性）
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                buf = io.BytesIO()
                img.save(buf, "PDF", resolution=100.0)
                img.close()

                # ZIP内文件名与图片同名；重名时加序号前缀避免覆盖
                base = os.path.splitext(os.path.basename(img_path))[0]
                name = f"{base}.pdf"
                if name.lower() in used_names:
                    name = f"{i:03d}_{base}.pdf"
                used_names.add(name.lower())

                zipf.writestr(name, buf.getvalue())
                print(f"已转换: {img_path} -> {name}")

        print(f"\n成功创建ZIP文件: {output_zip_path}")
        print(f"包含 {len(valid_images)} 个PDF")
        return True

    except Exception as e:
        print(f"创建ZIP时出错: {e}")
        return False

def merge_images_to_pdf(image_paths, output_pdf_path):
    """
    将多张图片合并成一个PDF文件
    
    参数:
        image_paths: 图片文件路径列表
        output_pdf_path: 输出PDF文件路径
    """
    try:
        from PIL import Image
    except ImportError:
        print("错误: 需要安装 Pillow 库。请运行: pip install Pillow")
        sys.exit(1)
    
    # 验证所有图片文件是否存在
    valid_images = _filter_valid_images(image_paths)
    
    if not valid_images:
        print("错误: 没有有效的图片文件")
        return False
    
    try:
        # 打开所有图片并转换为RGB模式
        images = []
        for img_path in valid_images:
            img = Image.open(img_path)
            # 转换为RGB模式（确保兼容性）
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)
        
        # 保存为PDF
        first_image = images[0]
        rest_images = images[1:]
        
        first_image.save(
            output_pdf_path,
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=rest_images
        )
        
        print(f"成功创建PDF文件: {output_pdf_path}")
        print(f"包含 {len(valid_images)} 张图片")
        return True
        
    except Exception as e:
        print(f"创建PDF时出错: {e}")
        return False

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description='将多张图片合并成一个PDF文件，每张图片一页',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python image_to_pdf.py image1.jpg image2.png -o output.pdf
  python image_to_pdf.py *.jpg -o result.pdf
  python image_to_pdf.py -i filelist.txt -o output.pdf
        """
    )
    
    parser.add_argument(
        'images',
        nargs='*',
        help='图片文件路径（支持多个文件）'
    )
    
    parser.add_argument(
        '-i', '--input-file',
        help='包含图片文件路径列表的文本文件（每行一个路径）'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='output.pdf',
        help='输出PDF文件路径（默认: output.pdf）'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='递归搜索子目录中的图片文件'
    )

    parser.add_argument(
        '-z', '--zip',
        action='store_true',
        help='每张图片单独转成一个PDF，打包为一个ZIP文件'
    )
    
    args = parser.parse_args()
    
    # 收集图片路径
    image_paths = []
    
    # 从命令行参数
    if args.images:
        image_paths.extend(args.images)
    
    # 从输入文件
    if args.input_file:
        if not os.path.exists(args.input_file):
            print(f"错误: 输入文件不存在 - {args.input_file}")
            sys.exit(1)
        
        # utf-8-sig 兼容带 BOM 的文件（如 Windows 记事本保存的 UTF-8）
        with open(args.input_file, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # 忽略空行和注释
                    image_paths.append(line)
    
    # 如果没有指定任何图片文件，显示帮助
    if not image_paths:
        parser.print_help()
        print("\n错误: 请指定至少一个图片文件")
        sys.exit(1)
    
    # 如果启用递归搜索，展开目录
    if args.recursive:
        expanded_paths = []
        for path in image_paths:
            if os.path.isdir(path):
                # 搜索目录中的图片文件
                from pathlib import Path
                for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.tif', '*.gif']:
                    expanded_paths.extend(Path(path).rglob(ext))
            else:
                expanded_paths.append(path)
        # 大小写不敏感排序，保证页序稳定且符合直觉
        image_paths = sorted((str(p) for p in expanded_paths), key=str.lower)
    
    # 转换图片
    if args.zip:
        success = convert_images_to_zip(image_paths, args.output)
    else:
        success = merge_images_to_pdf(image_paths, args.output)
    
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    main()