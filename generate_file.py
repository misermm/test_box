#!/usr/bin/env python3
"""
生成指定大小的文件
支持生成ZIP、普通文件等
"""

import os
import sys
import zipfile
import argparse


CORRUPT_METHODS = {
    "header_tail": "覆盖头部和尾部",
    "header_only": "仅覆盖头部",
    "tail_only": "仅覆盖尾部",
    "random_positions": "随机位置覆盖",
    "full_random": "全部随机覆盖",
    "truncate": "截断文件",
    "zero_fill": "全部清零",
}


def corrupt_file(output_path, method="header_tail"):
    """
    损坏文件：按照指定方式损坏文件

    参数:
        output_path: 文件路径
        method: 损坏方式
            - header_tail: 覆盖头部和尾部（默认）
            - header_only: 仅覆盖头部
            - tail_only: 仅覆盖尾部
            - random_positions: 随机位置覆盖
            - full_random: 全部随机覆盖
            - truncate: 截断文件
            - zero_fill: 全部清零
    """
    print(f"正在损坏文件（方式：{CORRUPT_METHODS.get(method, method)}）...")
    total = os.path.getsize(output_path)
    if total <= 0:
        return

    region = min(4096, total // 2)

    with open(output_path, 'r+b') as f:
        if method == "header_tail":
            f.write(os.urandom(region))
            f.seek(total - region)
            f.write(os.urandom(region))
            print(f"已覆盖头部和尾部各 {region} 字节")

        elif method == "header_only":
            f.write(os.urandom(region))
            print(f"已覆盖头部 {region} 字节")

        elif method == "tail_only":
            f.seek(total - region)
            f.write(os.urandom(region))
            print(f"已覆盖尾部 {region} 字节")

        elif method == "random_positions":
            num_positions = min(10, total // 1024)
            positions = sorted([int.from_bytes(os.urandom(4), 'big') % total for _ in range(num_positions)])
            for pos in positions:
                chunk_size = min(256, total - pos)
                f.seek(pos)
                f.write(os.urandom(chunk_size))
            print(f"已覆盖 {num_positions} 个随机位置")

        elif method == "full_random":
            f.seek(0)
            chunk_size = 1024 * 1024
            written = 0
            while written < total:
                data = os.urandom(min(chunk_size, total - written))
                f.write(data)
                written += len(data)
            print(f"已将全部 {total} 字节替换为随机数据")

        elif method == "truncate":
            keep_size = max(1, total // 2)
            f.truncate(keep_size)
            print(f"已截断文件，保留 {keep_size} 字节")

        elif method == "zero_fill":
            f.seek(0)
            chunk_size = 1024 * 1024
            written = 0
            while written < total:
                data = b'\x00' * min(chunk_size, total - written)
                f.write(data)
                written += len(data)
            print(f"已将全部 {total} 字节清零")


def create_file(output_path, size_mb, file_type="zip", corrupted=False, corrupt_method="header_tail"):
    """
    创建指定大小的文件

    参数:
        output_path: 输出文件路径
        size_mb: 文件大小（MB）
        file_type: 文件类型 (zip, plain, pdf, docx, xlsx)
        corrupted: 是否生成损坏的文件
        corrupt_method: 损坏方式 (header_tail, header_only, tail_only, random_positions, full_random, truncate, zero_fill)
    """
    size_bytes = int(size_mb * 1024 * 1024)
    
    print(f"目标大小: {size_mb} MB ({size_bytes} bytes)")
    print(f"文件类型: {file_type}")
    if corrupted:
        print(f"是否损坏: 是（{CORRUPT_METHODS.get(corrupt_method, corrupt_method)}）")
    else:
        print(f"是否损坏: 否")
    print(f"输出路径: {output_path}")
    print()
    
    # 创建目录
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    if file_type == "zip":
        create_zip_file(output_path, size_bytes)
    elif file_type == "pdf":
        create_pdf_file(output_path, size_bytes)
    elif file_type == "docx":
        create_docx_file(output_path, size_bytes)
    elif file_type == "xlsx":
        create_xlsx_file(output_path, size_bytes)
    else:
        create_plain_file(output_path, size_bytes)

    if corrupted:
        corrupt_file(output_path, corrupt_method)

    # 验证文件大小
    actual_size = os.path.getsize(output_path)
    actual_mb = actual_size / (1024 * 1024)
    
    print(f"\n创建成功!")
    print(f"文件: {output_path}")
    print(f"实际大小: {actual_mb:.2f} MB")
    return True


def create_zip_file(output_path, target_size):
    """创建指定大小的ZIP文件"""
    print("正在创建ZIP文件...")
    
    # 使用随机数据（不可压缩）来确保文件大小准确
    chunk_size = 1024 * 1024  # 1MB
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_STORED) as zipf:
        bytes_written = 0
        part_num = 0
        
        while bytes_written < target_size:
            # 创建1MB的随机数据（不可压缩）
            data = os.urandom(chunk_size)
            
            # 计算当前还需要多少字节
            remaining = target_size - bytes_written
            if remaining < chunk_size:
                data = data[:remaining]
            
            # 写入ZIP（不压缩）
            zipf.writestr(f"data_{part_num:04d}.bin", data)
            
            bytes_written += len(data)
            part_num += 1
            
            # 显示进度
            progress = min(100, (bytes_written / target_size) * 100)
            print(f"\r进度: {progress:.1f}%", end="", flush=True)
    
    print()  # 换行


def create_plain_file(output_path, target_size):
    """创建指定大小的普通文件"""
    print("正在创建文件...")
    
    chunk_size = 1024 * 1024  # 1MB
    bytes_written = 0
    
    with open(output_path, 'wb') as f:
        while bytes_written < target_size:
            # 写入1MB的随机数据（最后一块截断到剩余字节数）
            remaining = target_size - bytes_written
            data = os.urandom(min(chunk_size, remaining))
            f.write(data)
            
            bytes_written += len(data)
            
            # 显示进度
            progress = min(100, (bytes_written / target_size) * 100)
            print(f"\r进度: {progress:.1f}%", end="", flush=True)
    
    print()  # 换行


def create_pdf_file(output_path, target_size):
    """创建指定大小的PDF文件"""
    print("正在创建PDF文件...")
    
    # PDF 文件头
    header = b"%PDF-1.4\n"
    
    # 各对象的内容（按顺序写入）
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << >> >>\nendobj\n"
    
    # obj4 的stream内容（固定文本）和stream头尾模板
    stream_content = b"BT /F1 12 Tf 100 700 Td (Test Page) Tj ET"
    
    # 计算各部分偏移
    header_size = len(header)
    obj1_offset = header_size
    obj2_offset = obj1_offset + len(obj1)
    obj3_offset = obj2_offset + len(obj2)
    
    # obj4 头部固定部分： "4 0 obj\n<< /Length XXXXX >>\nstream\n"
    # 先用占位长度计算偏移，后面再修正
    obj4_header_template = b"4 0 obj\n<< /Length %d >>\nstream\n"
    obj4_footer = b"\nendstream\nendobj\n"
    
    # xref + trailer 大约需要 200 字节
    # obj4 头部大小：用较大长度估算（100000000 是 9 位数）
    obj4_header_approx = len(b"4 0 obj\n<< /Length 100000000 >>\nstream\n")
    
    # 填充数据大小 = 目标大小 - 头部 - obj1-3 - obj4头尾近似 - stream内容 - xref/trailer
    fixed_overhead = header_size + len(obj1) + len(obj2) + len(obj3)
    fixed_overhead += obj4_header_approx + len(stream_content) + len(obj4_footer)
    fixed_overhead += 200  # xref + trailer
    
    filler_size = target_size - fixed_overhead
    
    # 如果目标太小，创建最小有效PDF（无填充）
    if filler_size <= 0:
        obj4 = b"4 0 obj\n<< /Length %d >>\nstream\n" % len(stream_content)
        obj4 += stream_content
        obj4 += b"\nendstream\nendobj\n"
        obj4_offset = obj3_offset + len(obj3)
        
        with open(output_path, 'wb') as f:
            f.write(header + obj1 + obj2 + obj3 + obj4)
            xref_offset = f.tell()
            f.write(b"xref\n0 5\n")
            f.write(b"0000000000 65535 f \n")
            for off in [obj1_offset, obj2_offset, obj3_offset, obj4_offset]:
                f.write(("%010d 00000 n \n" % off).encode())
            f.write(b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n")
            f.write(("%d\n" % xref_offset).encode())
            f.write(b"%%EOF\n")
        return
    
    # 计算精确的obj4头部大小（填充数据字节数的位数）
    obj4_header = obj4_header_template % (len(stream_content) + filler_size)
    obj4_offset = obj3_offset + len(obj3)
    
    with open(output_path, 'wb') as f:
        f.write(header)
        f.write(obj1)
        f.write(obj2)
        f.write(obj3)
        
        # 写入 obj4 头部
        f.write(obj4_header)
        
        # 写入 stream 内容（固定文本）
        f.write(stream_content)
        
        # 写入填充数据
        chunk_size = 1024 * 1024  # 1MB
        bytes_written = 0
        
        while bytes_written < filler_size:
            data = os.urandom(min(chunk_size, filler_size - bytes_written))
            f.write(data)
            bytes_written += len(data)
            
            progress = min(100, (bytes_written / filler_size) * 100)
            print(f"\r进度: {progress:.1f}%", end="", flush=True)
        
        # 写入 obj4 尾部
        f.write(obj4_footer)
        
        # xref表
        xref_offset = f.tell()
        f.write(b"xref\n0 5\n")
        f.write(b"0000000000 65535 f \n")
        for off in [obj1_offset, obj2_offset, obj3_offset, obj4_offset]:
            f.write(("%010d 00000 n \n" % off).encode())
        
        # trailer
        f.write(b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n")
        f.write(("%d\n" % xref_offset).encode())
        f.write(b"%%EOF\n")
    
    print()


def create_docx_file(output_path, target_size):
    """创建指定大小的DOCX文件"""
    print("正在创建DOCX文件...")
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_STORED) as zipf:
        # DOCX 基本结构（有效的空文档）
        zipf.writestr('[Content_Types].xml', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        
        zipf.writestr('_rels/.rels', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
        
        zipf.writestr('word/_rels/document.xml.rels', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>""")
        
        zipf.writestr('word/document.xml', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r>
        <w:t>Test Document</w:t>
      </w:r>
    </w:p>
  </w:body>
</w:document>""")
        
        # 获取当前ZIP大小
        current_size = zipf.fp.tell()
        
        # 填充数据到目标大小
        filler_size = target_size - current_size
        if filler_size > 0:
            chunk_size = 1024 * 1024  # 1MB
            bytes_written = 0
            
            while bytes_written < filler_size:
                data = os.urandom(min(chunk_size, filler_size - bytes_written))
                zipf.writestr(f'filler/filler_{bytes_written:08d}.bin', data)
                bytes_written += len(data)
                
                progress = min(100, (bytes_written / filler_size) * 100)
                print(f"\r进度: {progress:.1f}%", end="", flush=True)
    
    print()


def create_xlsx_file(output_path, target_size):
    """创建指定大小的XLSX文件"""
    print("正在创建XLSX文件...")
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_STORED) as zipf:
        # XLSX 基本结构（有效的空工作簿）
        zipf.writestr('[Content_Types].xml', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>""")
        
        zipf.writestr('_rels/.rels', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        
        zipf.writestr('xl/_rels/workbook.xml.rels', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""")
        
        zipf.writestr('xl/workbook.xml', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""")
        
        zipf.writestr('xl/worksheets/sheet1.xml', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="inlineStr">
        <is><t>Test</t></is>
      </c>
    </row>
  </sheetData>
</worksheet>""")
        
        zipf.writestr('xl/styles.xml', """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellXfs count="1"><xf/></cellXfs>
</styleSheet>""")
        
        # 获取当前ZIP大小
        current_size = zipf.fp.tell()
        
        # 填充数据到目标大小
        filler_size = target_size - current_size
        if filler_size > 0:
            chunk_size = 1024 * 1024  # 1MB
            bytes_written = 0
            
            while bytes_written < filler_size:
                data = os.urandom(min(chunk_size, filler_size - bytes_written))
                zipf.writestr(f'filler/filler_{bytes_written:08d}.bin', data)
                bytes_written += len(data)
                
                progress = min(100, (bytes_written / filler_size) * 100)
                print(f"\r进度: {progress:.1f}%", end="", flush=True)
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description='生成指定大小的文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 生成101MB的ZIP文件
  python generate_file.py -s 101 -o output/file.zip
  
  # 生成50MB的ZIP文件
  python generate_file.py -s 50 -o output/file.zip -t zip
  
  # 生成25MB的普通文件
  python generate_file.py -s 25 -o output/file.bin -t plain
        """
    )
    
    parser.add_argument(
        '-s', '--size',
        type=float,
        required=True,
        help='文件大小（MB）'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='输出文件路径'
    )
    
    parser.add_argument(
        '-t', '--type',
        choices=['zip', 'plain', 'pdf', 'docx', 'xlsx'],
        default='zip',
        help='文件类型: zip, plain, pdf, docx, xlsx (默认: zip)'
    )

    parser.add_argument(
        '-c', '--corrupted',
        action='store_true',
        help='生成损坏的文件'
    )

    parser.add_argument(
        '-m', '--corrupt-method',
        choices=list(CORRUPT_METHODS.keys()),
        default='header_tail',
        help='损坏方式: ' + ', '.join(f'{k}({v})' for k, v in CORRUPT_METHODS.items()) + ' (默认: header_tail)'
    )
    
    args = parser.parse_args()

    if args.size <= 0:
        print("错误: 文件大小必须大于0")
        sys.exit(1)

    create_file(args.output, args.size, args.type, corrupted=args.corrupted, corrupt_method=args.corrupt_method)


if __name__ == '__main__':
    main()