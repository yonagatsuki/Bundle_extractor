#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_DEPS = ROOT / "work" / "pydeps"
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))

import UnityPy


# Windows 文件名不能包含这些字符，Unity 里的资源名有时会带 / 或特殊符号。
BAD_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def clean_name(name, default_name):
    #把 Unity 资源名整理成可以落盘的文件名。
    name = str(name or default_name).strip()
    name = BAD_FILENAME_CHARS.sub("_", name).rstrip(" .")
    return name[:180] or default_name


def get_asset_name(asset, default_name):
    #不同 UnityPy 对象字段名不完全一样，这里统一取资源名。
    return clean_name(
        getattr(asset, "name", None) or getattr(asset, "m_Name", None),
        default_name,
    )


def no_overwrite_path(path):
    #如果文件已存在，就自动加 _1、_2，避免覆盖之前导出的资源。
    if not path.exists():
        return path

    for i in range(1, 10000):
        new_path = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not new_path.exists():
            return new_path

    raise RuntimeError(f"too many duplicate file names: {path}")


def save_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path = no_overwrite_path(path)
    path.write_bytes(data)
    return path


def save_image(out_dir, folder, name, image):
    #Texture2D 和 Sprite 都可以转成 png，所以单独写一个小函数。
    path = no_overwrite_path(out_dir / folder / f"{name}.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def export_text_asset(out_dir, name, asset):
    # 旧版本 UnityPy 可能叫 script，新版对象里常见字段是 m_Script。
    text_data = getattr(asset, "script", None)
    if text_data is None:
        text_data = getattr(asset, "m_Script", b"")

    if isinstance(text_data, str):
        raw = text_data.encode("utf-8", "surrogateescape")
    else:
        raw = bytes(text_data)

    return save_bytes(out_dir / "TextAsset" / f"{name}.txt", raw)


def export_audio_clip(out_dir, name, asset):
    saved_count = 0

    # UnityPy 会把 AudioClip 解成 samples 字典，key 通常就是文件名。
    for sample_name, sample_data in (asset.samples or {}).items():
        file_name = clean_name(sample_name, name)
        if "." not in Path(file_name).name:
            file_name += ".wav"
        save_bytes(out_dir / "AudioClip" / file_name, sample_data)
        saved_count += 1

    return saved_count


def export_mesh(out_dir, name, obj, asset):
    # Mesh 能导 OBJ 就导 OBJ；失败就保留原始 bin，至少不丢数据。
    try:
        raw = asset.export().encode("utf-8", "replace")
        save_bytes(out_dir / "Mesh" / f"{name}.obj", raw)
    except Exception:
        save_bytes(out_dir / "Mesh_raw" / f"{name}.bin", obj.get_raw_data())


def export_as_json_or_raw(out_dir, type_name, name, obj, asset):
    # Material、MonoBehaviour 这类对象有时能读 typetree，有时不行。
    # 能读就保存 JSON；不能读就保存 raw bin。
    try:
        raw = json.dumps(asset.read_typetree(), ensure_ascii=False, indent=2).encode("utf-8")
        save_bytes(out_dir / type_name / f"{name}.json", raw)
    except Exception:
        save_bytes(out_dir / f"{type_name}_raw" / f"{name}.bin", obj.get_raw_data())


def export_one_object(obj, out_dir):
    #根据 Unity 对象类型，选择对应的导出方式。
    type_name = obj.type.name
    asset = obj.read()
    name = get_asset_name(asset, f"{type_name}_{obj.path_id}")

    if type_name == "Texture2D" and asset.image:
        save_image(out_dir, "Texture2D", name, asset.image)
        return 1

    if type_name == "Sprite" and asset.image:
        save_image(out_dir, "Sprite", name, asset.image)
        return 1

    if type_name == "AudioClip":
        return export_audio_clip(out_dir, name, asset)

    if type_name == "TextAsset":
        export_text_asset(out_dir, name, asset)
        return 1

    if type_name == "Mesh":
        export_mesh(out_dir, name, obj, asset)
        return 1

    if type_name in {"Material", "MonoBehaviour", "AnimationClip", "AnimatorController"}:
        export_as_json_or_raw(out_dir, type_name, name, obj, asset)
        return 1

    # 其他类型暂时跳过，比如 Transform、GameObject、Renderer 等。
    return 0


def export_bundle(bundle_path, out_dir):
    #读取一个 .bundle，并把能导出的 Unity 资源保存到 out_dir。
    env = UnityPy.load(str(bundle_path))
    type_counts = {}
    exported_count = 0
    errors = []

    for obj in env.objects:
        type_name = obj.type.name
        type_counts[type_name] = type_counts.get(type_name, 0) + 1

        try:
            exported_count += export_one_object(obj, out_dir)
        except Exception as error:
            errors.append({
                "type": type_name,
                "path_id": obj.path_id,
                "error": str(error),
            })

    return {
        "bundle": str(bundle_path),
        "object_counts": dict(sorted(type_counts.items())),
        "exported": exported_count,
        "error_count": len(errors),
        "errors": errors[:50],
    }


def find_bundle_files(input_path, recursive):
    #输入可以是单个 .bundle，也可以是一个目录。
    if input_path.is_file():
        yield input_path
        return

    pattern = "**/*.bundle" if recursive else "*.bundle"
    yield from input_path.glob(pattern)


def main():
    parser = argparse.ArgumentParser(description="Extract Unity .bundle files with UnityPy.")
    parser.add_argument("input", type=Path, help="a .bundle file or a directory")
    parser.add_argument("-o", "--out", type=Path, required=True, help="output directory")
    parser.add_argument("-r", "--recursive", action="store_true", help="scan directory recursively")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    summaries = []
    for bundle_path in find_bundle_files(args.input, args.recursive):
        print(f"extracting: {bundle_path}")

        # 每个 bundle 单独一个输出目录，避免不同 bundle 里的同名资源混在一起。
        bundle_out_dir = args.out / bundle_path.stem
        bundle_out_dir.mkdir(parents=True, exist_ok=True)

        summaries.append(export_bundle(bundle_path, bundle_out_dir))

    summary_file = args.out / "_summary.json"
    summary_file.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {summary_file}")


if __name__ == "__main__":
    main()
