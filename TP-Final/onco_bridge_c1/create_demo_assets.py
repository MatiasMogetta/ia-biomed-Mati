"""Crea una imagen no médica para comprobar que C2 responde de extremo a extremo."""
from pathlib import Path

from PIL import Image, ImageDraw


OUTPUT = Path(__file__).resolve().parent / "demo_assets" / "non_medical_test_image.png"


def main() -> None:
    OUTPUT.parent.mkdir(exist_ok=True)
    image = Image.new("L", (768, 768), color=25)
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 688, 688), outline=180, width=6)
    draw.line((80, 80, 688, 688), fill=120, width=4)
    draw.line((688, 80, 80, 688), fill=120, width=4)
    draw.text((205, 350), "NON-MEDICAL TEST IMAGE", fill=255)
    draw.text((245, 385), "EXPECT: NOT EVALUABLE", fill=220)
    image.save(OUTPUT)
    print(f"Creada: {OUTPUT}")


if __name__ == "__main__":
    main()
