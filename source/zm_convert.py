# zm_convert.py — Zeta Motion
# Conversion utilities (HD -> proxy), naming helpers and swap logic.
# Designed to be minimal-impact and callable from zm_movie and zm_ui.

import os
import threading
import tempfile
import shutil
from PIL import Image
import bpy

# JPEG quality for proxies
DEFAULT_QUALITY = 85

# Map scale string to float
SCALE_MAP = {
    '25': 0.25,
    '50': 0.50,
    '75': 0.75,
}

# Helper: produce proxy filename in same dir
# Example: /path/mipeli_HD_00001.jpg -> /path/mipeli_25_00001.jpg

def get_scaled_name(hd_path, scale_label):
    dirn = os.path.dirname(hd_path)
    base = os.path.basename(hd_path)
    name, ext = os.path.splitext(base)

    # normalize name - remove existing _HD or _25/_50/_75 or _sml
    # Strategy: try to strip suffix tokens we use
    tokens = name.split('_')
    # remove trailing known tokens
    if tokens[-1] in ('HD', 'sml') or tokens[-1] in ('25', '50', '75'):
        tokens = tokens[:-1]
    # If name ends with numeric index like 00001, keep it
    new_name = '_'.join(tokens)

    return os.path.join(dirn, f"{new_name}_{scale_label}_{tokens[-1] if tokens[-1].isdigit() else '00001'}" + ext)


def get_hd_name(filepath):
    # Ensure the HD filename uses `_HD_` token before the index
    dirn = os.path.dirname(filepath)
    base = os.path.basename(filepath)
    name, ext = os.path.splitext(base)
    tokens = name.split('_')
    if 'HD' in tokens:
        return filepath
    # try to find trailing numeric token
    if tokens and tokens[-1].isdigit():
        idx = tokens[-1]
        core = '_'.join(tokens[:-1]) if len(tokens) > 1 else tokens[0]
        return os.path.join(dirn, f"{core}_HD_{idx}{ext}")
    else:
        # fallback
        return os.path.join(dirn, f"{name}_HD{ext}")


def _atomic_save(img: Image.Image, dest_path: str, quality:int=DEFAULT_QUALITY):
    # save to temp then atomically replace
    dirn = os.path.dirname(dest_path)
    fd, tmp = tempfile.mkstemp(suffix=".jpg", dir=dirn)
    os.close(fd)
    try:
        img.save(tmp, "JPEG", quality=int(quality), optimize=True)
        os.replace(tmp, dest_path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def convert_image(hd_path, scale_label, quality=DEFAULT_QUALITY):
    """
    Convert hd_path into a proxy at scale_label ('25','50','75').
    Returns proxy_path on success, None on failure.
    This function is safe to call from a background thread.
    """
    if not os.path.exists(hd_path):
        print(f"[Zeta Motion][Convert] HD not found: {hd_path}")
        return None

    scale = SCALE_MAP.get(str(scale_label), 0.5)
    try:
        with Image.open(hd_path) as img:
            w, h = img.size
            tw = max(1, int(w * scale))
            th = max(1, int(h * scale))

            # copy and thumbnail to be memory-friendly
            img_copy = img.copy()
            img_copy.thumbnail((tw, th), Image.LANCZOS)

            if img_copy.mode not in ("RGB", "L"):
                img_copy = img_copy.convert("RGB")

            # build proxy filename: base_{scale}_{index}.jpg
            # We'll try to preserve the trailing index token if present
            base = os.path.basename(hd_path)
            name, ext = os.path.splitext(base)
            tokens = name.split('_')
            idx = '00001'
            if tokens and tokens[-1].isdigit():
                idx = tokens[-1]
                core = '_'.join(tokens[:-1])
            else:
                core = name

            proxy_name = f"{core}_{scale_label}_{idx}{ext}"
            proxy_path = os.path.join(os.path.dirname(hd_path), proxy_name)

            _atomic_save(img_copy, proxy_path, quality=quality)
            print(f"[Zeta Motion][Convert] Proxy created: {proxy_path} ({tw}x{th})")
            return proxy_path
    except Exception as e:
        print(f"[Zeta Motion][Convert] Failed to convert {hd_path}: {e}")
        return None


def convert_image_async(hd_path, scale_label, quality=DEFAULT_QUALITY, callback=None):
    """Start conversion in a background thread. callback(proxy_path) is invoked in main thread via bpy.app.timers.register.
    callback will be called with a single argument: proxy_path (or None).
    """
    def _worker():
        proxy = convert_image(hd_path, scale_label, quality)
        if callback:
            # schedule callback on main thread
            def _cb():
                try:
                    callback(proxy)
                except Exception as e:
                    print(f"[Zeta Motion][Convert] callback failed: {e}")
                return None
            try:
                bpy.app.timers.register(_cb, first_interval=0.01)
            except Exception as e:
                print(f"[Zeta Motion][Convert] Failed scheduling callback: {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


# ----------------------------
# Swap helper: recreate strip pointing to proxy or HD
# ----------------------------

def find_strip_by_base(scene, base_name):
    seq = getattr(scene, 'sequence_editor', None)
    if not seq:
        return None
    for s in seq.sequences_all:
        if s.name == base_name:
            return s
    return None


def swap_strip_resolution(context, strip_name=None, use_proxy=True, scale_label=None):
    """
    Swap the resolution target of the strip identified by strip_name (or scene.zm_preview_strip_name like logic).
    If use_proxy is True, try to point the recreated strip to proxy; otherwise to HD.
    This function must be called in main thread.
    Returns new_strip or None.
    """
    scene = context.scene

    # If no strip_name provided, try to use stored name for movie strips: use a heuristic
    if not strip_name:
        print("[Zeta Motion][Swap] strip_name not provided")
        return None

    seq = getattr(scene, 'sequence_editor', None)
    if not seq:
        print("[Zeta Motion][Swap] No sequence editor")
        return None

    # find old strip
    old = None
    for s in seq.sequences_all:
        if s.name == strip_name:
            old = s
            break
    if not old:
        print(f"[Zeta Motion][Swap] strip '{strip_name}' not found")
        return None

    # determine base_name from strip elements; use filename without scale tokens
    try:
        elem_fn = old.elements[0].filename
    except Exception:
        print("[Zeta Motion][Swap] cannot read element filename")
        return None

    # construct counterparts
    dirn = os.path.dirname(bpy.path.abspath(old.filepath)) if getattr(old, 'filepath', None) else os.path.dirname(bpy.path.abspath(scene.zm_capture_path))
    # try to infer core name and index
    name, ext = os.path.splitext(elem_fn)
    tokens = name.split('_')
    idx = tokens[-1] if tokens[-1].isdigit() else '00001'
    # core assumption: tokens before index compose the base
    core = '_'.join(tokens[:-1]) if tokens[-1].isdigit() else tokens[0]

    hd_candidate = os.path.join(dirn, f"{core}_HD_{idx}{ext}")
    proxy_candidate = None
    if scale_label:
        proxy_candidate = os.path.join(dirn, f"{core}_{scale_label}_{idx}{ext}")
    else:
        # try detect any proxy in folder 25/50/75
        for sfx in ('25','50','75'):
            p = os.path.join(dirn, f"{core}_{sfx}_{idx}{ext}")
            if os.path.exists(p):
                proxy_candidate = p
                break

    target_path = proxy_candidate if use_proxy and proxy_candidate and os.path.exists(proxy_candidate) else hd_candidate
    if not os.path.exists(target_path):
        print(f"[Zeta Motion][Swap] target not found: {target_path}")
        return None

    # snapshot props
    props = None
    try:
        import zm_properties
        props = zm_properties.store_strip_properties(old)
    except Exception:
        props = None

    channel = getattr(old, 'channel', 1)
    frame_start = getattr(old, 'frame_start', scene.frame_current)
    frame_duration = getattr(old, 'frame_final_duration', 1)

    # destroy old
    try:
        seq.sequences.remove(old)
    except Exception as e:
        print(f"[Zeta Motion][Swap] failed to remove old strip: {e}")

    # create new strip using existing helper: new_image with filepath set
    try:
        new_strip = scene.sequence_editor.sequences.new_image(
            name=core,
            filepath=target_path,
            channel=channel,
            frame_start=frame_start,
        )
        # set duration
        try:
            new_strip.frame_final_duration = frame_duration
        except Exception:
            pass
        # apply props if available
        if props:
            try:
                import zm_properties
                zm_properties.apply_strip_properties(new_strip, props)
            except Exception:
                pass
        print(f"[Zeta Motion][Swap] Recreated strip '{new_strip.name}' -> {target_path}")
        return new_strip
    except Exception as e:
        print(f"[Zeta Motion][Swap] failed to create new strip: {e}")
        return None
