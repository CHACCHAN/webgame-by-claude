import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { gameHolder } from '../GameCanvas';
import { useMenuInput } from '../useMenuInput';
import { CAR_SPECS, type CarId } from '../../game/vehicle/carSpecs';
import { KIND_TRAITS, kindOf, traitsOf } from '../../game/vehicle/kinds';
import { specForLivery } from '../../game/vehicle/trains';
import { jetForLivery } from '../../game/vehicle/jets';
import { useGarage } from '../../store/garage';
import { CountText, FocusFrame, Hint, PadKey, type HintKey } from '../kit';
import { COLORS, liveryName, originOf, useGarageOrbit } from '../screens/Cars';
import { sfx } from '../sfx';
import { BAR_KNEE, SORTS, garageFramingFor, moveInGrid, pickerTabs, sortFigure, sortVehicles, tabVehicles, vehicleBars, type TabId } from './picker';


export interface VehiclePickerProps {
  /** the heading: what is being chosen, and the same in the display face */
  title: string;
  titleEn: string;
  /** what may be picked here (the course's vehicles), in the players' order */
  vehicles: CarId[];
  /** the vehicle highlighted on opening */
  initial: CarId;
  /** the colour picked earlier (null: each vehicle's first) */
  initialColor?: string | null;
  /** offer the colours / liveries (not online: there every grid slot has its paint) */
  colors?: boolean;
  /** the vehicle that is entered now (online), marked while others are looked at */
  entered?: CarId;
  confirmLabel: string;
  /** drawn over another screen (the online lobby and room), which it hides meanwhile */
  overlay?: boolean;
  onConfirm: (id: CarId, color: string | null) => void;
  onBack: () => void;
  /** every change of the highlighted vehicle or of the colour (also once on opening) */
  onBrowse?: (id: CarId, color: string | null) => void;
  /** under the bars (single player: the record on this course) */
  extra?: (id: CarId) => ReactNode;
}

/** The vehicle's picture (public/img/vehicles/<id>.webp, tools/thumbs.cjs); without one, a tile naming its kind. */
export function VehicleThumb({ id }: { id: CarId }) {
  const [missing, setMissing] = useState(false);
  return (
    <div className="vp-thumb">
      {missing ? (
        <div className="vp-thumb-none">{KIND_TRAITS[kindOf(CAR_SPECS[id])].label}</div>
      ) : (
        <img src={`/img/vehicles/${id}.webp`} alt="" draggable={false} onError={() => setMissing(true)} />
      )}
    </div>
  );
}

/** Measured figures as bars (the scale: picker.ts `barFill`), each with the real number. */
function Bars({ id }: { id: CarId }) {
  const bars = vehicleBars(id);
  if (!bars) return <div className="vp-bars vp-bars-none">性能データは計測待ちです</div>;
  return (
    <div className="vp-bars">
      {bars.map((b) => (
        <div key={b.key} className={`vp-bar${b.neutral ? ' neutral' : ''}${b.over ? ' over' : ''}`}>
          <span>{b.label}</span>
          <div className="vp-track">
            <div style={{ transform: `scaleX(${b.fill.toFixed(3)})` }} />
            <i style={{ left: `${BAR_KNEE * 100}%` }} />
          </div>
          <CountText text={b.text} />
        </div>
      ))}
      <p className="vp-bars-note">平坦な乾いた路面での実測値。バーは切れ目から先を縮めて表示</p>
    </div>
  );
}

/**
 * The car select, the same for single player and online: tabs by kind of vehicle, a grid of pictures (sortable, with
 * favourites), and for the highlighted vehicle the 3D garage with its measured figures, colours and the confirm
 * button. Highlighting only shows a vehicle (`game.showGarage`); `onConfirm` is the choice.
 * Keys: arrows move in the grid, Q / E (LB / RB) change the tab, R (Back) the order, C (Y) the colour, X the
 * favourite, Enter confirms, Esc goes back. Mouse and touch: a tile highlights, the highlighted tile again (or the
 * button) confirms.
 */
export function VehiclePicker({ title, titleEn, vehicles, initial, initialColor = null, colors = true, entered, confirmLabel, overlay, onConfirm, onBack, onBrowse, extra }: VehiclePickerProps) {
  const favourites = useGarage((s) => s.favourites);
  const sort = useGarage((s) => s.sort);
  const [id, setId] = useState<CarId>(vehicles.includes(initial) ? initial : vehicles[0]);
  const [picked, setPicked] = useState<string | null>(initialColor);
  // the tab last used, unless the vehicle to show is not on it: then its kind's
  const [tab, setTab] = useState<TabId>(() => {
    const stored = useGarage.getState().tab;
    return tabVehicles(vehicles, stored, useGarage.getState().favourites).includes(id) ? stored : kindOf(CAR_SPECS[id]);
  });
  const tabs = useMemo(() => pickerTabs(vehicles, favourites), [vehicles, favourites]);
  const list = useMemo(() => sortVehicles(tabVehicles(vehicles, tab, favourites), sort), [vehicles, tab, favourites, sort]);
  const palette = COLORS[id];
  const color = colors ? (picked && palette.includes(picked) ? picked : palette[0]) : undefined;
  // a train's figures as fitted for the line picked, a two-seat fighter's mass
  const spec = jetForLivery(specForLivery(CAR_SPECS[id], color), color);

  // the 3D garage follows the highlighted vehicle; another colour repaints the one standing there
  useEffect(() => {
    gameHolder.game?.showGarage(id, color);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  useEffect(() => {
    if (color) gameHolder.game?.setGarageColor(color);
  }, [color]);
  const browse = useRef(onBrowse);
  browse.current = onBrowse;
  useEffect(() => browse.current?.(id, picked), [id, picked]);
  // the 3D vehicle stands in the part of the screen the picker leaves free: right of the list, above the card
  // (whose height changes with the vehicle and the screen)
  const root = useRef<HTMLDivElement>(null);
  const view3d = traitsOf(spec).garage;
  useEffect(() => {
    const game = gameHolder.game;
    const el = root.current;
    const list = el?.querySelector<HTMLElement>('.vp-browse');
    const card = el?.querySelector<HTMLElement>('.vp-detail');
    if (!game || !el || !list || !card) return;
    const before = game.garageFraming;
    const frame = () => {
      const view = { w: el.clientWidth, h: el.clientHeight };
      // (the places in the layout: both slide in, and a place read while that runs would be off)
      game.garageFraming = garageFramingFor(view, { left: list.offsetLeft + list.offsetWidth, right: view.w, top: 0, bottom: card.offsetTop }, view3d);
    };
    frame();
    const watch = new ResizeObserver(frame);
    watch.observe(el);
    watch.observe(card);
    return () => {
      watch.disconnect();
      game.garageFraming = before;
    };
  }, [view3d]);

  const grid = useRef<HTMLDivElement>(null);
  useEffect(() => {
    grid.current?.querySelector('.vp-tile.on')?.scrollIntoView({ block: 'nearest' });
  }, [id, list]);
  const columns = () => (grid.current ? getComputedStyle(grid.current).gridTemplateColumns.split(' ').filter(Boolean).length : 1);

  const highlight = (next: CarId) => {
    if (next === id) return;
    setId(next);
    sfx.move();
  };
  const move = (dir: 'left' | 'right' | 'up' | 'down') => {
    if (!list.length) return;
    const i = list.indexOf(id);
    highlight(i < 0 ? list[0] : list[moveInGrid(i, list.length, columns(), dir)]);
  };
  const openTab = (t: TabId) => {
    if (t === tab) return;
    setTab(t);
    useGarage.getState().set({ tab: t });
    sfx.tab();
    // the cursor stays on the vehicle if the tab has it, else goes to the tab's first
    const next = sortVehicles(tabVehicles(vehicles, t, favourites), sort);
    if (next.length && !next.includes(id)) setId(next[0]);
  };
  const stepTab = (d: number) => openTab(tabs[(tabs.findIndex((t) => t.id === tab) + d + tabs.length) % tabs.length].id);
  const setSort = (key: (typeof SORTS)[number]['key']) => {
    useGarage.getState().set({ sort: key });
    sfx.move();
  };
  const nextSort = () => setSort(SORTS[(SORTS.findIndex((s) => s.key === sort) + 1) % SORTS.length].key);
  const nextColor = () => {
    if (!color || palette.length < 2) return;
    setPicked(palette[(palette.indexOf(color) + 1) % palette.length]);
    sfx.move();
  };
  const star = (v: CarId) => {
    useGarage.getState().toggleFavourite(v);
    sfx.move();
  };
  const confirm = () => {
    sfx.confirm();
    onConfirm(id, colors ? picked : null);
  };
  useMenuInput((a) => {
    if (a === 'left' || a === 'right' || a === 'up' || a === 'down') move(a);
    if (a === 'prevTab') stepTab(-1);
    if (a === 'nextTab') stepTab(1);
    if (a === 'optionSort') nextSort();
    if (a === 'optionY') nextColor();
    if (a === 'optionX') star(id);
    if (a === 'confirm') confirm();
    if (a === 'back') {
      sfx.back();
      onBack();
    }
  });
  const orbit = useGarageOrbit();
  const sortLabel = SORTS.find((s) => s.key === sort)?.label ?? '';
  const badge = traitsOf(spec).badge;
  const hints: [HintKey, string][] = [['all', '車両'], ['tab', 'タブ'], ['sort', '並べ替え'], ['fav', 'お気に入り'], ['ok', '決定']];
  if (colors) hints.splice(3, 0, ['color', 'カラー']);
  return (
    <div ref={root} className={`screen vp${overlay ? ' vp-over' : ''}${orbit.dragging ? ' orbiting' : ''}`} {...orbit.handlers}>
      <div className="vp-browse">
        <div className="vp-top">
          <div className="vp-head">
            <h2>{title}</h2>
            <span className="sh-en">{titleEn}</span>
          </div>
          <button className="vp-sort-cycle" onClick={nextSort}>並べ替え：{sortLabel}</button>
        </div>
        <div className="vp-tabs" role="tablist">
          <kbd className="vp-key k-key">Q</kbd>
          <span className="vp-key"><PadKey name="LB" /></span>
          {tabs.map((t) => (
            <button key={t.id} role="tab" aria-selected={t.id === tab} data-tab={t.id} className={`vp-tab${t.id === tab ? ' on' : ''}`} onClick={() => openTab(t.id)} title={t.id === 'fav' ? 'お気に入り' : undefined}>
              {t.label}
              <i>{t.count}</i>
            </button>
          ))}
          <kbd className="vp-key k-key">E</kbd>
          <span className="vp-key"><PadKey name="RB" /></span>
        </div>
        <div className="vp-sorts">
          <span>並べ替え</span>
          {SORTS.map((s) => (
            <button key={s.key} data-sort={s.key} className={`vp-sort${s.key === sort ? ' on' : ''}`} onClick={() => setSort(s.key)}>
              {s.label}
            </button>
          ))}
        </div>
        <div className="vp-grid" ref={grid} role="listbox">
          {list.map((v) => {
            const figure = sortFigure(v, sort);
            const fav = favourites.includes(v);
            return (
              <div key={v} role="option" aria-selected={v === id} data-id={v} className={`vp-tile${v === id ? ' on' : ''}`} onClick={() => (v === id ? confirm() : highlight(v))}>
                <VehicleThumb id={v} />
                <div className="vp-tile-name">{CAR_SPECS[v].name}</div>
                {figure && <div className="vp-tile-fig">{figure}</div>}
                {v === entered && <span className="vp-entered">エントリー中</span>}
                <button
                  className={`vp-star${fav ? ' on' : ''}`}
                  aria-label={`${CAR_SPECS[v].name} をお気に入りに${fav ? 'から外す' : '入れる'}`}
                  aria-pressed={fav}
                  onClick={(e) => {
                    e.stopPropagation();
                    star(v);
                  }}
                >
                  ★
                </button>
              </div>
            );
          })}
          {!list.length && (
            <p className="vp-empty">
              {tab === 'fav' ? <>お気に入りはまだありません。<br />車両の ★（X キー）で登録できます。</> : 'このコースで選べる車両がありません。'}
            </p>
          )}
          <FocusFrame on=".vp-tile.on" deps={[id, list]} pad={3} />
        </div>
      </div>
      <div className="vp-detail">
        {badge && <div className="vp-badge">{badge}</div>}
        <h2 className="car-name">{spec.name}</h2>
        <div className="car-tag">{spec.tagline} ・ {originOf(spec)}</div>
        <p className="car-desc">{spec.description}</p>
        <Bars id={id} />
        {extra?.(id)}
        {colors && (
          <div className="colors">
            {palette.map((c) => (
              <button key={c} className={c === color ? 'swatch on' : 'swatch'} style={{ background: c }} onClick={() => setPicked(c)} aria-label={liveryName(id, c) ?? `color ${c}`} title={liveryName(id, c) ?? undefined} />
            ))}
            {color && liveryName(id, color) && <span className="livery-name">{liveryName(id, color)}</span>}
          </div>
        )}
        <div className="vp-actions">
          <button className="cta" onClick={confirm}>
            {confirmLabel} <span>▶</span>
          </button>
          <button className={`vp-fav${favourites.includes(id) ? ' on' : ''}`} aria-pressed={favourites.includes(id)} onClick={() => star(id)}>
            ★<span> お気に入り</span>
          </button>
        </div>
      </div>
      <Hint items={hints} />
    </div>
  );
}
