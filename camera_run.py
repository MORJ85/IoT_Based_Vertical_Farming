import time
import csv
import os
import logging
import subprocess
from datetime import datetime0

import board
import busio
import numpy as np
import tifffile
import matplotlib
matplotlib.use("Agg")
import matplotlib.cm as cm

from flirpy.camera.lepton import Lepton
from PIL import Image, ImageDraw, ImageFont
from adafruit_bus_device.i2c_device import I2CDevice


# ============================================================
# SETTINGS
# ============================================================

SAVE_EVERY_SEC = 3600       # Every one hour
MASK_WARMUP_SEC = 120       # Primary time for building canopy mask
MIN_WARMUP_FRAMES = 30
LOOP_SLEEP_SEC = 1

CMAP_NAME = "inferno"
P_LOW = 2.0
P_HIGH = 98.0
PNG_SCALE = 4
MASK_PREVIEW_ALPHA = 0.45

RAW_TO_CELSIUS_SCALE = 100.0
KELVIN_OFFSET = 273.15

ROOT_DIR = "./plant_thermal_hourly"
RUN_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
RUN_DIR = os.path.join(ROOT_DIR, f"run_{RUN_TIMESTAMP}")
RAW_DIR = os.path.join(RUN_DIR, "raw_tiff")
PNG_DIR = os.path.join(RUN_DIR, "png")
MASK_DIR = os.path.join(RUN_DIR, "mask")
LOG_DIR = os.path.join(RUN_DIR, "logs")

for d in [RUN_DIR, RAW_DIR, PNG_DIR, MASK_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)

CSV_PATH = os.path.join(RUN_DIR, f"hourly_canopy_data_{RUN_TIMESTAMP}.csv")
LOG_PATH = os.path.join(LOG_DIR, "logger.log")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info("Camera run started")
logging.info(f"Run directory: {RUN_DIR}")


# ============================================================
# FFC HELPERS
# ============================================================

VIDEO_DEV_CANDIDATES = ["/dev/video0", "/dev/video1"]
PT1_XML = os.path.expanduser("~/purethermal1-uvc-capture/v4l2/uvcdynctrl/pt1.xml")
FFC_INTERVAL_SEC = 180
DISCARD_AFTER_FFC_FRAMES = 3

_ffc_device = None
_last_ffc_time = 0.0


def _v4l2_list_controls(dev):
    try:
        r = subprocess.run(
            ["v4l2-ctl", "-d", dev, "-l"],
            capture_output=True,
            text=True
        )
        return r.stdout or ""
    except Exception:
        return ""


def _has_run_ffc(dev):
    return "lep_cid_rad_run_ffc" in _v4l2_list_controls(dev)


def _try_import_pt1_xml(dev):
    if not os.path.exists(PT1_XML):
        return False

    try:
        subprocess.run(
            ["uvcdynctrl", "-d", dev, "-i", PT1_XML],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        return False


def _detect_ffc_device():
    for dev in VIDEO_DEV_CANDIDATES:
        if _has_run_ffc(dev):
            return dev

    for dev in VIDEO_DEV_CANDIDATES:
        _try_import_pt1_xml(dev)

    for dev in VIDEO_DEV_CANDIDATES:
        if _has_run_ffc(dev):
            return dev

    return None


def run_ffc_if_available(force=False):
    global _ffc_device, _last_ffc_time

    now = time.time()

    if (not force) and _last_ffc_time and (now - _last_ffc_time) < FFC_INTERVAL_SEC:
        return False

    if _ffc_device is None:
        _ffc_device = _detect_ffc_device()

    if _ffc_device is None:
        logging.warning("FFC control not available.")
        return False

    try:
        r = subprocess.run(
            ["v4l2-ctl", "-d", _ffc_device, "-c", "lep_cid_rad_run_ffc=1"],
            capture_output=True,
            text=True
        )

        if r.returncode != 0:
            logging.warning(f"FFC trigger failed: {r.stderr.strip()}")
            return False

        _last_ffc_time = now
        logging.info("FFC triggered")
        return True

    except Exception as e:
        logging.warning(f"FFC trigger exception: {e}")
        return False


# ============================================================
# IMAGE FUNCTIONS
# ============================================================

def raw_to_temp_c(raw_frame):
    return raw_frame.astype(np.float32) / RAW_TO_CELSIUS_SCALE - KELVIN_OFFSET


def choose_color_range(temp_c):
    vmin = float(np.percentile(temp_c, P_LOW))
    vmax = float(np.percentile(temp_c, P_HIGH))

    if vmax <= vmin:
        vmax = vmin + 1e-6

    return vmin, vmax


def thermal_to_rgb(temp_c, vmin, vmax):
    cmap = cm.get_cmap(CMAP_NAME)
    norm = np.clip((temp_c - vmin) / (vmax - vmin), 0.0, 1.0)
    return (cmap(norm)[..., :3] * 255).astype(np.uint8)


def save_png(img_array, path, scale=PNG_SCALE):
    img = Image.fromarray(img_array)

    if scale > 1:
        img = img.resize(
            (img.width * scale, img.height * scale),
            Image.Resampling.NEAREST
        )

    img.save(path)


def otsu_threshold(values, bins=256):
    values = values[np.isfinite(values)]

    if values.size == 0:
        return 0.0

    vmin = float(np.min(values))
    vmax = float(np.max(values))

    if vmax <= vmin:
        return vmin

    hist, bin_edges = np.histogram(values, bins=bins, range=(vmin, vmax))
    hist = hist.astype(np.float64)

    prob = hist / hist.sum()
    centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    omega = np.cumsum(prob)
    mu = np.cumsum(prob * centers)
    mu_t = mu[-1]

    denominator = omega * (1.0 - omega)
    denominator[denominator == 0] = np.nan

    sigma_b = ((mu_t * omega - mu) ** 2) / denominator
    idx = int(np.nanargmax(sigma_b))

    return float(centers[idx])


def majority_filter(mask, passes=2):
    result = mask.astype(bool)

    for _ in range(passes):
        padded = np.pad(result.astype(np.uint8), 1, mode="edge")

        neighbors = (
            padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:] +
            padded[1:-1, :-2] + padded[1:-1, 1:-1] + padded[1:-1, 2:] +
            padded[2:, :-2] + padded[2:, 1:-1] + padded[2:, 2:]
        )

        result = neighbors >= 5

    return result


def largest_component(mask):
    mask = mask.astype(bool)
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=bool)

    best_pixels = []

    for y in range(h):
        for x in range(w):
            if not mask[y, x] or visited[y, x]:
                continue

            stack = [(y, x)]
            visited[y, x] = True
            pixels = []

            while stack:
                cy, cx = stack.pop()
                pixels.append((cy, cx))

                for ny in (cy - 1, cy, cy + 1):
                    for nx in (cx - 1, cx, cx + 1):
                        if ny < 0 or ny >= h or nx < 0 or nx >= w:
                            continue
                        if mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))

            if len(pixels) > len(best_pixels):
                best_pixels = pixels

    output = np.zeros_like(mask, dtype=bool)

    for y, x in best_pixels:
        output[y, x] = True

    return output


def border_fraction(mask):
    h, w = mask.shape
    border = np.zeros_like(mask, dtype=bool)
    border[0, :] = True
    border[-1, :] = True
    border[:, 0] = True
    border[:, -1] = True

    return np.count_nonzero(mask & border) / max(1, np.count_nonzero(border))


def build_canopy_mask(mean_temp_c):
    threshold = otsu_threshold(mean_temp_c)

    candidates = []

    for side_name, raw_mask in [
        ("cooler", mean_temp_c <= threshold),
        ("warmer", mean_temp_c > threshold)
    ]:
        mask = majority_filter(raw_mask, passes=2)
        mask = largest_component(mask)
        mask = majority_filter(mask, passes=1)

        area_percent = 100.0 * np.count_nonzero(mask) / mask.size
        bfrac = border_fraction(mask)

        if 1.0 <= area_percent <= 90.0:
            candidates.append({
                "side": side_name,
                "mask": mask,
                "area_percent": area_percent,
                "border_fraction": bfrac
            })

    if not candidates:
        return None, {
            "status": "failed",
            "threshold_c": threshold,
            "selected_side": "NA",
            "area_percent": "NA",
            "border_fraction": "NA"
        }

    candidates.sort(key=lambda c: (c["border_fraction"], -c["area_percent"]))
    selected = candidates[0]

    return selected["mask"], {
        "status": "ok",
        "threshold_c": round(float(threshold), 3),
        "selected_side": selected["side"],
        "area_percent": round(float(selected["area_percent"]), 3),
        "border_fraction": round(float(selected["border_fraction"]), 3)
    }


def save_mask_diagnostics(mean_temp_c, canopy_mask, mask_info):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    vmin, vmax = choose_color_range(mean_temp_c)
    rgb = thermal_to_rgb(mean_temp_c, vmin, vmax)

    mask_img = (canopy_mask.astype(np.uint8) * 255)

    overlay = rgb.copy()
    overlay[canopy_mask] = (
        overlay[canopy_mask].astype(np.float32) * (1.0 - MASK_PREVIEW_ALPHA) +
        np.array([0, 255, 0], dtype=np.float32) * MASK_PREVIEW_ALPHA
    ).astype(np.uint8)

    save_png(rgb, os.path.join(MASK_DIR, f"startup_mean_thermal_{timestamp}.png"))
    save_png(mask_img, os.path.join(MASK_DIR, f"startup_canopy_mask_{timestamp}.png"))
    save_png(overlay, os.path.join(MASK_DIR, f"startup_canopy_overlay_{timestamp}.png"))

    info_path = os.path.join(MASK_DIR, f"startup_mask_info_{timestamp}.txt")

    with open(info_path, "w") as f:
        for k, v in mask_info.items():
            f.write(f"{k}: {v}\n")


def save_hourly_images(raw_frame, temp_c, canopy_mask, timestamp_name):
    raw_tiff_path = os.path.join(RAW_DIR, f"thermal_raw_{timestamp_name}.tiff")
    thermal_png_path = os.path.join(PNG_DIR, f"thermal_color_{timestamp_name}.png")
    overlay_png_path = os.path.join(PNG_DIR, f"thermal_canopy_overlay_{timestamp_name}.png")
    mask_png_path = os.path.join(PNG_DIR, f"canopy_mask_{timestamp_name}.png")

    tifffile.imwrite(raw_tiff_path, raw_frame.astype(np.uint16))

    vmin, vmax = choose_color_range(temp_c)
    rgb = thermal_to_rgb(temp_c, vmin, vmax)
    save_png(rgb, thermal_png_path)

    mask_img = (canopy_mask.astype(np.uint8) * 255)

    overlay = rgb.copy()
    overlay[canopy_mask] = (
        overlay[canopy_mask].astype(np.float32) * (1.0 - MASK_PREVIEW_ALPHA) +
        np.array([0, 255, 0], dtype=np.float32) * MASK_PREVIEW_ALPHA
    ).astype(np.uint8)

    save_png(mask_img, mask_png_path)
    save_png(overlay, overlay_png_path)

    return {
        "raw_tiff_path": raw_tiff_path,
        "thermal_png_path": thermal_png_path,
        "overlay_png_path": overlay_png_path,
        "mask_png_path": mask_png_path,
        "color_vmin_c": round(float(vmin), 3),
        "color_vmax_c": round(float(vmax), 3)
    }


# ============================================================
# SENSOR FUNCTIONS
# ============================================================

def read_hdc1080(hdc_device):
    try:
        with hdc_device:
            hdc_device.write(bytes([0x00]))
            time.sleep(0.015)
            temp_data = bytearray(2)
            hdc_device.readinto(temp_data)

            air_temp_c = ((temp_data[0] << 8) | temp_data[1]) * (165.0 / 65536.0) - 40.0

            hdc_device.write(bytes([0x01]))
            time.sleep(0.015)
            hum_data = bytearray(2)
            hdc_device.readinto(hum_data)

            rh = ((hum_data[0] << 8) | hum_data[1]) * (100.0 / 65536.0)

        air_temp_c = round(float(air_temp_c), 3)
        rh = round(float(rh), 3)

        if air_temp_c < -40 or air_temp_c > 85:
            return "NA", "NA", 0

        if rh < 0 or rh > 100:
            return "NA", "NA", 0

        return air_temp_c, rh, 1

    except Exception as e:
        logging.warning(f"HDC1080 error: {e}")
        return "NA", "NA", 0


def compute_vpd_kpa(air_temp_c, rh_percent):
    if air_temp_c == "NA" or rh_percent == "NA":
        return "NA"

    t = float(air_temp_c)
    rh = float(rh_percent)

    es = 0.6108 * np.exp((17.27 * t) / (t + 237.3))
    ea = es * rh / 100.0
    vpd = es - ea

    return round(float(vpd), 4)


def compute_features(temp_c, canopy_mask, air_temp_c, rh_percent):
    pixels = temp_c[canopy_mask]

    canopy_avg = round(float(np.mean(pixels)), 3)
    canopy_min = round(float(np.min(pixels)), 3)
    canopy_max = round(float(np.max(pixels)), 3)
    canopy_std = round(float(np.std(pixels)), 3)

    full_avg = round(float(np.mean(temp_c)), 3)
    full_min = round(float(np.min(temp_c)), 3)
    full_max = round(float(np.max(temp_c)), 3)

    canopy_pixel_count = int(pixels.size)
    canopy_cover = round(100.0 * canopy_pixel_count / temp_c.size, 3)

    vpd = compute_vpd_kpa(air_temp_c, rh_percent)

    if air_temp_c == "NA":
        ctd = "NA"
        cooling = "NA"
        et_index = "NA"
    else:
        ctd = round(canopy_avg - float(air_temp_c), 4)
        cooling = round(float(air_temp_c) - canopy_avg, 4)

        if vpd == "NA":
            et_index = "NA"
        else:
            et_index = round(max(0.0, cooling) * float(vpd), 4)

    return {
        "canopy_avg": canopy_avg,
        "canopy_min": canopy_min,
        "canopy_max": canopy_max,
        "canopy_std": canopy_std,
        "canopy_pixel_count": canopy_pixel_count,
        "canopy_cover": canopy_cover,
        "full_avg": full_avg,
        "full_min": full_min,
        "full_max": full_max,
        "vpd": vpd,
        "ctd": ctd,
        "cooling": cooling,
        "et_index": et_index
    }


# ============================================================
# MAIN CAMERA RUN
# ============================================================

def main():
    cam = None

    try:
        i2c_bus = busio.I2C(board.SCL, board.SDA)
        hdc_device = I2CDevice(i2c_bus, 0x40)
        hdc_enabled = True
        logging.info("HDC1080 initialized")
    except Exception as e:
        hdc_device = None
        hdc_enabled = False
        logging.warning(f"HDC1080 init failed: {e}")

    try:
        cam = Lepton()
        logging.info("FLIR initialized")
    except Exception as e:
        logging.error(f"FLIR init failed: {e}")
        return

    try:
        run_ffc_if_available(force=True)
        time.sleep(0.5)
    except Exception:
        pass

    warmup_frames = []
    warmup_start = time.time()

    print("Building canopy mask...")

    while True:
        elapsed = time.time() - warmup_start

        try:
            raw_frame = cam.grab().astype(np.uint16)
            temp_c = raw_to_temp_c(raw_frame)

            if -40 < float(np.mean(temp_c)) < 150:
                warmup_frames.append(temp_c)
        except Exception as e:
            logging.warning(f"Warmup FLIR error: {e}")

        print(f"Mask warmup: {int(elapsed)}s | frames: {len(warmup_frames)}")

        if elapsed >= MASK_WARMUP_SEC and len(warmup_frames) >= MIN_WARMUP_FRAMES:
            break

        time.sleep(1)

    mean_temp_c = np.mean(np.stack(warmup_frames, axis=0), axis=0)
    canopy_mask, mask_info = build_canopy_mask(mean_temp_c)

    if canopy_mask is None:
        print("Canopy mask failed. Using full frame.")
        canopy_mask = np.ones_like(mean_temp_c, dtype=bool)
    else:
        print("Canopy mask created:", mask_info)
        save_mask_diagnostics(mean_temp_c, canopy_mask, mask_info)

    csv_file = open(CSV_PATH, "w", newline="")
    writer = csv.writer(csv_file)

    writer.writerow([
        "Elapsed Time (s)",
        "Timestamp",
        "Canopy Avg Temp (C)",
        "Canopy Min Temp (C)",
        "Canopy Max Temp (C)",
        "Canopy Std Temp (C)",
        "Canopy Pixel Count",
        "Canopy Cover (%)",
        "Full Frame Avg Temp (C)",
        "Full Frame Min Temp (C)",
        "Full Frame Max Temp (C)",
        "Air Temp (C)",
        "Relative Humidity (%)",
        "VPD (kPa)",
        "CTD Canopy-Air (C)",
        "Canopy Cooling Air-Canopy (C)",
        "ET Index Relative",
        "Mask Status",
        "Mask Threshold (C)",
        "Mask Selected Side",
        "Mask Area (%)",
        "QC FLIR Valid",
        "QC HDC Valid",
        "Raw Thermal TIFF Path",
        "Thermal PNG Path",
        "Canopy Overlay PNG Path",
        "Canopy Mask PNG Path",
        "Color Vmin (C)",
        "Color Vmax (C)"
    ])

    csv_file.flush()

    start_time = time.time()
    last_save_time = 0

    print("Hourly logging started...")

    try:
        while True:
            now = time.time()
            elapsed_s = int(now - start_time)

            try:
                did_ffc = run_ffc_if_available(force=False)

                if did_ffc:
                    for _ in range(DISCARD_AFTER_FFC_FRAMES):
                        cam.grab()
                        time.sleep(0.02)

                raw_frame = cam.grab().astype(np.uint16)
                temp_c = raw_to_temp_c(raw_frame)

                qc_flir = 1

                if not (-40 < float(np.mean(temp_c)) < 150):
                    qc_flir = 0

            except Exception as e:
                logging.warning(f"FLIR read error: {e}")
                qc_flir = 0
                raw_frame = None
                temp_c = None

            if hdc_enabled:
                air_temp_c, rh_percent, qc_hdc = read_hdc1080(hdc_device)
            else:
                air_temp_c, rh_percent, qc_hdc = "NA", "NA", 0

            if qc_flir:
                features = compute_features(temp_c, canopy_mask, air_temp_c, rh_percent)
            else:
                features = {
                    "canopy_avg": "NA",
                    "canopy_min": "NA",
                    "canopy_max": "NA",
                    "canopy_std": "NA",
                    "canopy_pixel_count": 0,
                    "canopy_cover": "NA",
                    "full_avg": "NA",
                    "full_min": "NA",
                    "full_max": "NA",
                    "vpd": "NA",
                    "ctd": "NA",
                    "cooling": "NA",
                    "et_index": "NA"
                }

            print(
                f"{elapsed_s}s | "
                f"Tc={features['canopy_avg']} C | "
                f"Air={air_temp_c} C | "
                f"RH={rh_percent}% | "
                f"VPD={features['vpd']} | "
                f"ETidx={features['et_index']}"
            )

            should_save = (last_save_time == 0) or ((now - last_save_time) >= SAVE_EVERY_SEC)

            if should_save:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                timestamp_name = datetime.now().strftime("%Y%m%d_%H%M%S")

                if qc_flir:
                    image_paths = save_hourly_images(
                        raw_frame,
                        temp_c,
                        canopy_mask,
                        timestamp_name
                    )
                else:
                    image_paths = {
                        "raw_tiff_path": "NA",
                        "thermal_png_path": "NA",
                        "overlay_png_path": "NA",
                        "mask_png_path": "NA",
                        "color_vmin_c": "NA",
                        "color_vmax_c": "NA"
                    }

                writer.writerow([
                    elapsed_s,
                    timestamp,
                    features["canopy_avg"],
                    features["canopy_min"],
                    features["canopy_max"],
                    features["canopy_std"],
                    features["canopy_pixel_count"],
                    features["canopy_cover"],
                    features["full_avg"],
                    features["full_min"],
                    features["full_max"],
                    air_temp_c,
                    rh_percent,
                    features["vpd"],
                    features["ctd"],
                    features["cooling"],
                    features["et_index"],
                    mask_info.get("status", "NA"),
                    mask_info.get("threshold_c", "NA"),
                    mask_info.get("selected_side", "NA"),
                    mask_info.get("area_percent", "NA"),
                    qc_flir,
                    qc_hdc,
                    image_paths["raw_tiff_path"],
                    image_paths["thermal_png_path"],
                    image_paths["overlay_png_path"],
                    image_paths["mask_png_path"],
                    image_paths["color_vmin_c"],
                    image_paths["color_vmax_c"]
                ])

                csv_file.flush()
                last_save_time = now

                print("Saved:", timestamp)

            time.sleep(LOOP_SLEEP_SEC)

    except KeyboardInterrupt:
        print("Stopped manually.")

    finally:
        csv_file.close()

        if cam is not None:
            cam.close()

        logging.info("Camera run finished")


if __name__ == "__main__":
    main()
