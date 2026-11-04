"""
Number plate texture for the AE86 model (hayate): a white Japanese-style private plate (330 x 165 mm) with a
fictional registration, green lettering, Noto Sans CJK JP (OFL). Deterministic; run on the host (needs PIL):

  python3 tools/blender/cars/hayate_textures.py   → tools/blender/textures/hayate/plate.png
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'textures', 'hayate')
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
FONT_B = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
JP = 0      # face index of Noto Sans CJK JP in the collection

W, H = 512, 256                     # 330 x 165 mm at ~1.55 px/mm
GREEN = (22, 84, 52)
WHITE = (244, 244, 238)


def text_c(d, xy, s, font, fill):
    l, t, r, b = d.textbbox((0, 0), s, font=font)
    d.text((xy[0] - (l + r) / 2, xy[1] - (t + b) / 2), s, font=font, fill=fill)


def plate():
    im = Image.new('RGB', (W, H), WHITE)
    d = ImageDraw.Draw(im)
    # rim and the two bolt holes
    d.rounded_rectangle((3, 3, W - 4, H - 4), radius=14, outline=GREEN, width=5)
    for x in (W * 0.22, W * 0.78):
        d.ellipse((x - 9, 24 - 9, x + 9, 24 + 9), fill=(200, 200, 196), outline=(150, 150, 146))
    # top line: area name and class number (fictional: 朧 300)
    f_top = ImageFont.truetype(FONT, 58, index=JP)
    text_c(d, (W * 0.50, 62), '朧 300', f_top, GREEN)
    # bottom line: hiragana and the four digits 12-34
    f_kana = ImageFont.truetype(FONT, 62, index=JP)
    text_c(d, (W * 0.11, 172), 'さ', f_kana, GREEN)
    f_num = ImageFont.truetype(FONT_B, 150, index=JP)
    l, t, r, b = d.textbbox((0, 0), '12-34', font=f_num)
    num = Image.new('L', (r - l + 8, b - t + 8), 0)
    ImageDraw.Draw(num).text((4 - l, 4 - t), '12-34', font=f_num, fill=255)
    # the digits are tall and narrow on real plates: squeeze them horizontally
    num = num.resize((int(num.width * 0.80), int(num.height * 0.92)), Image.LANCZOS)
    x0 = int(W * 0.58 - num.width / 2)
    y0 = int(172 - num.height / 2)
    im.paste(Image.new('RGB', num.size, GREEN), (x0, y0), num)
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    plate().save(os.path.join(OUT, 'plate.png'), optimize=True)
    print('wrote', os.path.join(OUT, 'plate.png'))


if __name__ == '__main__':
    main()
