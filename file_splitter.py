#!/usr/bin/env python3
"""
将文件分割成指定大小的ZIP文件
支持按大小分割并压缩
"""

import os
import sys
import math
import zipfile
import argparse
from pathlib import Path


def get_file_size_mb(file_path):
    """获取文件大小（MB）"""
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)


def split_to_zip(input_file, output_dir, max_size_mb, prefix="part"):
    """
    将文件分割成指定大小的ZIP文件
    
    参数:
        input_file: 输入文件路径
        output_dir: 输出目录
        max_size_mb: 每个ZIP文件的最大大小（MB）
        prefix: 输出文件名前缀
    """
    if not os.path.exists(input_file):
        print(f"错误: 文件不存在 - {input_file}")
        return False
    
    # 获取文件信息
    file_size_mb = get_file_size_mb(input_file)
    file_name = os.path.basename(input_file)
    
    print(f"文件: {file_name}")
    print(f"文件大小: {file_size_mb:.2f} MB")
    print(f"目标分片大小: {max_size_mb} MB")
    
    # 如果文件小于指定大小，直接压缩
    if file_size_mb <= max_size_mb:
        output_file = os.path.join(output_dir, f"{prefix}_1.zip")
        print(f"\n文件小于目标大小，直接创建ZIP文件...")
        
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(input_file, file_name)
        
        final_size = get_file_size_mb(output_file)
        print(f"创建成功: {output_file}")
        print(f"ZIP文件大小: {final_size:.2f} MB")
        return True
    
    # 计算需要分割的块数
    input_size_bytes = os.path.getsize(input_file)
    max_size_bytes = max_size_mb * 1024 * 1024
    num_parts = math.ceil(input_size_bytes / max_size_bytes)
    
    print(f"\n需要分割成 {num_parts} 个部分")
    
    # 读取文件内容
    with open(input_file, 'rb') as f:
        data = f.read()
    
    # 计算每部分的大小
    part_size = math.ceil(len(data) / num_parts)
    
    # 创建分割文件
    created_files = []
    for i in range(num_parts):
        start = i * part_size
        end = min((i + 1) * part_size, len(data))
        part_data = data[start:end]
        
        # 创建临时文件
        temp_file = os.path.join(output_dir, f"{prefix}_temp_{i+1}.bin")
        with open(temp_file, 'wb') as f:
            f.write(part_data)
        
        # 压缩成ZIP
        output_file = os.path.join(output_dir, f"{prefix}_{i+1}.zip")
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(temp_file, f"{file_name}.part{i+1}")
        
        # 删除临时文件
        os.remove(temp_file)
        
        final_size = get_file_size_mb(output_file)
        print(f"创建: {output_file} ({final_size:.2f} MB)")
        created_files.append(output_file)
    
    print(f"\n分割完成! 共创建 {len(created_files)} 个ZIP文件")
    return True


def merge_zip_files(zip_files, output_file):
    """
    合并多个ZIP文件
    
    参数:
        zip_files: ZIP文件列表（支持glob模式）
        output_file: 输出文件路径
    """
    import glob
    
    # 展开glob模式
    expanded_files = []
    for pattern in zip_files:
        expanded_files.extend(glob.glob(pattern))
    
    if not expanded_files:
        print("错误: 没有找到匹配的ZIP文件")
        return False
    
    all_data = {}
    
    # 读取所有ZIP文件
    for zip_file in sorted(expanded_files):
        print(f"读取: {zip_file}")
        with zipfile.ZipFile(zip_file, 'r') as zipf:
            for name in zipf.namelist():
                # 从文件名提取部分号
                if '.part' in name:
                    part_str = name.split('.part')[-1]
                    try:
                        part_num = int(part_str)
                        all_data[part_num] = zipf.read(name)
                    except ValueError:
                        continue
    
    if not all_data:
        print("错误: 没有找到可合并的数据")
        return False
    
    # 按顺序合并
    print(f"\n合并 {len(all_data)} 个部分...")
    merged_data = b''
    for part_num in sorted(all_data.keys()):
        merged_data += all_data[part_num]
    
    # 保存合并后的文件
    with open(output_file, 'wb') as f:
        f.write(merged_data)
    
    print(f"合并完成: {output_file}")
    print(f"文件大小: {get_file_size_mb(output_file):.2f} MB")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='将文件分割成指定大小的ZIP文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 将PDF分割成每个101MB的ZIP文件
  python file_splitter.py split document.pdf -s 101 -o output/
  
  # 合并ZIP文件
  python file_splitter.py merge output/part_*.zip -o merged.pdf
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='操作类型')
    
    # 分割命令
    split_parser = subparsers.add_parser('split', help='分割文件')
    split_parser.add_argument('input', help='输入文件路径')
    split_parser.add_argument('-s', '--size', type=float, required=True,
                             help='每个ZIP文件的最大大小（MB）')
    split_parser.add_argument('-o', '--output', default='.',
                             help='输出目录（默认: 当前目录）')
    split_parser.add_argument('-p', '--prefix', default='part',
                             help='输出文件名前缀（默认: part）')
    
    # 合并命令
    merge_parser = subparsers.add_parser('merge', help='合并ZIP文件')
    merge_parser.add_argument('files', nargs='+', help='ZIP文件列表')
    merge_parser.add_argument('-o', '--output', required=True,
                             help='输出文件路径')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'split':
        # 创建输出目录
        os.makedirs(args.output, exist_ok=True)
        
        success = split_to_zip(
            args.input,
            args.output,
            args.size,
            args.prefix
        )
        
        if not success:
            sys.exit(1)
    
    elif args.command == 'merge':
        success = merge_zip_files(args.files, args.output)
        
        if not success:
            sys.exit(1)


if __name__ == '__main__':
    main()