import os
import zipfile
import tarfile
import io


SUPPORTED_ENCODINGS = ["UTF-8", "GBK", "GB2312", "BIG5"]

SUPPORTED_FORMATS = ["zip", "tar.gz"]


def create_archive_with_encoding(file_list, out_path, encoding="UTF-8", fmt="zip"):
    if fmt == "tar.gz":
        with tarfile.open(out_path, "w:gz") as tar:
            for fpath in file_list:
                arcname = _encode_name(os.path.basename(fpath), encoding)
                tar.add(fpath, arcname=arcname)
    else:
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fpath in file_list:
                arcname = _encode_name(os.path.basename(fpath), encoding)
                zf.write(fpath, arcname=arcname)


def verify_archive_names(archive_path, encoding="UTF-8", fmt="zip"):
    names = []
    if fmt == "tar.gz":
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                try:
                    name = member.name.encode("utf-8").decode(encoding)
                except Exception:
                    name = member.name
                names.append((member.name, name))
    else:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                try:
                    name = info.filename.encode("cp437").decode(encoding)
                except Exception:
                    name = info.filename
                names.append((info.filename, name))
    return names


def _encode_name(filename, encoding):
    try:
        return filename.encode(encoding).decode("utf-8")
    except Exception:
        return filename