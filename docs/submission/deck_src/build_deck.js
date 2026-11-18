// 기획서 덱 생성: node build_deck.js <repo root> <output.pptx>
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const md = require("react-icons/md");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const ROOT = process.argv[2];
const OUT = process.argv[3];
const IMG = (name) => path.join(ROOT, "docs/submission/images", name);
const HERE = __dirname;

const THEME = {
  name: "Citrus Juice",
  headFontFace: "Malgun Gothic",
  bodyFontFace: "Malgun Gothic",
  colors: {
    dk1: "1A1410", lt1: "FFFFFF", dk2: "146B2D", lt2: "FFF5E4",
    accent1: "F26B00", accent2: "1E8F3E", accent3: "FF8A00", accent4: "FFB31A",
    accent5: "D95500", accent6: "6B4423", hlink: "F26B00", folHlink: "D95500",
  },
};
const HEX = THEME.colors;
const MUTED = "6E6255";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.title = "감귤의 신(神) 기획서";
pres.author = "감귤의 신 팀";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, M = 0.6;

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "COVER",
  background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.0, w: 7.4, h: 1.5, fontSize: 54, bold: true, color: C.background2, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 3.6, w: 7.4, h: 1.9, fontSize: 20, color: C.background2, valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CLOSING",
  background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.55, w: W - 2 * M, h: 0.9, fontSize: 34, bold: true, color: C.background2, valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: "FFFFFF" },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.35, w: W - 2 * M, h: 0.85, fontSize: 28, bold: true, color: C.text1, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "감귤의 신(神) · 기획서", options: { x: M, y: H - 0.42, w: 4, h: 0.3, fontSize: 10, color: MUTED, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: H - 0.42, w: 0.6, h: 0.3, fontSize: 10, color: MUTED, align: "right" },
});

// ---------- helpers ----------
async function icon(Comp, color = "FFFFFF") {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: 256 }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}
async function imageSize(file) {
  const m = await sharp(file).metadata();
  return { w: m.width, h: m.height };
}
// Fit an image inside a box, keeping its aspect ratio (centered)
async function fitImage(slide, file, box, extra = {}) {
  const s = await imageSize(file);
  const r = Math.min(box.w / s.w, box.h / s.h);
  const w = s.w * r, h = s.h * r;
  slide.addImage({ path: file, x: box.x + (box.w - w) / 2, y: box.y + (box.h - h) / 2, w, h, ...extra });
  return { x: box.x + (box.w - w) / 2, y: box.y + (box.h - h) / 2, w, h };
}
function card(slide, x, y, w, h, name, fill = HEX.lt2) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: fill },
    shadow: { type: "outer", color: "C9A77F", opacity: 0.25, blur: 6, offset: 2, angle: 90 }, objectName: name,
  });
}
async function iconCircle(slide, x, y, d, Comp, fill = HEX.accent1, name = "icon") {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill }, objectName: name + " circle" });
  slide.addImage({ data: await icon(Comp), x: x + d * 0.2, y: y + d * 0.2, w: d * 0.6, h: d * 0.6, objectName: name });
}
function text(slide, t, opts) {
  slide.addText(t, { isTextBox: true, margin: 0, fontSize: 14, color: C.text1, valign: "top", ...opts });
}
function stat(slide, x, y, w, big, label, color = C.accent1, bigSize = 40) {
  text(slide, big, { x, y, w, h: 0.8, fontSize: bigSize, bold: true, color, valign: "bottom" });
  text(slide, label, { x, y: y + 0.85, w, h: 0.7, fontSize: 13, color: MUTED });
}
function content(title, section, notes) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}
const SRC = (slide, t) => text(slide, t, { x: 4.8, y: H - 0.42, w: W - 4.8 - M - 0.8, h: 0.3, fontSize: 10, color: MUTED, align: "right" });

// eaLnBrk="0": do not split East Asian words at line ends (PowerPoint splits Korean mid-word by default)
async function keepKoreanWords(file) {
  const JSZip = require("jszip");
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  const parts = Object.keys(zip.files).filter((n) => /^ppt\/(slides|slideLayouts|slideMasters)\/[^/]+\.xml$/.test(n));
  for (const name of parts) {
    let xml = await zip.file(name).async("string");
    xml = xml.replace(/<a:pPr(?![^>]*eaLnBrk)/g, '<a:pPr eaLnBrk="0"');
    xml = xml.replace(/<a:p>(?!<a:pPr)/g, '<a:p><a:pPr eaLnBrk="0"/>');
    zip.file(name, xml);
  }
  // Copy files only into a fresh archive: folder entries break opening from cloud services.
  const out = new JSZip();
  for (const name of Object.keys(zip.files)) {
    if (!zip.files[name].dir) out.file(name, await zip.file(name).async("nodebuffer"), { createFolders: false });
  }
  fs.writeFileSync(file, await out.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}

(async () => {
  // 1. Cover ------------------------------------------------------------
  pres.addSection({ title: "개요" });
  let s = pres.addSlide({ masterName: "COVER", sectionTitle: "개요" });
  s.addText([{ text: "감귤", options: { color: C.accent3 } }, { text: "의 신(神)" }], { placeholder: "title" });
  s.addText([
    { text: "데이터로 읽는 제주 감귤 수급 비서", options: { bold: true, fontSize: 24, breakLine: true } },
    { text: "22년 생산·가격·경영비 데이터 분석과, 검증된 숫자로만 답하는 질의응답 에이전트", options: { fontSize: 16 } },
  ], { placeholder: "body" });
  text(s, "2026. 11.  기획서", { x: M, y: H - 0.9, w: 5, h: 0.4, fontSize: 14, color: C.background2 });
  s.addShape(pres.shapes.OVAL, { x: 8.55, y: 1.35, w: 4.3, h: 4.3, fill: { color: HEX.lt2, transparency: 88 }, line: { color: HEX.lt2, transparency: 88 }, objectName: "glow" });
  await fitImage(s, path.join(HERE, "mandarin.png"), { x: 8.7, y: 1.5, w: 4.0, h: 4.0 }, { objectName: "mandarin" });
  s.addNotes("감귤의 신(神)은 제주 감귤 데이터를 정리·분석하고, 그 결과를 누구나 질문으로 꺼내 볼 수 있게 만든 서비스입니다.");

  // 2. Problem ----------------------------------------------------------
  s = content("물어볼 곳이 마땅치 않은 세 가지 질문", "개요",
    "감귤 농사와 관련된 판단은 가격·생산량·비용 자료가 흩어져 있어 근거를 모으기 어렵습니다.");
  const qs = [
    [md.MdAgriculture, "기존 감귤 농가", "“올해는 언제 팔아야\n값을 더 받을까?”", HEX.accent1],
    [md.MdStorefront, "예비 창업자", "“어떤 품종이 비용을\n빼고도 더 남을까?”", HEX.accent2],
    [md.MdInsights, "수급·정책 담당", "“생산량이 몇 톤을\n넘으면 적자일까?”", HEX.accent5],
  ];
  for (let i = 0; i < 3; i++) {
    const x = M + i * 4.1, y = 1.55, w = 3.8, h = 3.1;
    card(s, x, y, w, h, "question card " + (i + 1));
    await iconCircle(s, x + 0.35, y + 0.35, 0.8, qs[i][0], qs[i][3], "question icon " + (i + 1));
    text(s, qs[i][1], { x: x + 1.35, y: y + 0.5, w: w - 1.6, h: 0.5, fontSize: 16, bold: true, color: MUTED });
    text(s, qs[i][2], { x: x + 0.35, y: y + 1.45, w: w - 0.7, h: 1.4, fontSize: 20, bold: true });
  }
  card(s, M, 5.0, W - 2 * M, 1.6, "data problem", "F2F8F3");
  await iconCircle(s, M + 0.35, 5.35, 0.8, md.MdScatterPlot, HEX.accent2, "scattered data icon");
  text(s, [
    { text: "답할 자료는 있지만 흩어져 있다", options: { bold: true, fontSize: 18, breakLine: true } },
    { text: "수급센터 통계표·간행물 PDF, 기상청, 물가지수가 따로 공개되고\n단위·기간·정의가 서로 달라, 비교하려면 정리부터 해야 한다", options: { fontSize: 15 } },
  ], { x: M + 1.4, y: 5.25, w: W - 2 * M - 1.8, h: 1.2 });

  // 3. Solution ---------------------------------------------------------
  s = content("해결 방안: 데이터를 정리·분석하고, 질문으로 꺼내 쓰게 한다", "개요",
    "1단계 데이터 정리, 2단계 분석, 3단계 에이전트로 전달. 에이전트는 분석 결과와 정제 데이터만 근거로 답합니다.");
  const steps = [
    [md.MdCleaningServices, "① 수집·정제", "5개 기관 자료를 통일", "품질 이슈 11건 처리", "표준소득표 판독·검산"],
    [md.MdQueryStats, "② 분석", "가격 탄력성·출하 시기", "기상과 생산량·가격", "경영비·물가 보정 소득", "손익분기·소득 분해"],
    [md.MdChat, "③ 질의응답 에이전트", "결론 → 근거 순서로 답", "검증된 숫자만 사용", "예측·단정은 하지 않음"],
  ];
  for (let i = 0; i < 3; i++) {
    const x = M + i * 4.15, y = 1.6, w = 3.75, h = 4.9;
    card(s, x, y, w, h, "step card " + (i + 1), i === 2 ? "FFE8CC" : HEX.lt2);
    await iconCircle(s, x + w / 2 - 0.5, y + 0.4, 1.0, steps[i][0], i === 2 ? HEX.accent1 : HEX.accent2, "step icon " + (i + 1));
    text(s, steps[i][1], { x: x + 0.3, y: y + 1.6, w: w - 0.6, h: 0.55, fontSize: 20, bold: true, align: "center" });
    text(s, steps[i].slice(2).map((t, k, a) => ({ text: t, options: { bullet: true, breakLine: k < a.length - 1 } })),
      { x: x + 0.35, y: y + 2.35, w: w - 0.6, h: 2.3, fontSize: 15, paraSpaceAfter: 10 });
    if (i < 2) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + w + 0.05, y: y + h / 2 - 0.2, w: 0.3, h: 0.4, fill: { color: HEX.accent1 }, line: { color: HEX.accent1 }, objectName: "arrow " + (i + 1) });
  }

  // 4. Data -------------------------------------------------------------
  pres.addSection({ title: "데이터" });
  s = content("22년, 8개 품종, 5개 기관의 데이터를 하나로", "데이터",
    "수급센터 자료는 이용약관상 제출본에 넣지 않고 수집 절차만 제공합니다. 나머지 공공 데이터는 함께 제출합니다.");
  const stats = [["22년", "2004~2025 생산·가격 통계"], ["8개", "노지·하우스·월동온주와\n만감류 5종"], ["5개", "자료 출처 기관"], ["20종", "정제 데이터셋"]];
  stats.forEach(([b, l], i) => stat(s, M + i * 3.1, 1.45, 2.8, b, l, i % 2 ? C.accent2 : C.accent1, 44));
  const rows = [
    ["출처", "데이터", "기간"],
    ["제주농산물수급관리센터", "품종별 생산·면적·조수입, 가공·수출, 일별·월별 가격, 유통처리, 표준소득표(경영비)", "2003~2026"],
    ["제주데이터허브", "제주 과수 품종별 생산 통계, 특용작물 생산현황", "2010~2023"],
    ["기상청 ASOS", "제주·고산·성산·서귀포 일자료 (기온·강수·일조·폭염일수)", "2004~2026"],
    ["통계청 · KOSIS", "소비자물가지수, 농가구입가격지수 (물가 보정)", "2004~2026"],
  ];
  s.addTable(rows.map((r, ri) => r.map((c) => ({ text: c, options: ri === 0
      ? { bold: true, color: C.background1, fill: { color: HEX.dk2 } }
      : { color: C.text1, fill: { color: ri % 2 ? "FFFFFF" : HEX.lt2 } } }))),
    { x: M, y: 3.55, w: W - 2 * M, colW: [2.9, 7.5, 1.733], fontSize: 13, border: { type: "solid", pt: 0.75, color: "EAD5B5" }, rowH: 0.5, valign: "middle", margin: 0.08 });

  // 5. Cleaning & quality -----------------------------------------------
  s = content("정제와 검증: 숫자를 믿을 수 있게 만드는 일", "데이터",
    "탐색 분석에서 품질 이슈 11건을 찾아 모두 원인을 확인하고 정제 코드로 처리했습니다. 다시 만들면 바이트 단위로 같은 결과가 나옵니다.");
  const flow = [["raw", "받은 그대로 보관\n(읽기 전용)"], ["interim", "품질 이슈 정정"], ["processed", "분석·에이전트용\n표준 CSV"]];
  flow.forEach(([t, d], i) => {
    const x = M + i * 2.15;
    card(s, x, 1.55, 1.85, 1.6, "pipeline " + t, i === 2 ? "FFE8CC" : HEX.lt2);
    text(s, t, { x: x + 0.15, y: 1.7, w: 1.55, h: 0.45, fontSize: 18, bold: true, align: "center", color: i === 2 ? C.accent1 : C.accent2 });
    text(s, d, { x: x + 0.15, y: 2.2, w: 1.55, h: 0.8, fontSize: 12, align: "center", color: MUTED });
    if (i < 2) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 1.88, y: 2.2, w: 0.24, h: 0.3, fill: { color: HEX.accent1 }, line: { color: HEX.accent1 }, objectName: "pipe arrow " + (i + 1) });
  });
  stat(s, M, 3.45, 6.2, "11건", "품질 이슈 모두 원인 확인·처리 (재생성 시 바이트 단위 동일)", C.accent1, 44);
  const qlist = ["연도 문자열", "합계 행 혼재", "증감률 열 이름 오기", "과수 대분류 오기·이중 집계", "중복·소계·미재배 행",
    "통계 기간 불일치", "월별 출하량 범위", "단가 정의", "2017년 면적 단절", "생산량 ≠ 처리량", "표 간 물량 차이"];
  card(s, M, 4.75, 6.2, 1.9, "issue list", "F7EFE2");
  [qlist.slice(0, 6), qlist.slice(6)].forEach((part, c) => text(s,
    part.map((q, i) => ({ text: `Q${i + 1 + c * 6}  ${q}`, options: { breakLine: i < part.length - 1 } })),
    { x: M + 0.3 + c * 3.0, y: 4.95, w: 2.9, h: 1.6, fontSize: 11, color: MUTED }));
  const issues = [
    [md.MdCalculate, "단가 = 조수입 ÷ 처리량", "생산량으로 나누면 15개 행이 어긋남\n→ 처리량 기준 확인·검증 컬럼 추가 (Q8)"],
    [md.MdWarningAmber, "2017년 재배면적 통계 단절", "만감류 면적만 2.5~4.4배로 급증\n→ 2016↔2017 면적 비교 금지 (Q9)"],
    [md.MdPictureAsPdf, "표준소득표 9개년 판독", "스캔본은 쪽 이미지를 보고 옮김\n모든 행 검산: 소득 = 총수입 − 경영비"],
  ];
  for (let i = 0; i < 3; i++) {
    const y = 1.55 + i * 1.65;
    card(s, 7.15, y, W - M - 7.15, 1.45, "issue card " + (i + 1));
    await iconCircle(s, 7.4, y + 0.3, 0.75, issues[i][0], i === 1 ? HEX.accent5 : HEX.accent2, "issue icon " + (i + 1));
    text(s, issues[i][1], { x: 8.35, y: y + 0.18, w: W - M - 8.55, h: 0.45, fontSize: 16, bold: true });
    text(s, issues[i][2], { x: 8.35, y: y + 0.62, w: W - M - 8.55, h: 0.75, fontSize: 12, color: MUTED });
  }

  // 6. Analysis 1 -------------------------------------------------------
  pres.addSection({ title: "분석 결과" });
  s = content("많이 나면 값이 떨어진다: 1% 증산에 단가 2~3% 하락", "분석 결과",
    "노지온주 2004~2025년 22개 연도. 기울기의 절댓값이 1보다 커서 물량이 늘면 총매출이 오히려 줄 수 있습니다. 관측된 관계이며 미래 가격 공식이 아닙니다.");
  await fitImage(s, IMG("fig_02_elasticity_scatter.png"), { x: M, y: 1.45, w: 7.6, h: 5.3 }, { objectName: "elasticity chart" });
  stat(s, 8.75, 1.6, 4.0, "−0.86", "노지온주 생산량–단가 상관계수\n(2004~2025, 22개 연도)");
  stat(s, 8.75, 3.25, 4.0, "−2.2 / −2.9", "로그 기울기 (전체 기간 / 최근 10년)", C.accent2, 34);
  card(s, 8.75, 5.05, 3.98, 1.55, "takeaway card", "FFE8CC");
  text(s, "증산이 매출 증가로 이어지지 않는다 → 출하 조절의 근거", { x: 8.95, y: 5.2, w: 3.6, h: 1.25, fontSize: 15, bold: true, valign: "middle" });
  SRC(s, "자료: 제주농산물수급관리센터 / 분석: 노트북 02 §3");

  // 7. Analysis 2 (native chart) ----------------------------------------
  s = content("매출 1위가 소득 1위는 아니다: 경영비를 빼면 천혜향", "분석 결과",
    "표준소득표 2024년산, 표본 농가 10a당. 하우스온주는 매출이 가장 높지만 난방 등 경영비가 53%라 소득은 천혜향보다 낮습니다.");
  const varieties = ["노지온주", "하우스온주", "월동온주", "한라봉", "천혜향", "레드향", "황금향"];
  s.addChart(pres.charts.BAR, [
    { name: "총수입", labels: varieties, values: [453.6, 2333.5, 1491.2, 1515.0, 1971.9, 1390.9, 1577.5] },
    { name: "소득 (총수입 − 경영비)", labels: varieties, values: [286.6, 1094.3, 968.6, 985.4, 1366.9, 757.3, 777.1] },
  ], {
    x: M, y: 1.4, w: 8.0, h: 5.4, barDir: "col", barGapWidthPct: 60,
    chartColors: ["F3C99B", HEX.accent1],
    showTitle: true, title: "2024년산 품종별 총수입과 소득 (만원/10a)", titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9, dataLabelColor: MUTED, dataLabelFormatCode: "#,##0", dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: MUTED, valAxisLabelColor: MUTED, catAxisLabelFontSize: 12, valAxisLabelFontSize: 10, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: "EEE3D2", size: 0.75 }, catGridLine: { style: "none" }, valAxisLabelFormatCode: "#,##0",
    showLegend: true, legendPos: "b", legendFontSize: 12, legendColor: MUTED, legendFontFace: "+mn-lt",
  });
  stat(s, 9.0, 1.55, 3.7, "53%", "하우스온주 경영비율 (2024년산)\n2016년산 41%에서 상승");
  stat(s, 9.0, 3.2, 3.7, "9년 연속", "천혜향 소득 2위 안 (2016~2024)\n2021·2023·2024년 1위", C.accent2, 36);
  stat(s, 9.0, 4.85, 3.7, "−40%", "하우스온주 실질 소득 2016→2024년산\n(1,586.5 → 958.4만원/10a, 2020년 물가)", C.accent5);
  SRC(s, "자료: 수급센터 「감귤유통처리 분석」 표준소득표 / 노트북 03");

  // 8. Analysis 3 (native chart) ----------------------------------------
  s = content("물가를 빼도 올랐나? 무엇으로 나누느냐에 달렸다", "분석 결과",
    "노지온주 실질 단가 2017→2025년. 생활물가 기준으로는 올랐지만 농사 비용 물가로 보면 오히려 내렸습니다. 같은 기간 노무비 2.9배, 농약비 2.4배.");
  s.addChart(pres.charts.BAR, [
    { name: "실질 단가 변화 (%)", labels: ["소비자물가(CPI)", "농가구입가격지수", "노지 경영비지수"], values: [16.8, 9.0, -4.9] },
  ], {
    x: M, y: 1.4, w: 7.4, h: 5.3, barDir: "bar", barGapWidthPct: 55, chartColors: [HEX.accent2, HEX.accent4, HEX.accent5],
    showTitle: true, title: "노지온주 실질 단가 변화, 2017→2025년 (%)", titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 14, dataLabelColor: HEX.dk1, dataLabelFormatCode: "+0.0;-0.0", dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 14, catAxisLabelFontFace: "+mn-lt", catAxisOrientation: "maxMin", catAxisLabelPos: "low",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, valAxisMinVal: -10, valAxisMaxVal: 22,
  });
  card(s, 8.4, 1.55, W - M - 8.4, 2.1, "insight card", "FFE8CC");
  text(s, [
    { text: "가격 상승 ≠ 농가 형편 개선", options: { bold: true, fontSize: 20, breakLine: true } },
    { text: "가격은 생활물가보다 빨리 올랐지만,\n노무비·농약비 등 농사 비용 상승을\n따라잡지 못했다", options: { fontSize: 15 } },
  ], { x: 8.65, y: 1.75, w: W - M - 8.9, h: 2.0 });
  stat(s, 8.4, 4.25, 2.0, "2.9배", "노무비", C.accent5, 36);
  stat(s, 10.6, 4.25, 2.0, "2.4배", "농약비", C.accent5, 36);
  text(s, "2017→2025년, 농가구입가격지수 항목", { x: 8.4, y: 5.85, w: 4.3, h: 0.4, fontSize: 12, color: MUTED });
  SRC(s, "자료: 통계청 CPI, KOSIS 농가구입가격지수, 수급센터 / 노트북 03 §2");

  // 9. Analysis 4 -------------------------------------------------------
  s = content("손익분기 47만 톤: 넘으면 평균 농가가 생산비 적자", "분석 결과",
    "생산량–매출 관계에 2026년산 비용 수준을 넣은 결과입니다. 2026년산 생산 전망이 나오면 이 경계와 비교해 출하 조절 판단에 쓸 수 있습니다.");
  text(s, "약 47만 톤", { x: M, y: 1.45, w: 4.3, h: 1.1, fontSize: 54, bold: true, color: C.accent1, valign: "bottom" });
  text(s, "제주 노지온주 생산량이 이 선을 넘으면\n평균 농가가 생산비 기준 적자\n(가격 변동 ±20% 감안 39~56만 톤)", { x: M, y: 2.65, w: 4.3, h: 1.3, fontSize: 14, color: MUTED });
  const be = [["45만 톤 (+10%)", "순수익 약 +20만원/10a", HEX.accent2], ["50만 톤 (+22%)", "순수익 약 −30만원/10a", HEX.accent5]];
  be.forEach(([a, b, col], i) => {
    const y = 4.2 + i * 1.2;
    card(s, M, y, 4.3, 1.0, "scenario " + (i + 1));
    text(s, a, { x: M + 0.25, y: y + 0.12, w: 3.8, h: 0.4, fontSize: 15, bold: true });
    text(s, b, { x: M + 0.25, y: y + 0.52, w: 3.8, h: 0.4, fontSize: 15, bold: true, color: col });
  });
  await fitImage(s, IMG("fig_04_noji_breakeven_production.png"), { x: 5.3, y: 1.45, w: W - M - 5.3, h: 4.0 }, { objectName: "breakeven chart" });
  text(s, "표준 농가 손익분기 단가 885원(2016) → 2,229원/kg(2024). 제주 평균 농가는 2019~2022년산 4년 연속 생산비 기준 적자.",
    { x: 5.3, y: 5.65, w: W - M - 5.3, h: 0.9, fontSize: 14 });
  SRC(s, "자료: 표준소득표 2016~2024년산 + 2015~2025년 가격 모델 / 노트북 04 §1");

  // 10. Analysis 5 ------------------------------------------------------
  s = content("소득은 왜 변했나: 가격·수량·경영비로 나눠 보기", "분석 결과",
    "2016~18년산 평균 → 2022~24년산 평균, 2020년 물가, 10a당. 표준 농가의 단가와 수량은 상관 −0.88로 값이 좋은 해는 수확이 적은 해였습니다.");
  await fitImage(s, IMG("fig_04_income_decomposition.png"), { x: M, y: 1.4, w: 7.7, h: 5.3 }, { objectName: "decomposition chart" });
  const dec = [
    ["노지온주 −43만원", "단가 +31%(+108)를\n수량 −25%(−116)가 상쇄하고,\n경영비 증가(−35)만큼 감소", HEX.accent1],
    ["하우스온주 −333만원", "가격·수량·경영비 세 요인 모두\n마이너스, 가장 크게 감소", HEX.accent5],
    ["천혜향·한라봉 증가", "수확량 증가(+20%, +14%)가\n소득을 끌어올림", HEX.accent2],
  ];
  dec.forEach(([a, b, col], i) => {
    const y = 1.55 + i * 1.7;
    card(s, 8.6, y, W - M - 8.6, 1.5, "decomposition card " + (i + 1));
    text(s, a, { x: 8.85, y: y + 0.15, w: W - M - 9.1, h: 0.45, fontSize: 17, bold: true, color: col });
    text(s, b, { x: 8.85, y: y + 0.6, w: W - M - 9.1, h: 0.85, fontSize: 13, color: C.text1 });
  });
  SRC(s, "단위: 만원/10a (2020년 물가) / 노트북 04 §2");

  // 11. Analysis 6 ------------------------------------------------------
  s = content("언제 팔고, 날씨는 어떻게 작용했나", "분석 결과",
    "출하 시기는 2021~2025년산 5개 시즌 출하량 가중 도매가격. 기상은 장기 추세를 제거한 뒤의 상관이며 인과가 아닙니다.");
  await fitImage(s, IMG("fig_02_season_price_flow.png"), { x: M, y: 1.45, w: W - 2 * M, h: 2.55 }, { objectName: "season price chart" });
  const half = (W - 2 * M - 0.4) / 2;
  card(s, M, 4.25, half, 2.4, "timing card");
  await iconCircle(s, M + 0.3, 4.5, 0.75, md.MdCalendarMonth, HEX.accent1, "timing icon");
  text(s, "출하 시기 (노지온주)", { x: M + 1.25, y: 4.6, w: half - 1.5, h: 0.5, fontSize: 17, bold: true });
  text(s, [
    { text: "10월 가격은 12월의 0.67~1.01배: 대체로 낮거나 비슷", options: { bullet: true, breakLine: true } },
    { text: "2월은 12월의 약 1.0~1.8배: 시즌마다 차이가 큼", options: { bullet: true } },
  ], { x: M + 0.3, y: 5.35, w: half - 0.6, h: 1.2, fontSize: 14, paraSpaceAfter: 6 });
  card(s, M + half + 0.4, 4.25, half, 2.4, "weather card");
  await iconCircle(s, M + half + 0.7, 4.5, 0.75, md.MdWbSunny, HEX.accent2, "weather icon");
  text(s, "날씨 (추세 제거 후 상관)", { x: M + half + 1.65, y: 4.6, w: half - 1.5, h: 0.5, fontSize: 17, bold: true });
  text(s, [
    { text: "여름 평균기온–단가 +0.83", options: { bullet: true, breakLine: true } },
    { text: "폭염일수–단가 +0.73", options: { bullet: true, breakLine: true } },
    { text: "폭염일수–면적당 생산량 −0.47", options: { bullet: true, breakLine: true } },
    { text: "더운 해에 수확은 적고 값은 높았음", options: { bullet: true } },
  ], { x: M + half + 0.7, y: 5.25, w: half - 0.6, h: 1.35, fontSize: 14, paraSpaceAfter: 2 });
  SRC(s, "자료: 수급센터 일별 가격, 기상청 ASOS / 노트북 02 §4·§6");

  // 12. Agent architecture ----------------------------------------------
  pres.addSection({ title: "에이전트" });
  s = content("숫자는 검증된 로컬 조회에서만 나온다", "에이전트",
    "모델은 질문 해석과 문장 정리만 맡습니다. 답에 나온 숫자는 조회 결과와 자동 대조해, 근거 없는 숫자가 있으면 다시 쓰게 하거나 뺍니다.");
  const arch = [
    [md.MdQuestionAnswer, "질문", "“2024년산 품종별\n소득 비교해줘”"],
    [md.MdPsychology, "해석", "로컬 규칙\n애매하면 Claude가\n조건을 되물음"],
    [md.MdStorage, "조회·계산", "정제 데이터 20종\n검증된 분석 카드 11개"],
    [md.MdFactCheck, "숫자 대조", "답의 모든 숫자를\n조회 결과와 비교"],
    [md.MdArticle, "답변", "결론 → 표·그래프·출처\nPDF 리포트"],
  ];
  const bw = 2.2, gap = (W - 2 * M - 5 * bw) / 4;
  for (let i = 0; i < 5; i++) {
    const x = M + i * (bw + gap);
    card(s, x, 1.6, bw, 2.75, "architecture " + arch[i][1], i === 3 ? "FFE8CC" : HEX.lt2);
    await iconCircle(s, x + bw / 2 - 0.4, 1.8, 0.8, arch[i][0], i === 3 ? HEX.accent1 : HEX.accent2, "architecture icon " + (i + 1));
    text(s, arch[i][1], { x: x + 0.1, y: 2.75, w: bw - 0.2, h: 0.45, fontSize: 17, bold: true, align: "center" });
    text(s, arch[i][2], { x: x + 0.15, y: 3.25, w: bw - 0.3, h: 1.0, fontSize: 12, align: "center", color: MUTED });
    if (i < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + bw + gap / 2 - 0.13, y: 2.8, w: 0.26, h: 0.34, fill: { color: HEX.accent1 }, line: { color: HEX.accent1 }, objectName: "flow arrow " + (i + 1) });
  }
  const princ = [
    [md.MdKeyOff, "API 키 없이도 동작", "키가 없으면 로컬 규칙으로\n모든 조회·분석에 답함\n(Claude Haiku 5.5는 선택)"],
    [md.MdBlock, "예측·단정은 하지 않음", "“내년 귤값?”에는 이유를 밝히고\n지난 기록으로 답할 질문을 제안"],
    [md.MdRule, "한계를 함께 밝힘", "표본 농가 기준, 순이익 아님,\n상관 ≠ 인과를 답마다 표시"],
  ];
  for (let i = 0; i < 3; i++) {
    const x = M + i * 4.1;
    await iconCircle(s, x, 4.8, 0.65, princ[i][0], HEX.accent5, "principle icon " + (i + 1));
    text(s, princ[i][1], { x: x + 0.85, y: 4.8, w: 3.0, h: 0.45, fontSize: 16, bold: true });
    text(s, princ[i][2], { x: x + 0.85, y: 5.3, w: 3.2, h: 1.2, fontSize: 13, color: MUTED });
  }

  // 13. Agent screens ---------------------------------------------------
  s = content("「감귤의 신(神)」 화면", "에이전트",
    "시작 화면에서 귤을 누르면 메인 화면. 답변은 결론, 표·그래프, 근거·출처 순. 애매한 질문에는 상담 모드가 조건을 되묻습니다. 휴대폰 화면도 지원합니다.");
  const shots = [
    ["app_02_main.png", "메인: 추천 질문과 입력칸"],
    ["app_05_breakeven.png", "답변: 결론과 그래프"],
    ["app_09_consult.png", "상담: 조건을 선택지로 되물음"],
  ];
  for (let i = 0; i < 3; i++) {
    const x = M + i * 4.1, box = { x, y: 1.45, w: 3.85, h: 4.6 };
    card(s, x - 0.05, 1.4, 3.95, 4.7, "screenshot frame " + (i + 1), "F7EFE2");
    await fitImage(s, IMG(shots[i][0]), { x: box.x + 0.05, y: box.y + 0.05, w: box.w - 0.1, h: box.h - 0.1 }, { objectName: shots[i][1] });
    text(s, shots[i][1], { x, y: 6.25, w: 3.85, h: 0.4, fontSize: 14, bold: true, align: "center" });
  }

  // 14. Impact -----------------------------------------------------------
  pres.addSection({ title: "기대 효과·계획" });
  s = content("기대 효과: 같은 데이터, 다른 결정", "기대 효과·계획",
    "같은 정제 데이터와 분석 결과를 사용자마다 필요한 질문으로 꺼내 쓰게 하는 것이 목표입니다.");
  const impact = [
    [md.MdAgriculture, "기존 농가", ["출하 시기별 가격 비교", "손익분기와 실제 단가 비교", "내 판매량으로 이익 계산"], HEX.accent1],
    [md.MdStorefront, "예비 창업자", ["비용 뺀 소득으로 품종 비교", "표준 농가 ≠ 평균 농가 안내", "자료에 없는 비용도 명시"], HEX.accent2],
    [md.MdInsights, "수급·정책 담당", ["생산 전망 vs 47만 톤 경계", "물가 기준별 실질 소득 점검", "근거·출처 붙은 리포트 공유"], HEX.accent5],
  ];
  for (let i = 0; i < 3; i++) {
    const x = M + i * 4.1, y = 1.55, w = 3.8, h = 3.75;
    card(s, x, y, w, h, "impact card " + (i + 1));
    await iconCircle(s, x + 0.35, y + 0.35, 0.85, impact[i][0], impact[i][3], "impact icon " + (i + 1));
    text(s, impact[i][1], { x: x + 1.4, y: y + 0.52, w: w - 1.6, h: 0.55, fontSize: 20, bold: true });
    text(s, impact[i][2].map((t, k, a) => ({ text: t, options: { bullet: true, breakLine: k < a.length - 1 } })),
      { x: x + 0.35, y: y + 1.5, w: w - 0.65, h: 2.1, fontSize: 16, paraSpaceAfter: 14 });
  }
  card(s, M, 5.6, W - 2 * M, 1.0, "impact banner", "FFE8CC");
  text(s, "하나의 정제 데이터와 검증된 분석 결과를, 사용자마다 필요한 질문으로 꺼내 쓴다",
    { x: M + 0.3, y: 5.6, w: W - 2 * M - 0.6, h: 1.0, fontSize: 18, bold: true, valign: "middle", align: "center" });

  // 15. Validation & next ----------------------------------------------
  s = pres.addSlide({ masterName: "CLOSING", sectionTitle: "기대 효과·계획" });
  s.addText("검증 결과와 다음 계획", { placeholder: "title" });
  s.addNotes("자동 검사와 노트북 재실행으로 검증했고, 다음 단계는 2026년산 생산 전망 연동과 빠진 자료 보강입니다.");
  const v = [["315개", "자동 검사 통과\n(데이터 52 · 에이전트 263)"], ["16/16", "경영비·손익분기\n오프라인 평가"], ["4/4", "분석 노트북\n처음부터 재실행"]];
  v.forEach(([b, l], i) => {
    text(s, b, { x: M + i * 2.45, y: 1.7, w: 2.3, h: 0.9, fontSize: 40, bold: true, color: C.accent3, valign: "bottom" });
    text(s, l, { x: M + i * 2.45, y: 2.65, w: 2.3, h: 0.9, fontSize: 13, color: C.background2 });
  });
  text(s, [
    { text: "다음 계획", options: { bold: true, fontSize: 20, breakLine: true } },
    { text: "농업관측센터 2026년산 생산 전망을 손익분기 경계(47만 톤)와 연동", options: { bullet: true, breakLine: true } },
    { text: "병해충·가온 시설 조건·농지와 시설 비용 데이터 보강", options: { bullet: true, breakLine: true } },
    { text: "가격 예측 모델 개선 (현재 오차 16.1%, 단순 기준선 16.9%와 비슷)", options: { bullet: true, breakLine: true } },
    { text: "수급센터 자료 이용 승낙을 받아 누구나 바로 실행할 수 있게 배포", options: { bullet: true } },
  ], { x: M, y: 3.95, w: 7.6, h: 3.0, fontSize: 15, color: C.background2, paraSpaceAfter: 8 });
  await fitImage(s, path.join(HERE, "mandarin.png"), { x: 9.2, y: 2.3, w: 3.4, h: 3.4 }, { objectName: "closing mandarin" });

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})().catch((e) => { console.error(e); process.exit(1); });
