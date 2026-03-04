import json
import random
from pathlib import Path
from collections import defaultdict

from ultralytics import YOLO
import shutil

ROOT = Path(__file__).resolve().parent
TRAIN_ROOT = ROOT / "yolo_train_data"
IMAGES_DIR = TRAIN_ROOT / "images"
META_FILE = TRAIN_ROOT / "annotations.jsonl"

DATASET_ROOT = ROOT / "yolo_dataset"
IMG_TRAIN = DATASET_ROOT / "images" / "train"
IMG_VAL = DATASET_ROOT / "images" / "val"
LBL_TRAIN = DATASET_ROOT / "labels" / "train"
LBL_VAL = DATASET_ROOT / "labels" / "val"

RANDOM_SEED = 42
VAL_FRACTION = 0.2  # 20 % av bilderna blir validering


def build_dataset():
    """
    Läser annotations.jsonl och bygger ett YOLO-dataset med train/val-split.

    - Ignorerar label "__IGNORE__"
    - Gruppar per bild, så alla boxar för samma bild hamnar i samma split
    - Skriver data.yaml med rätt train/val paths
    """
    if not META_FILE.exists():
        print("Hittar inte", META_FILE)
        return None, None

    # skapa mappar
    for p in [IMG_TRAIN, IMG_VAL, LBL_TRAIN, LBL_VAL]:
        p.mkdir(parents=True, exist_ok=True)
        for f in p.glob("*"):
            f.unlink()

    # 1) Läs alla records och gruppera per bild
    image_records = defaultdict(list)  # img_name -> [rec, rec, ...]
    with META_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            img_name = rec["image"]
            image_records[img_name].append(rec)

    if not image_records:
        print("Inga records hittades i", META_FILE)
        return None, None

    # 2) Klassnamn → id
    class_to_id = {}
    next_id = 0

    # 3) Slumpa train/val-split på bildnivå
    img_names = list(image_records.keys())
    random.Random(RANDOM_SEED).shuffle(img_names)

    n_val = max(1, int(len(img_names) * VAL_FRACTION)) if len(img_names) > 5 else 1
    val_set = set(img_names[:n_val])
    train_set = set(img_names[n_val:]) if len(img_names) > 1 else set()

    if not train_set:
        # Om väldigt få bilder, lägg alla i train men varna
        print("Väldigt få bilder – använder alla som train.")
        train_set = set(img_names)
        val_set = set()

    # För statistik
    class_counts = defaultdict(int)

    # 4) Skriv bilder + labels för train/val
    def process_split(split_names, img_dir, lbl_dir, split_name):
        nonlocal next_id
        for img_name in split_names:
            recs = image_records[img_name]

            # Hämta bildinfo från första recordet
            base = recs[0]
            w_img = base["width"]
            h_img = base["height"]
            src_img = IMAGES_DIR / img_name
            if not src_img.exists():
                print(f"[{split_name}] Saknar bild:", src_img)
                continue

            # Kopiera bild
            dst_img = img_dir / img_name
            shutil.copy2(src_img, dst_img)

            # Labels-fil
            txt_name = Path(img_name).with_suffix(".txt")
            lbl_path = lbl_dir / txt_name

            with lbl_path.open("w", encoding="utf-8") as lf:
                for rec in recs:
                    label = rec["label"]
                    if label == "__IGNORE__":
                        continue

                    bbox = rec["bbox"]  # {"x": x, "y": y, "w": w, "h": h}

                    # map label → class id
                    if label not in class_to_id:
                        class_to_id[label] = next_id
                        next_id += 1

                    cls_id = class_to_id[label]
                    class_counts[label] += 1

                    x = bbox["x"]
                    y = bbox["y"]
                    w = bbox["w"]
                    h = bbox["h"]

                    cx = (x + w / 2) / w_img
                    cy = (y + h / 2) / h_img
                    nw = w / w_img
                    nh = h / h_img

                    lf.write(f"{cls_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")

    process_split(train_set, IMG_TRAIN, LBL_TRAIN, "train")
    process_split(val_set, IMG_VAL, LBL_VAL, "val")

    if not class_to_id:
        print("Inga giltiga tränings-exempel hittades.")
        return None, None

    # 5) Skriv data.yaml
    data_yaml = DATASET_ROOT / "data.yaml"
    class_list = [None] * len(class_to_id)
    for name, idx in class_to_id.items():
        class_list[idx] = name

    with data_yaml.open("w", encoding="utf-8") as f:
        f.write(f"path: {DATASET_ROOT.as_posix()}\n")
        f.write("train: images/train\n")
        if val_set:
            f.write("val: images/val\n")
        else:
            f.write("val: images/train\n")  # fallback om inga val-bilder\n")
        f.write("names:\n")
        for idx, name in enumerate(class_list):
            f.write(f"  {idx}: {name}\n")

    print("Dataset klart.")
    print("Antal train-bilder:", len(train_set))
    print("Antal val-bilder:", len(val_set))
    print("Klasser:", class_list)
    print("Klass-fördelning:")
    for cls_name, cnt in class_counts.items():
        print(f" - {cls_name}: {cnt}")

    return data_yaml, class_list


def train_yolo(data_yaml):
    """
    Tränar YOLO med:
      - start från pti_best.pt om den finns (inkrementell träning)
      - annars från yolov8n.pt
      - enklare augmentation / bättre imgsz
    """
    # startmodell: om du redan har tränat en, fortsätt därifrån
    pti_path = ROOT / "pti_best.pt"
    if pti_path.exists():
        print("Laddar befintlig modell:", pti_path)
        model = YOLO(str(pti_path))
    else:
        print("Ingen pti_best.pt hittad – startar från yolov8n.pt")
        model = YOLO("yolov8n.pt")

    results = model.train(
        data=str(data_yaml),
        epochs=40,          # lite fler, du har få bilder
        imgsz=960,          # större input, bättre på små skador
        batch=8,
        patience=8,         # stoppa om val-loss inte förbättras
        # Några augmentation-parametrar (rimliga default för industri)
        degrees=5.0,
        scale=0.10,
        shear=2.0,
        flipud=0.0,        # containers upp-och-ned är orimligt :)
        fliplr=0.5,        # horisontell flip kan vara okej
    )

    # Ultralytics sparar normalt weights/best.pt i runs/detect/train*/weights/best.pt
    best = Path(results.save_dir) / "weights" / "best.pt"
    if best.exists():
        dst = ROOT / "pti_best.pt"
        shutil.copy2(best, dst)
        print("Ny modell sparad som:", dst)
    else:
        print("Kunde inte hitta best.pt efter träning.")


def main():
    data_yaml, classes = build_dataset()
    if data_yaml is None:
        return
    print("Startar YOLO-träning...")
    train_yolo(data_yaml)
    print("KLART.")


if __name__ == "__main__":
    main()
