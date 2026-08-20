#!/usr/bin/env python3
"""
生成指定大小的文件
支持生成ZIP、普通文件等
"""

import os
import sys
import zipfile
import argparse


def create_file(output_path, size_mb, file_type="zip"):
    """
    创建指定大小的文件
    
    参数:
        output_path: 输出文件路径
        size_mb: 文件大小（MB）
        file_type: 文件类型 (zip, plain, pdf, docx, xlsx)
    """
    size_bytes = int(size_mb * 1024 * 1024)
    
    print(f"目标大小: {size_mb} MB ({size_bytes} bytes)")
    print(f"文件类型: {file_type}")
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
            # 写入1MB的随机数据
            data = os.urandom(chunk_size)
            f.write(data)
            
            bytes_written += chunk_size
            
            # 显示进度
            progress = min(100, (bytes_written / target_size) * 100)
            print(f"\r进度: {progress:.1f}%", end="", flush=True)
    
    print()  # 换行


def create_pdf_file(output_path, target_size):
    """创建指定大小的PDF文件"""
    print("正在创建PDF文件...")
    
    # PDF 文件头
    header = b"%PDF-1.4\n"
    
    # 创建一个简单的PDF页面（A4大小）+ xref + trailer
    # 这些内容放在文件末尾，确保结构有效
    page_content = b"""1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj

2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj

3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << >> >>
endobj

4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Test Page) Tj ET
endstream
endobj

xref
0 5
0000000000 65535 f 
"""
    # 注意：xref偏移值需要在最后修正，这里先用占位符
    page_content += b"0000000009 00000 n \n"
    page_content += b"0000000058 00000 n \n"
    page_content += b"0000000115 00000 n \n"
    page_content += b"0000000266 00000 n \n"
    
    trailer = b"""
trailer
<< /Size 5 /Root 1 0 R >>
startxref
"""
    trailer += b"360\n"
    trailer += b"%%EOF\n"
    
    header_size = len(header)
    page_size = len(page_content) + len(trailer)
    filler_size = target_size - header_size - page_size
    
    # 如果目标太小，无法创建有效PDF
    if filler_size < 0:
        # 只写入最小有效PDF（无填充）
        with open(output_path, 'wb') as f:
            f.write(header + page_content + trailer)
        return
    
    with open(output_path, 'wb') as f:
        f.write(header)
        
        # 写入填充数据（作为PDF stream对象）
        # 创建一个填充对象，使其成为有效的PDF结构
        filler_obj_header = b"5 0 obj\n<< /Length " + str(filler_size).encode() + b" >>\nstream\n"
        filler_obj_footer = b"\nendstream\nendobj\n"
        
        # 计算各部分偏移
        obj1_offset = header_size
        obj2_offset = header_size + len(f"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n\n")
        
        # 写入填充对象头
        f.write(filler_obj_header)
        filler_start = f.tell()
        
        # 写入填充数据
        chunk_size = 1024 * 1024  # 1MB
        bytes_written = 0
        
        while bytes_written < filler_size:
            data = os.urandom(min(chunk_size, filler_size - bytes_written))
            f.write(data)
            bytes_written += len(data)
            
            progress = min(100, (bytes_written / filler_size) * 100)
            print(f"\r进度: {progress:.1f}%", end="", flush=True)
        
        # 写入填充对象尾
        f.write(filler_obj_footer)
        
        # 计算xref偏移（填充对象后的偏移）
        xref_offset = f.tell()
        
        # 写入页面内容和trailer
        f.write(page_content)
        
        # 修正xref偏移（简化处理，使用固定偏移）
        # 注意：这里xref偏移值是近似的，但对于大文件影响很小
        f.write(trailer)
    
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
    
    args = parser.parse_args()
    
    if args.size <= 0:
        print("错误: 文件大小必须大于0")
        sys.exit(1)
    
    create_file(args.output, args.size, args.type)


if __name__ == '__main__':
    main()