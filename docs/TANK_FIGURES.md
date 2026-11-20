# Tank figures: checked against published sources (2026-11-18)

The tanks' figures in `frontend/src/game/vehicle/tanks.ts` were first written from memory. Each one was looked up
on 2026-11-18. Verdicts:

- **same**: a published source gives the code's value.
- **corrected**: the published value differs; the code now has it.
- **disagree**: published sources differ; the table says which one was taken and why.
- **not found**: nothing published was found; the value stays an estimate (`estimated` in the code, （推定） on the
  spec sheet) and the table gives the basis.

"Secondary" means a reference work (Wikipedia, an encyclopaedia table, a trade site) that names no primary source
for the figure; a primary source (army, ministry, maker) is named where one could be read. The Japanese ministry's
pages (`mod.go.jp/gsdf/…`, the 主要装備 one-sheet PDF) refused automated reading (403 / 404). So the Japanese
figures rest on secondary sources that agree with each other and with the ministry's rounded figures where those
appeared in search excerpts.

The figures the simulation does not use (height, range, fuel) are left out unless they show on the spec sheet.

## 10式戦車 (type10)

| Figure | Code before | Published | Source | Verdict |
|---|---|---|---|---|
| Mass (全備重量) | 44 t | 約44 t (base 40 t, full load 48 t) | ja.wikipedia 10式戦車 (https://ja.wikipedia.org/wiki/10式戦車); 乗りものニュース (https://trafficnews.jp/post/78637); en.wikipedia Type 10 (https://en.wikipedia.org/wiki/Type_10) | same |
| Engine | 水冷4サイクル V型8気筒ディーゼル (8VA34WTK) | same, 22.6 L | ja / en.wikipedia | same |
| Power | 1,200 PS / 2,300 rpm | 1,200 ps / 2,300 rpm | ja.wikipedia (infobox) | same |
| Torque curve | 3,666 N·m at 2,300 rpm, peak 4,200 estimated | not published | (none found) | not found: rated torque follows from the power; the curve stays an estimate |
| Transmission | HMT (油圧機械式無段変速) | 油圧機械式無段階自動変速操向機（HMT） | ja.wikipedia | same |
| Top speed fwd / rev | 70 / 70 km/h | 70 km/h 前進・後進 | ja.wikipedia (cites the 富士学校 open day's announcement); en.wikipedia (cites a JGSDF demonstration video and Army Recognition) | same |
| Length over gun / width | 9.42 m / 3.24 m | 9.42 m / 3.24 m (en.wikipedia: 9.485 m) | ja.wikipedia; 乗りものニュース (約9.4 m / 約3.2 m) | same (9.485 m is an outlier) |
| Crew | 3 | 3 | ja / en.wikipedia | same |
| Suspension | hydropneumatic (comment) | 油気圧式 | ja.wikipedia | same |
| Gun | 44口径120mm滑腔砲 (日本製鋼所) | 10式戦車砲（44口径120mm滑腔砲）, JSW | ja / en.wikipedia | same |
| Round | 10式120mm APFSDS | 国産の新型徹甲弾 (APFSDS) | ja.wikipedia; MOF budget audit report (cited by en.wikipedia) | same |
| Muzzle velocity | 1,650 m/s (estimated: the JM33's) | 10式 APFSDS: not published. JM33 = DM33 ≈ 1,650 m/s from the L/44 (one table: 1,640) | de.wikipedia Leopard 2, Munitionstypen (https://de.wikipedia.org/wiki/Leopard_2); en.wikipedia 120×570mm NATO (https://en.wikipedia.org/wiki/120×570mm_NATO) | not found: stays estimated (the JM33's figure, a lower bound) |
| Shot / charge (recoil) | 7.3 kg / 7.6 kg (estimated: JM33) | DM33: 7.3 kg sub-projectile with sabot, ~7.6 kg propellant | en.wikipedia 120×570mm NATO (table) | not found for the 10式 round: stays estimated (the JM33's, secondary) |
| Rounds carried (gun's `ammo`) | 14 (estimated) | autoloader 14 (軍事研究 2008); 22 ready (PANZER 2008: 14 + 2 + 6); 36 total (WeaponSystems.net) | ja / en.wikipedia with those citations | not found officially: stays 14 = the autoloader's reported load (the other rounds cannot be loaded on the move) |
| Reload | 4 s (estimated) | not published. en.wikipedia: "fire every 3.5 seconds" from a social-media post of firing training | en.wikipedia (cites a post, not an official figure) | not found: stays 4 s (the 90式's usual figure); 3.5 s is noted but is not an official figure |
| Elevation limits | −7° / +10° (estimated: 90式) | not published (90式 too: ja.wikipedia says only that the range is narrow and the suspension's tilt makes up for it) | ja.wikipedia 90式戦車 | not found: stays estimated |
| Traverse / elevation rate | 40 °/s / 15 °/s (estimated) | not published | — | not found: stays estimated |
| Sight magnification | 4× / 10× (estimated) | not published | — | not found: stays estimated |
| Drag (`dropPerKm`) | 60 m/s per km (estimated) | not published | — | not found: stays estimated |
| Track contact / gauge / clearance | 4.3 / 2.7 / 0.45 m | not published | — | not found (sim geometry, not on the spec sheet) |
| Gun's places (`dims`: ring, trunnions, barrel, sight) | ring z 0.2 / y 1.75, trunnions 0.35 above and 1.47 ahead, barrel 4.0 (muzzle 5.67 m ahead of the middle) | not published | measured on six Commons photographs through solved cameras (`tools/blender/tanks/fitdata/type10`: the road wheels' ground contacts give the origin, 9.42 m over the gun the length) | **from our model (2026-11-19)**: ring z −0.02 / y 1.55, trunnions 0.42 above and 1.42 ahead (1.97 m up), barrel 4.31 (muzzle 5.71 m ahead, hull rear −3.71); sight head = the model's forward roof hood [0.82, 0.815, 1.13] in the turret's frame (0.40 m above, 0.82 m left of the bore; the fire control converges the gun on the line of sight at the lased range); five road wheels at 1.06 m pitch |
| Pivot rate | 30 °/s | not published (ja.wikipedia: turns on half the 90式's radius) | — | not found (sim value, not on the spec sheet) |

## 16式機動戦闘車 (type16)

| Figure | Code before | Published | Source | Verdict |
|---|---|---|---|---|
| Mass | 26 t | 約26 t (26 t以下) | ja.wikipedia 16式機動戦闘車 (https://ja.wikipedia.org/wiki/16式機動戦闘車); en.wikipedia (https://en.wikipedia.org/wiki/Type_16_maneuver_combat_vehicle) | same |
| Length / width | 8.45 m / 2.98 m | 8.45 m / 2.98 m (MOD one-sheet in a search excerpt: 約8.5 m / 約3 m) | ja / en.wikipedia; 防衛省「主要装備」one-sheet (https://www.mod.go.jp/j/press/book/one_sheet/pdf/introduction_of_major_equipment.pdf, excerpt only) | same |
| Engine | 水冷4サイクル 直列4気筒ターボディーゼル | 4-cylinder water-cooled turbocharged diesel 11.3 L (三菱 4VA) | en.wikipedia; ja.wikipedia (ターボチャージド・ディーゼル) | same |
| Power | 570 PS / 2,100 rpm | 570 ps / 2,100 rpm | ja.wikipedia | same |
| Torque curve | 1,906 N·m at 2,100 rpm, rest estimated | not published | — | not found: stays estimated |
| Top speed | 100 km/h | 約100 km/h (ja.wikipedia: 100 km/h以上) | MOD one-sheet excerpt; ja / en.wikipedia | same |
| Transmission | automatic, 6 speeds (estimated) | automatic, gears not published | ja.wikipedia | gear count not found: stays estimated |
| Reverse speed | 20 km/h (estimated) | not published | — | not found: stays estimated |
| Steering | front two axles | 前方2軸 | ja.wikipedia | same |
| Crew | 4 | 4 | MOD one-sheet excerpt; ja / en.wikipedia | same |
| Gun | 52口径105mmライフル砲 (JSW) | 105 mm L/52, JSW, loaded by hand | ja / en.wikipedia | same |
| Round | 93式105mm APFSDS | 93式105mm装弾筒付翼安定徹甲弾 (also 91式 HEAT-MP) | ja.wikipedia | same |
| Muzzle velocity | 1,500 m/s (estimated) | not published | — | not found: stays estimated |
| Shot / charge | 5.8 / 5.6 kg (estimated) | not published | — | not found: stays estimated |
| Rounds carried | 40 (estimated) | not published | — | not found: stays estimated |
| Reload | 6 s (estimated) | not published | — | not found: stays estimated |
| Elevation, traverse, rates, sight | −6° / +15°, 40 °/s, 15 °/s, 4× / 8× (estimated) | not published | — | not found: stays estimated |
| Wheelbase / track / wheel radius | 4.6 / 2.55 / 0.6 m | not published | — | not found (sim geometry) |

## Leopard 2A5 (leopard2a5)

| Figure | Code before | Published | Source | Verdict |
|---|---|---|---|---|
| Combat weight | 59.7 t | 59.5 t (Bundeswehr data table: empty 57.3 t, combat 59.5 t; en.wikipedia 59.5 t); 59.7 t (de.wikipedia infobox); 62 t (KNDS); 55.4–62.5 t (Army Recognition) | de.wikipedia Leopard 2, Technische Daten (https://de.wikipedia.org/wiki/Leopard_2); en.wikipedia (https://en.wikipedia.org/wiki/Leopard_2); KNDS (https://knds.com/en/products/leopard/leopard-2A5) | **corrected → 59.5 t**: the German army's figure, two references agree; KNDS's 62 t covers the heavier export builds |
| Engine | MTU MB 873 Ka-501 V12 twin-turbo 47.6 L | same, 47.6 L | de.wikipedia; Army Recognition (https://www.armyrecognition.com/military-products/army/main-battle-tanks/main-battle-tanks/leopard-2a5-mbt-main-battle-tank-technical-data-sheet-specifications-pictures-video-12502163) | same |
| Power | 1,500 PS (1,103 kW) / 2,600 rpm | 1,500 PS (1,100 kW) / 2,600 rpm | de / en.wikipedia; Army Recognition; KNDS (1,500 HP / 1,100 kW) | same |
| Torque | 4,700 N·m at 1,600–1,700 rpm | 4,700 N·m at 1,600 (–1,700) rpm | de / en.wikipedia | same (the rest of the curve stays an estimate) |
| Transmission | Renk HSWL 354, 4 fwd / 2 rev | same | en.wikipedia; Army Recognition | same (ratios not published: estimated) |
| Top speed | 68 km/h | ≤ 70 km/h (KNDS, the maker); 68 km/h (en.wikipedia text); 70 (en infobox); 72 km/h (Army Recognition; de: 2A4) | KNDS; en / de.wikipedia; Army Recognition | **corrected → 70 km/h**: the maker's own figure for the A5 (72 belongs to the lighter A4) |
| Reverse speed | 31 km/h | 31 km/h | en.wikipedia; Army Recognition | same |
| Length over gun | 9.97 m | 9.67 m, turret forward (KNDS; de.wikipedia infobox "bis A5"; Army Recognition); 9.97 m (en.wikipedia, for the A4) | KNDS; de.wikipedia; Army Recognition | **corrected → 9.67 m** (the maker): the muzzle 5.81 m ahead of the middle, `barrel` 4.11 → 3.81 m |
| Width | 3.75 m | 3.76 m (Bundeswehr table, de.wikipedia), 3.77 m (Army Recognition), 3.67 m (KNDS) | as above | disagree: **3.76 m** taken (the Bundeswehr's figure; KNDS's 3.67 m is likely without the A5's skirts) |
| Hull length | 7.72 m | not found in the sources read | — | not found (kept) |
| Crew | 4 | 4 (loader by hand) | de / en.wikipedia | same |
| Gun | Rh-120 L/44 | 120 mm L/44 | KNDS; de.wikipedia | same |
| Round / muzzle velocity | DM53, 1,670 m/s | DM53: 1,670 m/s (L/44), 1,750 m/s (L/55) | de.wikipedia Munitionstypen; Defense Update (https://defense-update.com/?p=10492) | same |
| Shot / charge | 8.35 kg / 8.9 kg | 8.35 kg sub-projectile with sabot, ~8.9 kg L1 propellant | en.wikipedia 120×570mm NATO | same (secondary) |
| Rounds carried | 42 | 42: 15 in the turret bustle, 27 in the hull | de / en.wikipedia; Army Recognition | same |
| Elevation limits | −9° / +20° | −9° / +20° | de / en.wikipedia | same |
| Turret traverse | 40 °/s (360° in 9 s) | 360° in 9 s (electric) | de.wikipedia, Technische Daten | same |
| Elevation rate | 15 °/s (estimated) | not found | — | not found: stays estimated |
| Reload | 6 s (estimated) | no official figure; de.wikipedia: "realistisch vier bis sechs Schuss/Minute" (sustained) | de.wikipedia | not found: stays estimated |
| Sight magnification | 4× / 12× | EMES 15: 12× main sight; the thermal channel's 4× not confirmed | de.wikipedia (Zielgeräte) | 12× same; 4× not found (kept as the low setting) |
| Track contact 4.95 m / gauge 3.1 m / clearance 0.54 m | — | clearance 540 mm (falling to 500 mm, A4 column of the de table); contact length and gauge not found | de.wikipedia | clearance same; the rest not found |
| Pivot rate | 30 °/s (estimated) | not found | — | not found: stays estimated |

## M1A2 SEPv3 (m1a2)

| Figure | Code before | Published | Source | Verdict |
|---|---|---|---|---|
| Mass | 66.8 t | 73.6 short tons (66.8 t) | en.wikipedia M1 Abrams (https://en.wikipedia.org/wiki/M1_Abrams), citing ASA(ALT) Weapon Systems Handbook 2018 | same |
| Engine / power | Honeywell AGT1500, 1,500 shp | 1,500 shp recuperated gas turbine | Honeywell AGT1500 brochure (https://www.honeywellaerospace.com/content/dam/aerobt/en/documents/landing-pages/brochures/AGT1500-Turbine-Engine-Brochure.pdf); GDLS (https://www.gdls.com/m1a2-sepv3/) | same |
| Output speed / torque | 3,000 rpm, 3,560 N·m there; 5,355 N·m (3,950 lb·ft) at 1,000 rpm | 1,500 shp at 3,000 rpm; 2,750 lb·ft (3,730 N·m) "at that peak" | en.wikipedia Honeywell AGT1500 (https://en.wikipedia.org/wiki/Honeywell_AGT1500), citing Honeywell's archived product pages | disagree: 2,750 lb·ft at 3,000 rpm would be 1,571 shp, 5 % over Honeywell's own 1,500 shp: the power is kept (3,560 N·m). The 3,950 lb·ft low-speed figure was **not found** in any source read: it stays an estimate (noted in the code) |
| Transmission | Allison X1100-3B, 4 fwd / 2 rev | X-1100-3B, 4 forward, 2 reverse | en.wikipedia; Gary's Combat Vehicle Reference Guide (https://www.inetres.com/gp/military/cv/tank/M1.html) | same |
| Top speed | 67.6 km/h (42 mph, governed) | 42 mph (67 km/h), governed | en.wikipedia (citing the Army's fact file) | same |
| Reverse speed | 40 km/h (estimated) | not published | — | not found: stays estimated (25 mph is the usual secondary figure) |
| Length over gun | 9.83 m | 9.77 m (32.04 ft, the Army's fact file); 9.83 m (other references) | en.wikipedia (citing the fact file); Defense Watch / databases 9.83 m | disagree: **9.77 m** taken (the Army's own fact file): `barrel` 3.78 → 3.72 m |
| Hull length / width | 7.93 m / 3.66 m | 7.93 m / 3.66 m (12 ft) | en.wikipedia | same |
| Crew | 4 | 4 | en.wikipedia | same |
| Gun | M256 L/44 120 mm | M256 (M256A1) 120 mm L/44 smoothbore | en.wikipedia | same |
| Muzzle velocity | 1,555 m/s (estimated: M829A3) | M829A4: not published. M829A3: 1,552.5 m/s (Northrop Grumman's sheet); 1,555 m/s (encyclopaedias) | Northrop Grumman, 120mm M829A3 (https://www.fbcinc.com/source/Northrop_Resources/120mm_M829A3.pdf) | **corrected → 1,552.5 m/s** (the maker's figure for the stand-in round); stays marked estimated, as the A4's own is not published |
| Shot / charge | 10 kg / 8.1 kg | 10.0 kg projectile, 8.15 kg RPD-380 stick propellant | Northrop Grumman M829A3 sheet | shot same; **charge corrected → 8.15 kg** |
| Rounds carried | 42 | 40 (M1A1), 42 (M1A2) | en.wikipedia; Gary's guide | same (secondary; a SEPv3-specific figure was not found) |
| Elevation limits | −10° / +20° | −10° / +20° (Hunnicutt 2015, p. 306); −9° / +20° (en.wikipedia text) | en.wikipedia | disagree: −10° kept (the cited book) |
| Turret traverse | 40 °/s | 360° in 9 s | en.wikipedia (Hunnicutt 2015, p. 306) | same |
| Elevation rate | 15 °/s (estimated) | not found | — | not found: stays estimated |
| Reload | 6 s (estimated) | not published | — | not found: stays estimated |
| Sight magnification | 3× / 10× | GPS: 3× and 10× (day and thermal) | Gary's guide (secondary) | same (secondary) |
| Track contact / gauge / clearance | 4.6 / 2.9 / 0.48 m | clearance 0.43 m (M1A2), 0.48 m (M1/M1A1) | en.wikipedia | clearance disagrees slightly: 0.48 kept (sim geometry, not on the spec sheet); contact length / gauge not found |
| Pivot rate | 30 °/s (estimated) | not found | — | not found: stays estimated |

## T-14 Armata (t14)

Little is published by the maker. The first official weight and dimensions were given at Army-2019.

| Figure | Code before | Published | Source | Verdict |
|---|---|---|---|---|
| Mass | 48 t (estimated: 48–55 t) | 55 t ("впервые указан вес — 55 тонн"; 48–49 t were earlier unofficial figures) | Российская газета, 28.06.2019 (https://rg.ru/2019/06/28/ves-tanka-i-bmp-na-platforme-armata-rassekretili-na-armii-2019.html); en / ru.wikipedia cite it | **corrected → 55 t** (no longer an estimate) |
| Length over gun | 10.8 m | 10.8 m | Российская газета 2019; ru.wikipedia (10,800 mm) | same |
| Hull length | 8.7 m | 8,732 mm | ru.wikipedia; hi-tech.mail.ru (tables without a source) | same within 3 cm (kept) |
| Width | 3.5 m | 3.9 m | Российская газета 2019 | **corrected → 3.9 m** |
| Gauge | 2.85 m | 2,800 mm | hi-tech.mail.ru table (https://hi-tech.mail.ru/review/118378-tank-t-14-armata/), no source named | not found in a primary source: 2.85 kept (5 cm off the unsourced table) |
| Crew | 3 | 3 | en / ru.wikipedia | same |
| Engine / power | ChTZ 12N360 (A-85-3A), 1,500 hp | 12N360 (A-85-3A), 1,103 kW (1,500 hp) | ru.wikipedia (citing ChTZ-Uraltrak's catalogue); РИА Новости 2016; Российская газета 2019 | same |
| Rated rpm | 2,000 rpm (shown on the sheet as published) | not published | — | **not found**: the sheet no longer shows it as published; marked 機関回転数（推定） |
| Top speed | 80 km/h (estimated: 75–90) | 75–80 km/h (Российская газета 2015 and 2019); 80–90 km/h (vpk.name) | Российская газета; en.wikipedia | disagree: 80 kept, the top of the official range; the mark now reads 公表は75〜80 km/h |
| Gearbox | robotised, 8 fwd / 8 rev | 8 forward + 8 reverse, reversible (Первый технический, as reported by www1.ru); 12-speed automatic (vpk.name, Army Technology) | www1.ru (https://www1.ru/news/2026/10/09/t-14-armata-naucilsia-vygliadyvat-iz-za-ugla-sekret-manevra-v-reversivnoi-transmissii.amp.html); en.wikipedia | disagree: 8 / 8 kept (the more specific, more recent report); marked 変速段数（12段の報道も） |
| Reverse speed | 80 km/h (estimated: forward gears backwards) | "заявленная скорость движения назад оценивается в 40–50 км/ч" | www1.ru (as above, from Первый технический) | **corrected → 45 km/h**, still estimated (a reported range, not the maker's) |
| Gun | 2A82-1M 125 mm | 2A82-1M 125 mm smoothbore (L/56 per hi-tech.mail.ru) | en / ru.wikipedia | same |
| Round | 3BM69 APFSDS | "Вакуум-1" APFSDS (named); ru.wikipedia: a standard round for the T-14 is not yet made | en / ru.wikipedia | same (the name is a reported one) |
| Muzzle velocity | 1,750 m/s (estimated) | not published | — | not found: stays estimated |
| Rate of fire | 5.5 s (10–12 rounds a minute) | 10–12 rounds a minute | ru.wikipedia (citing US Army OE Watch); Naked Science | same (still estimated: a reported figure) |
| Rounds carried (gun's `ammo`) | 45 | 45, of which 32 in the autoloader | en.wikipedia (citing Army Recognition) | **corrected → 32**: the crew in the hull capsule cannot reach the other 13; the autoloader's count, as for the 10式 |
| Elevation limits | −6° / +14° (estimated: T-90) | +15° / −7° | ru.wikipedia; hi-tech.mail.ru (tables, no source named) | not found in a primary source: **−7° / +15°** taken as the estimate's basis (the T-14's own reported figure instead of the T-90's); stays estimated |
| Traverse / elevation rate | 40 °/s / 15 °/s (estimated) | not published | — | not found: stays estimated |
| Sight magnification | 4× / 12× (estimated) | not published | — | not found: stays estimated |
| Shot / charge / drag | 8.5 kg / 10 kg / 60 (estimated) | not published | — | not found: stays estimated |
| Track contact / clearance | 5.3 / 0.5 m | not published | — | not found (sim geometry) |

## Effects of the corrections

- Leopard 2A5: 59.5 t and 70 km/h (gear speeds spaced to 70: 16.5 / 29 / 45 / 70 km/h; the ratios are not published).
  Its muzzle is 0.3 m further back.
- M1A2 SEPv3: muzzle velocity 1,552.5 m/s, charge 8.15 kg (recoil +0.1 %), muzzle 0.06 m further back.
- T-14: 55 t instead of 48 t (slower to accelerate), 3.9 m wide (collision box), 45 km/h backwards instead of 80,
  32 rounds instead of 45, elevation −7° / +15°.
- `vehicleStats.json` and `TANK_MEDALS` were re-derived for the Leopard 2A5 and the T-14 (`TANKS=1 COURSE=<id>
  LIMIT=1800 npx tsx tools/sim-run.ts leopard2a5,t14,m1a2 legend`; the unchanged M1A2's laps reproduced its old
  medals to the half-second, which checks the derivation).
