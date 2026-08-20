# 图片转PDF工具

将多张图片合并成一个PDF文件，每张图片一页。

## 功能特点

### 1. 图片转PDF
- 支持常见图片格式：JPG, JPEG, PNG, BMP, TIFF, GIF 等
- 支持多张图片批量处理
- 支持从文本文件读取图片列表
- 支持递归搜索子目录中的图片
- 自动将图片转换为RGB模式确保兼容性

### 2. 生成指定大小文件
- 支持生成ZIP文件
- 支持生成普通文件
- 精确控制文件大小
- 支持任意大小（MB）

## 安装依赖

```bash
pip install Pillow
```

## 使用方法

### 基本用法

```bash
# 将多张图片合并成PDF
python image_to_pdf.py image1.jpg image2.png image3.jpg

# 指定输出文件名
python image_to_pdf.py image1.jpg image2.png -o output.pdf
```

### 从文件读取图片列表

创建一个文本文件（如 `filelist.txt`），每行包含一个图片路径：

```
images/photo1.jpg
images/photo2.png
images/photo3.bmp
```

然后运行：

```bash
python image_to_pdf.py -i filelist.txt -o output.pdf
```

### 使用通配符

```bash
# 处理当前目录所有JPG图片
python image_to_pdf.py *.jpg -o all_images.pdf

# 处理子目录中的所有图片（递归）
python image_to_pdf.py images/ -r -o all_images.pdf
```

### 命令行参数

| 参数 | 说明 |
|------|------|
| `images` | 图片文件路径（支持多个文件） |
| `-i, --input-file` | 包含图片路径列表的文本文件 |
| `-o, --output` | 输出PDF文件路径（默认：output.pdf） |
| `-r, --recursive` | 递归搜索子目录中的图片文件 |

## 示例

```bash
# 基本示例
python image_to_pdf.py photo1.jpg photo2.png -o document.pdf

# 从文件列表创建PDF
python image_to_pdf.py -i my_photos.txt -o album.pdf

# 递归处理整个文件夹
python image_to_pdf.py ./vacation_photos/ -r -o vacation.pdf

# 显示帮助信息
python image_to_pdf.py -h
```

## 项目结构

```
picture_to_pdf/
├── image_to_pdf.py    # 图片转PDF脚本
├── file_splitter.py   # 文件分割脚本
├── generate_file.py   # 生成指定大小文件脚本
├── merge_images.ps1   # PowerShell核心脚本
├── 合并图片.bat        # 一键启动脚本
├── README.md          # 使用说明
└── data/              # 图片存放目录
```

## 快速开始

### 方法一：一键启动（推荐）

1. 将图片放入 `data` 目录
2. 双击运行 `合并图片.bat`
3. PDF文件将自动保存到 `data` 目录

### 方法二：命令行

```bash
# 合并data目录中的所有图片
python image_to_pdf.py data/*.png -o data/合并文档.pdf

# 或者指定具体文件
python image_to_pdf.py data/发票.png data/营业执照.png -o data/合并文档.pdf
```

### 方法三：分割成ZIP文件

```bash
# 将PDF分割成101MB的ZIP文件
python file_splitter.py split data/合并文档.pdf -s 101 -o data/zip_parts/

# 将PDF分割成50MB的ZIP文件
python file_splitter.py split data/合并文档.pdf -s 50 -o data/zip_parts/

# 合并ZIP文件
python file_splitter.py merge data/zip_parts/part_*.zip -o data/restored.pdf
```

## 生成指定大小文件

### 命令行使用

```bash
# 生成101MB的ZIP文件
python generate_file.py -s 101 -o output/file.zip

# 生成50MB的ZIP文件
python generate_file.py -s 50 -o output/file.zip -t zip

# 生成25MB的普通文件
python generate_file.py -s 25 -o output/file.bin -t plain
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `-s, --size` | 文件大小（MB） |
| `-o, --output` | 输出文件路径 |
| `-t, --type` | 文件类型: zip (默认), plain |

### 示例

```bash
# 生成101MB的ZIP文件
python generate_file.py -s 101 -o "C:\output\101mb.zip"

# 生成50MB的ZIP文件到data目录
python generate_file.py -s 50 -o "data/test.zip"

# 生成25MB的普通文件
python generate_file.py -s 25 -o "data/test.bin" -t plain
```

### 命令行使用

```bash
# 分割文件
python file_splitter.py split <输入文件> -s <大小MB> -o <输出目录>

# 示例：分割成101MB的ZIP文件
python file_splitter.py split document.pdf -s 101 -o output/

# 合并文件
python file_splitter.py merge <ZIP文件> -o <输出文件>

# 示例：合并ZIP文件
python file_splitter.py merge output/part_*.zip -o restored.pdf
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `split` | 分割操作 |
| `merge` | 合并操作 |
| `-s, --size` | 每个ZIP文件的最大大小（MB） |
| `-o, --output` | 输出目录或文件路径 |
| `-p, --prefix` | 输出文件名前缀（默认: part） |

## 注意事项

1. 图片将按命令行参数的顺序添加到PDF中
2. 所有图片会自动转换为RGB模式以确保PDF兼容性
3. 如果图片不存在，会显示警告并跳过该文件
4. 支持中文文件名和路径
5. ZIP文件使用DEFLATE压缩算法
6. 分割后的文件可以使用 `merge` 命令重新合并