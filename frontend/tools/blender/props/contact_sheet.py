#!/usr/bin/env python3
"""<render dir>: contact_sheet.png from the *_main.png renders of the eight props (host python3 + PIL)"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

NAMES = [('street_light', '街路灯 street light'), ('wind_turbine', '風車 wind turbine'), ('curve_mirror', 'カーブミラー curve mirror'),
         ('vending_machine', '自販機 vending machine'), ('torii', '鳥居 torii'), ('stone_lantern', '灯籠 stone lantern'),
         ('bus_stop', 'バス停 bus shelter'), ('traffic_cone', 'コーン traffic cone')]
d = sys.argv[1]
T = (480, 420)
f = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc', 20, index=0)
sheet = Image.new('RGB', (T[0] * 4, T[1] * 2), (30, 30, 34))
dr = ImageDraw.Draw(sheet)
for i, (n, label) in enumerate(NAMES):
    p = os.path.join(d, f'{n}_main.png')
    if not os.path.exists(p):
        continue
    im = Image.open(p)
    k = min(T[0] / im.width, (T[1] - 30) / im.height)
    im = im.resize((int(im.width * k), int(im.height * k)))
    x, y = (i % 4) * T[0], (i // 4) * T[1]
    sheet.paste(im, (x + (T[0] - im.width) // 2, y + 30))
    dr.text((x + 10, y + 4), label, font=f, fill=(230, 230, 230))
sheet.save(os.path.join(d, 'contact_sheet.png'))
