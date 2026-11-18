"""감귤 그림: 메인 화면 아래 반쪽 귤 단면과 시작 화면의 통귤. 조각 모양을 코드로 계산해 그린다."""
import math


def drop(x, y, size, angle, delay=None, color='url(#juice)'):
    """A juice droplet pointing away from the fruit (angle in degrees, 0 = up)."""
    s = size
    body = (f'M0 {-s:.1f} C {s*.62:.1f} {-s*.15:.1f}, {s*.72:.1f} {s*.55:.1f}, 0 {s*.85:.1f} '
            f'C {-s*.72:.1f} {s*.55:.1f}, {-s*.62:.1f} {-s*.15:.1f}, 0 {-s:.1f} Z')
    shine = f'<ellipse cx="{-s*.22:.1f}" cy="{s*.18:.1f}" rx="{s*.16:.1f}" ry="{s*.26:.1f}" fill="#FFFFFF" opacity=".75"/>'
    cls = f' class="pop" style="animation-delay:{delay}s"' if delay is not None else ''
    return (f'<g transform="translate({x:.1f} {y:.1f}) rotate({angle:.1f})"><g{cls}>'
            f'<path d="{body}" fill="{color}"/>{shine}</g></g>')


def slice_segments(cx, cy, r_in, r_out, count=10, gap_deg=3.2):
    """Wedge paths of a mandarin cross-section, separated by thin pith gaps."""
    paths = []
    for i in range(count):
        a0 = math.radians(i * 360 / count + gap_deg / 2 - 90)
        a1 = math.radians((i + 1) * 360 / count - gap_deg / 2 - 90)
        p = lambda r, a: (cx + r * math.cos(a), cy + r * math.sin(a))
        x0, y0 = p(r_in, a0); x1, y1 = p(r_out, a0); x2, y2 = p(r_out, a1); x3, y3 = p(r_in, a1)
        paths.append(f'<path d="M{x0:.1f} {y0:.1f} L{x1:.1f} {y1:.1f} A{r_out} {r_out} 0 0 1 {x2:.1f} {y2:.1f} '
                     f'L{x3:.1f} {y3:.1f} A{r_in} {r_in} 0 0 0 {x0:.1f} {y0:.1f} Z" fill="url(#flesh)"/>')
        # juice sacs: short light strokes along the middle of each segment
        mid = (a0 + a1) / 2
        for k, r in enumerate(range(r_in + 60, r_out - 20, 55)):
            for off in (-.09, .09) if k % 2 else (0,):
                sx, sy = p(r, mid + off)
                ex, ey = p(r + 26, mid + off)
                paths.append(f'<path d="M{sx:.1f} {sy:.1f} L{ex:.1f} {ey:.1f}" stroke="#FFD27A" '
                             f'stroke-width="7" stroke-linecap="round" opacity=".55"/>')
    return ''.join(paths)


def main_art():
    """Bottom of the main page: a halved mandarin rising like a sun, juice splashing up."""
    cx, cy, r = 600, 640, 430
    drops = ''.join(drop(*d) for d in (
        (420, 150, 22, -35), (470, 92, 14, -22), (560, 60, 18, -6), (650, 70, 13, 8), (745, 110, 20, 28),
        (800, 165, 12, 40), (350, 205, 12, -50), (880, 220, 16, 52), (520, 128, 9, -15), (700, 140, 9, 18)))
    leaves = ('<path d="M150 380 C 170 300, 260 250, 330 262 C 300 330, 230 380, 150 380 Z" fill="#1E8F3E"/>'
              '<path d="M158 372 C 210 318, 262 286, 322 266" stroke="#146B2D" stroke-width="5" fill="none" stroke-linecap="round"/>'
              '<path d="M1050 380 C 1030 300, 940 250, 870 262 C 900 330, 970 380, 1050 380 Z" fill="#23A048"/>'
              '<path d="M1042 372 C 990 318, 938 286, 878 266" stroke="#146B2D" stroke-width="5" fill="none" stroke-linecap="round"/>')
    sparkles = ''.join(f'<path d="M{x} {y-s} L{x+s*.28} {y-s*.28} L{x+s} {y} L{x+s*.28} {y+s*.28} L{x} {y+s} '
                       f'L{x-s*.28} {y+s*.28} L{x-s} {y} L{x-s*.28} {y-s*.28} Z" fill="{c}"/>'
                       for x, y, s, c in ((300, 110, 16, '#FFB31A'), (930, 120, 20, '#1E8F3E'), (1010, 230, 11, '#FF8A00'),
                                          (200, 250, 10, '#1E8F3E')))
    return f'''<svg viewBox="0 0 1200 380" preserveAspectRatio="xMidYMax meet" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="flesh" cx="{cx}" cy="{cy}" r="{r}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#FFC85C"/><stop offset=".7" stop-color="#FFA21F"/><stop offset="1" stop-color="#FF8A00"/>
    </radialGradient>
    <linearGradient id="juice" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFC233"/><stop offset="1" stop-color="#FF8A00"/></linearGradient>
  </defs>
  {sparkles}
  {leaves}
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="#F26B00"/>
  <circle cx="{cx}" cy="{cy}" r="{r-18}" fill="#FFF3DA"/>
  {slice_segments(cx, cy, 48, r - 30)}
  <circle cx="{cx}" cy="{cy}" r="44" fill="#FFF3DA"/>
  {drops}
</svg>'''


def whole_art():
    """Splash: a whole mandarin with juice drops popping out around it (looping, no script)."""
    pops = ''.join(drop(*d) for d in (
        (40, 70, 13, -55, 0), (232, 60, 11, 50, .5), (22, 170, 10, -95, 1.0), (258, 170, 12, 95, 1.5),
        (70, 240, 9, -140, .8), (214, 246, 10, 140, 1.3), (140, 14, 9, 0, 1.8)))
    return '''<svg viewBox="-20 -20 320 300" xmlns="http://www.w3.org/2000/svg">
  <style>
    .pop {animation: pop 2.4s ease-out infinite; transform-box: fill-box; transform-origin: center; opacity: 0;}
    @keyframes pop {0% {opacity: 0; transform: translateY(14px) scale(.4);} 18% {opacity: 1;}
                    70% {opacity: 1; transform: translateY(-10px) scale(1);} 100% {opacity: 0; transform: translateY(-18px) scale(.9);}}
    @media (prefers-reduced-motion: reduce) {.pop {animation: none; opacity: 1;}}
  </style>
  <defs>
    <radialGradient id="p" cx="36%" cy="32%" r="72%">
      <stop offset="0" stop-color="#FFB547"/><stop offset=".55" stop-color="#FF8A00"/><stop offset="1" stop-color="#E06000"/>
    </radialGradient>
    <linearGradient id="juice" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFC233"/><stop offset="1" stop-color="#FF8A00"/></linearGradient>
    <clipPath id="f"><path d="M140 72 C 188 56, 242 80, 242 138 C 242 188, 196 214, 140 214 C 84 214, 38 188, 38 138 C 38 80, 92 56, 140 72 Z"/></clipPath>
  </defs>
  <path d="M140 72 C 188 56, 242 80, 242 138 C 242 188, 196 214, 140 214 C 84 214, 38 188, 38 138 C 38 80, 92 56, 140 72 Z" fill="url(#p)"/>
  <g clip-path="url(#f)">
    <g fill="#C85200" opacity=".32">
      <circle cx="80" cy="120" r="2.2"/><circle cx="104" cy="106" r="2"/><circle cx="170" cy="102" r="2.2"/><circle cx="196" cy="116" r="2"/>
      <circle cx="216" cy="144" r="2.2"/><circle cx="64" cy="156" r="2"/><circle cx="92" cy="180" r="2.2"/><circle cx="124" cy="196" r="2"/>
      <circle cx="160" cy="192" r="2.2"/><circle cx="192" cy="176" r="2"/><circle cx="140" cy="160" r="2"/><circle cx="112" cy="144" r="2.2"/>
      <circle cx="170" cy="138" r="2"/><circle cx="202" cy="158" r="2.2"/><circle cx="78" cy="142" r="2"/><circle cx="142" cy="122" r="2"/>
    </g>
    <ellipse cx="100" cy="106" rx="32" ry="13" fill="#FFFFFF" opacity=".35" transform="rotate(-20 100 106)"/>
  </g>
  <ellipse cx="140" cy="74" rx="18" ry="6" fill="#B84A00" opacity=".45"/>
  <path d="M144 70 C 160 40, 206 30, 230 40 C 214 66, 176 80, 144 70 Z" fill="#1E8F3E"/>
  <path d="M146 69 C 172 56, 200 46, 226 41" stroke="#146B2D" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  <path d="M140 60 L144 68 L153 68 L146 73 L149 81 L140 76 L131 81 L134 73 L127 68 L136 68 Z" fill="#2E9B3E" stroke="#146B2D" stroke-width="1.2" stroke-linejoin="round"/>
  <circle cx="140" cy="71" r="3" fill="#6B4423"/>
  ''' + pops + '''
</svg>'''


