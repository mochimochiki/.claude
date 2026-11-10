"""SVG の図のコントラストを確かめ、ヘッドレスブラウザで PNG に描画する。"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "{http://www.w3.org/2000/svg}"
TEXT_MIN = 4.5
SHAPE_MIN = 3.0
NAMED = {"white": "#ffffff", "black": "#000000", "none": None, "transparent": None}


def hex_rgb(value):
    value = NAMED.get(value, value)
    if not value or not value.startswith("#"):
        return None
    h = value[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) if len(h) == 6 else None


def luminance(rgb):
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    la, lb = luminance(hex_rgb(a)), luminance(hex_rgb(b))
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def parse_css(root):
    rules = {}
    for style in root.iter(NS + "style"):
        for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", style.text or ""):
            props = dict(
                (k.strip(), v.strip())
                for k, v in (p.split(":", 1) for p in body.split(";") if ":" in p)
            )
            for s in sel.split(","):
                rules.setdefault(s.strip(), {}).update(props)
    return rules


def resolve(el, prop, rules, parents):
    style = el.get("style") or ""
    m = re.search(prop + r"\s*:\s*([^;]+)", style)
    if m:
        return m.group(1).strip()
    tag = el.tag.replace(NS, "")
    for cls in (el.get("class") or "").split():
        if prop in rules.get("." + cls, {}):
            return rules["." + cls][prop]
    for node in parents.get(el, []):
        for cls in (node.get("class") or "").split():
            if prop in rules.get(f".{cls} {tag}", {}):
                return rules[f".{cls} {tag}"][prop]
    if prop in rules.get(tag, {}):
        return rules[tag][prop]
    if el.get(prop):
        return el.get(prop)
    if prop == "fill":
        for node in parents.get(el, []):
            if node.get(prop):
                return node.get(prop)
            for cls in (node.get("class") or "").split():
                if tag == "text" and prop in rules.get("." + cls, {}) and node.tag == NS + "text":
                    return rules["." + cls][prop]
    return None


def num(v, default=0.0):
    try:
        return float(re.sub(r"[a-z%]+$", "", v))
    except (TypeError, ValueError):
        return default


def path_box(d):
    tokens = re.findall(r"[A-Za-z]|-?\d*\.?\d+(?:e-?\d+)?", d)
    xs, ys, cx, cy, cmd, i = [], [], 0.0, 0.0, "M", 0
    sizes = {"M": 2, "L": 2, "H": 1, "V": 1, "A": 7, "C": 6, "Q": 4, "S": 4, "T": 2}
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                continue
        n = sizes.get(cmd.upper(), 2)
        args = [float(t) for t in tokens[i:i + n]]
        i += n
        if len(args) < n:
            break
        rel = cmd.islower()
        if cmd.upper() == "H":
            cx = cx + args[0] if rel else args[0]
        elif cmd.upper() == "V":
            cy = cy + args[0] if rel else args[0]
        else:
            ex, ey = args[-2], args[-1]
            cx, cy = (cx + ex, cy + ey) if rel else (ex, ey)
        xs.append(cx)
        ys.append(cy)
    if not xs:
        return None
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def shape_box(el):
    tag = el.tag.replace(NS, "")
    if tag == "rect":
        return num(el.get("x")), num(el.get("y")), num(el.get("width")), num(el.get("height"))
    if tag == "circle":
        r = num(el.get("r"))
        return num(el.get("cx")) - r, num(el.get("cy")) - r, 2 * r, 2 * r
    if tag == "path" and (el.get("fill") or "none") != "none":
        return path_box(el.get("d") or "")
    return None


def collect(root):
    parents = {}

    def walk(node, anc):
        for child in node:
            parents[child] = anc
            walk(child, [child] + anc)

    walk(root, [])
    return parents


def text_box(el, rules, parents):
    """文字の外接矩形を字の大きさと字数から見積もる。"""
    size = num(re.sub(r"px$", "", resolve(el, "font-size", rules, parents) or "16"), 16)
    label = "".join(el.itertext())
    width = sum(size * (0.3 if c == " " else 1.0 if ord(c) > 0x2E7F else 0.6) for c in label)
    x, y = num(el.get("x")), num(el.get("y"))
    anchor = resolve(el, "text-anchor", rules, parents) or "start"
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    return x, y - size * 0.8, width, size * 0.95, label.strip()


def data_segments(el, rules, parents):
    """線(データの線・軸・罫線・引き出し線)を線分の列にする。"""
    tag = el.tag.replace(NS, "")
    if tag not in ("polyline", "path", "line"):
        return []
    stroke = resolve(el, "stroke", rules, parents)
    if not stroke or stroke == "none" or num(resolve(el, "stroke-width", rules, parents) or "1") <= 0:
        return []
    if tag == "line":
        pts = [(num(el.get("x1")), num(el.get("y1"))), (num(el.get("x2")), num(el.get("y2")))]
    elif tag == "polyline":
        nums = [float(n) for n in re.findall(r"-?[\d.]+", el.get("points") or "")]
        pts = list(zip(nums[0::2], nums[1::2]))
    else:
        d = el.get("d") or ""
        if re.search(r"[CcQqSsTtAaZz]", d):
            return []
        pts, cx, cy = [], 0.0, 0.0
        for cmd, arg in re.findall(r"([MLHVmlhv])([^MLHVmlhv]*)", d):
            a = [float(n) for n in re.findall(r"-?[\d.]+", arg)]
            rel = cmd.islower()
            if cmd in "Hh":
                cx = cx + a[0] if rel else a[0]
            elif cmd in "Vv":
                cy = cy + a[0] if rel else a[0]
            else:
                cx, cy = (cx + a[0], cy + a[1]) if rel else (a[0], a[1])
            if cmd in "Mm" and pts:
                pts.append(None)
            pts.append((cx, cy))
    segs = []
    for a, b in zip(pts, pts[1:]):
        if a and b:
            segs.append((a, b))
    return segs


def seg_hits_box(seg, box):
    (x1, y1), (x2, y2) = seg
    bx, by, bw, bh = box
    for i in range(21):
        t = i / 20
        x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
        if bx < x < bx + bw and by < y < by + bh:
            return True
    return False


def overlaps(root, rules, parents):
    """文字どうし、文字と記号、文字とデータの線の重なりを見つける。
    線と文字のあいだに塗りの図形(文字の下に敷いた矩形など)があるときは、線が隠れるので重なりとしない。"""
    skip = lambda el: any(a.tag in (NS + "defs", NS + "symbol", NS + "marker", NS + "clipPath") for a in parents.get(el, []))
    order = {el: i for i, el in enumerate(root.iter())}
    text_els = [el for el in root.iter(NS + "text") if not skip(el)]
    texts = [(order[el], text_box(el, rules, parents)) for el in text_els]
    halos = [(resolve(el, "paint-order", rules, parents) or "").startswith("stroke") and
             (resolve(el, "stroke", rules, parents) or "none") != "none" for el in text_els]
    segs = [(order[el], s) for el in root.iter() if not skip(el) for s in data_segments(el, rules, parents)]
    fills = []
    for el in root.iter():
        box = shape_box(el)
        fill = resolve(el, "fill", rules, parents)
        if box and not skip(el) and fill and fill != "none":
            fills.append((order[el], box))
    icons = [(num(el.get("x")), num(el.get("y")), num(el.get("width")), num(el.get("height")))
             for el in root.iter(NS + "use") if not skip(el)]
    found = []
    for i, (oa, a) in enumerate(texts):
        for ix, iy, iw, ih in icons:
            if a[0] < ix + iw and ix < a[0] + a[2] and a[1] < iy + ih and iy < a[1] + a[3]:
                found.append(f"文字が記号に重なる「{a[4][:12]}」")
                break
        for ob, b in texts[i + 1:]:
            if a[0] < b[0] + b[2] - 1 and b[0] < a[0] + a[2] - 1 and a[1] < b[1] + b[3] - 1 and b[1] < a[1] + a[3] - 1:
                found.append(f"文字が重なる「{a[4][:12]}」と「{b[4][:12]}」")
        cx, cy = a[0] + a[2] / 2, a[1] + a[3] / 2
        if halos[i]:
            continue  # 背景色の縁取りで、下の線を切っている文字
        for ol, seg in segs:
            if not seg_hits_box(seg, a[:4]):
                continue
            (x1, y1), (x2, y2) = seg
            if y1 == y2 and a[0] - 6 <= min(x1, x2) and max(x1, x2) <= a[0] + a[2] + 6:
                continue  # 文字に合わせて引いた取り消し線
            hidden = any(ol < of < oa and fx <= cx <= fx + fw and fy <= cy <= fy + fh for of, (fx, fy, fw, fh) in fills)
            if not hidden:
                found.append(f"文字が線に重なる「{a[4][:12]}」")
                break
    return found


def check(svg_path):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    rules = parse_css(root)
    parents = collect(root)
    problems = []
    if root.find(NS + "title") is None:
        problems.append("title が無い")
    if root.find(NS + "desc") is None:
        problems.append("desc が無い(文書用では付ける)")
    texts = ["".join(t.itertext()).strip() for t in root.iter(NS + "text")]
    chars = sum(len(re.sub(r"\s", "", t)) for t in texts)
    vb = (root.get("viewBox") or "0 0 640 0").split()
    poster = num(vb[2]) >= 1000
    soft, hard = (100, 105) if poster else (120, 150)
    if root.get("data-char-limit"):
        hard = int(root.get("data-char-limit"))  # 多段のサンキーなど、numbers.md が認める図だけが上限を上げる
    if chars > hard:
        problems.append(f"字数 {chars} 字 > 上限 {hard} 字(目安 {soft} 字以下)。要る説明は削らず、要素を減らすか図を分ける")
    long_labels = [t for t in texts if len(t) > 25]
    for t in long_labels:
        problems.append(f"1 行が長い({len(t)} 字)「{t[:20]}…」")
    problems += overlaps(root, rules, parents)
    stats = f"字数 {chars} 字・ラベル {len(texts)} 個"
    rects = []
    order = 0
    for el in root.iter():
        order += 1
        box = shape_box(el)
        if box and not any(a.tag in (NS + "defs", NS + "marker") for a in parents.get(el, [])):
            fill = resolve(el, "fill", rules, parents) or "#000000"
            rects.append((order, *box, fill, el))
    full_w = num((root.get("viewBox") or "0 0 0 0").split()[2]) or num(root.get("width"))
    if not rects or rects[0][3] < full_w * 0.99 or not hex_rgb(rects[0][5]):
        problems.append("最初の要素に全面の背景の矩形が無い")

    def behind(x, y, upto):
        best = None
        for o, rx, ry, rw, rh, fill, _ in rects:
            if o >= upto:
                break
            if rx <= x <= rx + rw and ry <= y <= ry + rh and hex_rgb(fill):
                best = fill
        return best

    order = 0
    for el in root.iter():
        order += 1
        tag = el.tag.replace(NS, "")
        if tag == "text" and any(a.tag in (NS + "defs", NS + "symbol") for a in parents.get(el, [])):
            continue
        if tag == "text":
            color = resolve(el, "fill", rules, parents) or "#000000"
            bg = behind(num(el.get("x")), num(el.get("y")) - 4, order)
            if hex_rgb(color) and bg:
                r = ratio(color, bg)
                if r < TEXT_MIN:
                    label = "".join(el.itertext()).strip()[:20]
                    problems.append(f"文字 {r:.2f}:1 < {TEXT_MIN} 「{label}」 {color} on {bg}")
        elif tag == "rect":
            stroke = resolve(el, "stroke", rules, parents)
            fill = resolve(el, "fill", rules, parents)
            x, y = num(el.get("x")), num(el.get("y"))
            outside = behind(x - 1, y - 1, order) if x > 0 or y > 0 else None
            if hex_rgb(stroke) and outside:
                r_out = ratio(stroke, outside)
                r_in = ratio(stroke, fill) if hex_rgb(fill) else r_out
                if max(r_out, r_in) < SHAPE_MIN:
                    problems.append(f"枠線 {max(r_out, r_in):.2f}:1 < {SHAPE_MIN} {stroke} (外 {outside}, 内 {fill}) at {x:.0f},{y:.0f}")
    return problems, stats


def find_browser():
    candidates = [
        os.environ.get("DIAGRAM_BROWSER"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ] + [shutil.which(n) for n in ("chromium", "chromium-browser", "google-chrome", "microsoft-edge", "msedge")]
    return next((c for c in candidates if c and Path(c).exists()), None)


def render(svg_path, png_path, scale):
    browser = find_browser()
    if not browser:
        return "ブラウザが見つからない(DIAGRAM_BROWSER で指定できる)"
    root = ET.parse(svg_path).getroot()
    vb = (root.get("viewBox") or "").split()
    w = int(num(root.get("width"), num(vb[2]) if vb else 800))
    h = int(num(root.get("height"), num(vb[3]) if vb else 600))
    html = Path(tempfile.mkdtemp()) / "page.html"
    html.write_text(
        f'<!doctype html><html><body style="margin:0"><img src="{Path(svg_path).resolve().as_uri()}" '
        f'width="{w}" height="{h}" style="display:block"></body></html>', encoding="utf-8")
    profile = tempfile.mkdtemp()
    cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           f"--user-data-dir={profile}", f"--force-device-scale-factor={scale}",
           f"--window-size={w},{h}", f"--screenshot={Path(png_path).resolve()}", html.as_uri()]
    subprocess.run(cmd, capture_output=True, timeout=60)
    return None if Path(png_path).exists() else "PNG を書き出せなかった"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("svg", nargs="+")
    ap.add_argument("--png", action="store_true", help="同じ場所に PNG を書き出す")
    ap.add_argument("--out", help="PNG の書き出し先フォルダ(既定は SVG と同じ場所)")
    ap.add_argument("--scale", type=float, default=2)
    args = ap.parse_args()
    failed = False
    for svg in args.svg:
        problems, stats = check(svg)
        print(f"== {svg}  ({stats})")
        for p in problems:
            print("  NG", p)
        if not problems:
            print("  OK コントラスト・背景・字数・重なり")
        failed |= bool(problems)
        if args.png:
            out = Path(args.out) if args.out else Path(svg).parent
            out.mkdir(parents=True, exist_ok=True)
            png = str(out / (Path(svg).stem + ".png"))
            err = render(svg, png, args.scale)
            print("  NG" if err else "  PNG", err or png)
            failed |= bool(err)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
