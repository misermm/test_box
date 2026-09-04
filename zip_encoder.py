import os
import zipfile
import tarfile
import shutil
import subprocess

SUPPORTED_ENCODINGS = ["UTF-8", "GBK", "GB2312", "BIG5"]
SUPPORTED_FORMATS = ["zip", "tar.gz", "7z", "rar"]

# 7z/rar 格式说明：7z 头部文件名为 UTF-16 存储（原生 Unicode，天然不乱码）；
# rar 5.x 文件名同样为 UTF-8 存储。二者均不依赖"按指定编码写文件名"，
# 因此编码选项对这两种格式不产生额外效果（不会乱码）。


def create_archive_with_encoding(file_list, out_path, encoding="UTF-8", fmt="zip"):
    """按指定编码写入压缩包内文件名。

    zip：目标编码原始字节写入文件名字段（等长占位名+字节级替换，见 BUG-13 修复）。
    tar.gz：tarfile 原生 encoding 参数。
    7z：py7zr 生成，文件名原生 Unicode（编码选项不适用，天然不乱码）。
    rar：调用系统 WinRAR 命令行（rar.exe / WinRAR.exe），未安装时报错提示。
    """
    if fmt == "tar.gz":
        with tarfile.open(out_path, "w:gz", encoding=encoding) as tar:
            for fpath in file_list:
                tar.add(fpath, arcname=os.path.basename(fpath))
        return

    if fmt == "7z":
        _create_7z(file_list, out_path)
        return

    if fmt == "rar":
        _create_rar(file_list, out_path)
        return

    # ---- zip（原有逻辑）----
    name_map = {}  # 占位名(bytes) -> 目标文件名(按目标编码的原始 bytes)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, fpath in enumerate(file_list):
            basename = os.path.basename(fpath)
            try:
                raw = basename.encode(encoding)
            except Exception:
                raw = None  # 目标编码无法表示该名字，回退原生 UTF-8
            if raw is None or encoding.upper() == "UTF-8" or raw.isascii():
                zf.write(fpath, arcname=basename)
                continue
            placeholder = _make_placeholder(idx, len(raw))
            name_map[placeholder.encode("ascii")] = raw
            zf.write(fpath, arcname=placeholder)

    if name_map:
        _patch_archive_names(out_path, name_map)


def _create_7z(file_list, out_path):
    """用 py7zr 生成 7z 压缩包。文件名以 UTF-16 头存储，原生 Unicode 不乱码。"""
    import py7zr  # 延迟导入：未安装时给出可操作的提示
    with py7zr.SevenZipFile(out_path, "w") as z:
        for fpath in file_list:
            z.write(fpath, arcname=os.path.basename(fpath))


def _find_winrar():
    """查找系统中的 WinRAR/rar 命令行工具，返回 (exe路径, 是否rar.exe) 或 None。"""
    candidates = []
    exe_name = "rar.exe" if os.name == "nt" else "rar"
    wr = "WinRAR.exe" if os.name == "nt" else None
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""),
                 os.environ.get("LOCALAPPDATA", "")):
        if base:
            candidates.append(os.path.join(base, "WinRAR", exe_name))
            candidates.append(os.path.join(base, "WinRAR", "Rar.exe"))
            if wr:
                candidates.append(os.path.join(base, "WinRAR", wr))
    candidates.append(exe_name)  # PATH 中查找
    for c in candidates:
        if c and (os.path.isfile(c) or shutil.which(c)):
            return c, os.path.basename(c).lower().startswith("rar")
    return None


def _create_rar(file_list, out_path):
    """调用 WinRAR 命令行生成 rar。rar.exe / WinRAR.exe 均可；未安装则明确报错。

    rar 文件名在 RAR5 中按 UTF-8 存储、原生 Unicode，不依赖编码选项。
    """
    found = _find_winrar()
    if not found:
        raise RuntimeError(
            "未找到 WinRAR 命令行工具（rar.exe/WinRAR.exe）。"
            "生成 rar 需要安装 WinRAR：https://www.win-rar.com/ ；"
            "或改用 zip/7z/tar.gz 格式（7z 由本工具直接生成，无需额外软件）。")
    exe, is_rar_exe = found
    if is_rar_exe:
        cmd = [exe, "a", "-ep", "-y", out_path] + list(file_list)
    else:
        # WinRAR.exe：-ibck 后台运行，-ep 不含路径，-y 覆盖
        cmd = [exe, "a", "-ibck", "-ep", "-y", out_path] + list(file_list)
    creationflags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    proc = subprocess.run(cmd, capture_output=True, timeout=600,
                          creationflags=creationflags)
    if proc.returncode != 0 or not os.path.exists(out_path):
        err = (proc.stderr or b"").decode("gbk", errors="replace").strip()
        raise RuntimeError("rar 生成失败（WinRAR 返回 %s）%s" % (proc.returncode, err))


def _make_placeholder(idx, length):
    """生成长度恰好为 length 字节的唯一 ASCII 占位名（可打印、无路径分隔符）。"""
    body = f"PN{idx:06d}X"
    reps = max(1, length // len(body))
    p = (body * reps)[:length]
    p = p[:length].ljust(length, "Q")
    return p


def _patch_archive_names(out_path, name_map):
    """把 zip 字节流中的占位名替换为目标编码原始字节（等长，偏移不变）。"""
    with open(out_path, "rb") as f:
        data = f.read()
    changed = False
    for ph_bytes, raw in name_map.items():
        count = data.count(ph_bytes)
        if count == 2:  # 本地文件头 + 中央目录各一次
            data = data.replace(ph_bytes, raw)
            changed = True
    if changed:
        with open(out_path, "wb") as f:
            f.write(data)


def verify_archive_names(archive_path, encoding="UTF-8", fmt="zip"):
    names = []
    if fmt == "tar.gz":
        with tarfile.open(archive_path, "r:gz", encoding=encoding) as tar:
            for member in tar.getmembers():
                names.append((member.name, member.name))
    elif fmt == "7z":
        import py7zr
        with py7zr.SevenZipFile(archive_path, "r") as z:
            for n in z.getnames():
                names.append((os.path.basename(n), os.path.basename(n)))
    elif fmt == "rar":
        found = _find_winrar()
        if not found:
            names.append((os.path.basename(archive_path),
                          "（校验 rar 文件名需安装 WinRAR）"))
        else:
            exe, _ = found
            try:
                creationflags = 0x08000000 if os.name == "nt" else 0
                proc = subprocess.run([exe, "lb", archive_path], capture_output=True,
                                      timeout=120, creationflags=creationflags)
                out = (proc.stdout or b"").decode("gbk", errors="replace")
                for line in out.splitlines():
                    line = line.strip()
                    if line:
                        names.append((line, line))
            except Exception:
                names.append((os.path.basename(archive_path), "（rar 校验失败）"))
    else:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                try:
                    if info.flag_bits & 0x800:
                        name = info.filename  # UTF-8 标志：zipfile 已正确解码
                    else:
                        name = info.filename.encode("cp437").decode(encoding)
                except Exception:
                    name = info.filename
                names.append((info.filename, name))
    return names


def _encode_name(filename, encoding):
    """兼容保留的旧接口：返回按目标编码字节经 cp437 反解的显示串（不用于写入）。"""
    try:
        raw = filename.encode(encoding)
        if raw.isascii() or encoding.upper() == "UTF-8":
            return filename
        return raw.decode("cp437")
    except Exception:
        return filename
