#!/usr/bin/env python3
"""Собирает из Course Shell упрощённую оболочку для мастер-класса.

Убрано: attendance, аналитика и живая статистика, транскрипт речи (Whisper),
LanguageTool и Harper, проверка через ИИ, Speaking и Writing (блок с таймером
и автоматические проверки текстов). Остальное сохранено.

Запуск: python3 trim-shell.py <путь к Course Shell> <путь к папке вывода>
"""
import hashlib, re, shutil, sys
from pathlib import Path

SRC = Path(sys.argv[1]); OUT = Path(sys.argv[2])

# файлы, обрезка которых проверена на этих версиях
HASHES = {
    "docs/js/teacher.js": "4bf8861a5d6937ba",
    "docs/js/common.js": "d2f4c385ffb02232",
    "docs/js/student.js": "4de40ca20c298960",
    "docs/js/builder.js": "bc5a1faa05500749",
    "docs/js/sample-unit.js": "ede64ff05cf0a553",
    "docs/js/setup.js": "deca2c67a8cbbdfe",
}
COPY = [
    "docs/index.html", "docs/teacher.html", "docs/setup.html", "docs/firestore.rules.txt",
    "docs/css/course.css", "docs/img/cherdak.svg", "docs/media/sample/desk.svg",
    "docs/js/firebase-config.js", "docs/js/fb.js", "docs/js/settings.js",
    "docs/js/course-state.js", "docs/js/shell.js", "docs/js/export-docx.js",
    "docs/js/ai-prompt.js", "docs/js/vendor/docx.mjs", "docs/js/vendor/docx-LICENSE.txt",
    "firestore.rules", "LICENSE.md",
]
PATCH = ["docs/js/teacher.js", "docs/js/common.js", "docs/js/student.js",
         "docs/js/builder.js", "docs/js/sample-unit.js", "docs/js/setup.js"]

problems = []
for rel, want in HASHES.items():
    got = hashlib.sha256((SRC / rel).read_bytes()).hexdigest()[:16]
    if got != want:
        problems.append(f"{rel}: ожидался {want}, в папке {got}")
if problems:
    print("Файлы оболочки изменились с тех пор, как обрезку проверяли:")
    for p in problems: print("  " + p)
    print("Нужно сверить правки заново, иначе обрезка может сломать оболочку.")
    sys.exit(1)

def rep(text, old, new, count=1, label=""):
    n = text.count(old)
    if n != count:
        raise SystemExit(f"[{label}] фрагмент встречается {n} раз, ожидалось {count}:\n{old[:200]}")
    return text.replace(old, new)

def cut_lines(text, spans, label=""):
    """spans: [(first, last, ожидаемое начало первой строки)] — нумерация с 1, включительно."""
    lines = text.split("\n")
    for first, last, head in spans:
        got = lines[first - 1]
        if not got.lstrip().startswith(head):
            raise SystemExit(f"[{label}] строка {first} это «{got[:60]}», ожидалось «{head}»")
    drop = set()
    for first, last, _ in spans: drop.update(range(first, last + 1))
    return "\n".join(l for i, l in enumerate(lines, 1) if i not in drop)

# ------------------------------------------------------------------ teacher.js
def patch_teacher(t):
    t = cut_lines(t, [
        (406, 454, "// students of the group and their answers"),  # exStats, statSummary, itemBadge, mistakesHTML
        (465, 478, "function patchUnitStats()"),
        (495, 521, "// In-Class / HA and Done"),                   # слушатель плана и setPlanAs
        (523, 597, "// ====="),                                    # attendance целиком
        (624, 722, "// Free writing"),                             # writingBar, unitGrammar, checkWriting, checkTexts
        (723, 805, "// ====="),                                    # проверка грамматики, ИИ
        (818, 1105, "// ====="),                                   # Speaking и Writing progress
        (1373, 1472, "// ====="),                                  # аналитика и heat
    ], label="teacher.js")

    # импорты
    t = rep(t, '''import { loadVocab, checkGrammar, vocabProfile, unitVocabulary, feedbackHTML, sleep, findGrammar, textLevel } from "./writing.js?v=20261115d";
import { learnerIssues, expandGrammar, STRUCTURES } from "./grammar.js?v=20261115d";
import { aiCheck, aiReady, aiSettings, saveAiSettings, endpoint, PROVIDERS, listModels, testAi } from "./ai-check.js?v=20261115d";
''', "", label="teacher imports 1")
    t = rep(t, 'import "./speaking.js?v=20261115d";\n', "", label="teacher imports 2")
    t = rep(t, 'import { isWritingTask, measure, METRICS, metricsFor, toCSV } from "./progress.js?v=20261115d";\n', "", label="teacher imports 3")
    t = rep(t, 'import { LANGS, FIRST_LANGS, feat, langName } from "./course-state.js?v=20261115d";',
            'import { LANGS, FIRST_LANGS } from "./course-state.js?v=20261115d";', label="teacher imports 4")

    # состояние
    t = rep(t, '''  prog: null,            // Speaking and Writing progress: {gid, loading, tasks, rows, at, error}
  progOpt: { metric: { speaking: ls.get("progM:speaking", "wpm"), writing: ls.get("progM:writing", "words") }, student: "", setting: ls.get("progSet", ""), open: null },
''', "", label="T.prog")
    t = rep(t, '''  statsOnlySubmitted: false,
  journal: undefined,    // attendance of the current group: {lessons: {"2026-10-21": {absent: [uid]}}}
''', "", label="T.journal")
    t = rep(t, '''  mistOpen: new Set(),   // exercises whose list of students' mistakes is open
''', "", label="T.mistOpen")
    t = rep(t, '''// An absent student gets this share of the points for the in-class exercises of that lesson
const ABSENT_FACTOR = 0.25;

''', "", label="ABSENT_FACTOR")

    # список инструментов
    t = rep(t, '''  { id: "stats", icon: "📊", title: "Analytics", sub: "Difficult questions, heat map" },
  { id: "journal", icon: "📅", title: "Attendance", sub: "Lesson dates, present and absent" },
  { id: "speaking", icon: "🎙", title: "Speaking progress", sub: "Recordings as text: figures, trends, texts" },
  { id: "writing", icon: "✍", title: "Writing progress", sub: "Letters and essays: figures, trends, texts" },
  { id: "checker", icon: "🔎", title: "Grammar checker", sub: "LanguageTool or AI (Groq), the key" },
''', "", label="TOOLS")

    t = rep(t, '''{ id: "settings", icon: "⚙", title: "Course settings", sub: "Title, language, automatic checks" },''',
            '''{ id: "settings", icon: "⚙", title: "Course settings", sub: "Title, language, level" },''', label="settings tool label")

    # подписки: журнал посещаемости
    t = rep(t, '''  // attendance journal: kept in a teacher-only document (answerKeys/journal~<group>), students never receive it
  T.journal = undefined;
  T.ctxUnsub.push(onSnapshot(journalRef(T.gid), (snap) => {
    T.journal = snap.exists() ? snap.data() : { lessons: {} };
    T.journal.lessons ??= {};
    render();
  }, () => { T.journal = { lessons: {}, error: true }; render(); }));
''', "", label="journal snapshot")

    # перерисовка
    t = rep(t, '''  // A unit page that is already on the screen is not drawn again when students type:
  // only the live statistics are refreshed. The teacher's own answers, an audio file that is playing,
  // a flashcard or a recorder stay as they are.
  if (!force && r.unit && r.unit === T.unitId && T.unitViewKey && T.unitViewKey === unitViewKey(r)) { patchUnitStats(); return; }''',
        '''  // A unit page that is already on the screen is not drawn again when students type.
  // The teacher's own answers, an audio file that is playing or a flashcard stay as they are.
  if (!force && r.unit && r.unit === T.unitId && T.unitViewKey && T.unitViewKey === unitViewKey(r)) return;''',
        label="render patchUnitStats")
    t = rep(t, '''  const views = { access: viewAccess, works: viewWorks, tests: viewTests, stats: viewStats, content: viewContent, builder: viewBuilder, settings: viewSettings, groups: viewGroups, journal: viewJournal, checker: viewChecker, speaking: () => viewProgress("speaking"), writing: () => viewProgress("writing") };''',
        '''  const views = { access: viewAccess, works: viewWorks, tests: viewTests, content: viewContent, builder: viewBuilder, settings: viewSettings, groups: viewGroups };''',
        label="views map")

    # страница юнита
    t = rep(t, '''       Under each exercise title you can mark it <b>In-Class</b> or <b>HA</b> and tick <b>Done</b>. The figures on the right update live while the students work (drafts included).
''', "", label="tip plan line")
    t = rep(t, '''    + renderBlocks(blocks, (ex) => {
      const st = exStats(ex);
      if (T.viewAs) {''', '''    + renderBlocks(blocks, (ex) => {
      if (T.viewAs) {''', label="viewUnit exStats")
    t = rep(t, '''          key: graded ? null : d.keys[ex.id] || {}, readOnly: true, answers: ans,
          speech: vs?.answers?._speech?.[ex.id],
          auto''', '''          key: graded ? null : d.keys[ex.id] || {}, readOnly: true, answers: ans,
          auto''', label="viewUnit speech")
    t = rep(t, '''          before: g ? toolsBar(u, ex, g, st) : "",
          itemExtra: fbx ? (itemId) => feedbackHTML(fbx[itemId], { checkedAt: fmtTime(vexr.feedbackAt?.[ex.id]), teacher: true }) : null,
''', '''          before: g ? toolsBar(u, ex, g) : "",
''', label="viewUnit itemExtra")
    t = rep(t, '''        const fbx = vexr?.feedback?.[ex.id];
''', "", label="viewUnit fbx")
    t = rep(t, '''        tag: ex.check === "teacher" ? (isManual(ex) ? "Writing check by the teacher" : "Checked by the teacher") : "",
        before: g ? toolsBar(u, ex, g, st) : "",
        itemStat: st.items ? (itemId) => `<span class="istat" data-is="${esc(ex.id)}|${esc(itemId)}">${itemBadge(ex, st.items[itemId])}</span>` : null,
        after: st.items ? `<div class="mist" data-mi="${esc(ex.id)}" ${T.mistOpen.has(ex.id) ? "" : "hidden"}>${mistakesHTML(ex, st)}</div>` : "",
''', '''        tag: ex.check === "teacher" ? "Checked by the teacher" : "",
        before: g ? toolsBar(u, ex, g) : "",
''', label="viewUnit itemStat")

    # полоса над упражнением
    t = rep(t, '''// ================================================================== In-Class / HA, Done, live statistics
// The bar above each exercise in the Teacher's Edition.
function toolsBar(u, ex, g, st) {
  const p = g.plan?.[u.id]?.[ex.id] || {};
  const k = `${u.id}|${ex.id}`;
  const row = `<div class="tb-row">
    <span class="seg" role="group" aria-label="Type of work">
      <button type="button" class="${p.as === "class" ? "on" : ""}" data-act="plan-as" data-unit="${esc(u.id)}" data-ex="${esc(ex.id)}" data-as="class" title="Work done in class">In-Class</button><button type="button" class="${p.as === "home" ? "on" : ""}" data-act="plan-as" data-unit="${esc(u.id)}" data-ex="${esc(ex.id)}" data-as="home" title="Home assignment">HA</button>
    </span>
    <label class="tb-done ${p.done ? "on" : ""}"><input type="checkbox" data-plan-done="${esc(k)}" ${p.done ? "checked" : ""}> Done</label>
    ${p.done ? `<input type="date" class="tb-date" data-plan-date="${esc(k)}" value="${esc(p.date || "")}" title="The lesson when it was done">` : ""}
    <span class="sp" style="flex:1"></span>
    <span class="tstat" data-ts="${esc(ex.id)}">${statSummary(ex, st)}</span>
    ${st.items ? `<button class="btn small" type="button" data-act="mist" data-ex="${esc(ex.id)}">Mistakes</button>` : ""}
  </div>`;
  const check = ex.check === "teacher" ? (isManual(ex) ? writingBar(u, ex, g) : exerciseBar(u, ex, g)) : "";
  return `<div class="ex-bar tbar">${row}${check}</div>`;
}''', '''// The bar above each exercise in the Teacher's Edition: checking one exercise when the teacher decides.
function toolsBar(u, ex, g) {
  if (ex.check !== "teacher" || isManual(ex)) return "";
  return `<div class="ex-bar tbar">${exerciseBar(u, ex, g)}</div>`;
}''', label="toolsBar")

    # обработчики кнопок
    for line in ['    "check-writing": () => checkWriting(T.gid, u, b.dataset.ex),\n',
                 '    "ai-test": () => aiButton("ai-test"),\n',
                 '    "ai-models": () => aiButton("ai-models"),\n',
                 '    "try-check": () => tryCheck(),\n',
                 '    "prog-reload": () => { T.prog = null; T.progOpt.open = null; render(true); },\n',
                 '    "prog-csv": () => progressCSV(b.dataset.skill),\n',
                 '    "prog-close": () => { T.progOpt.open = null; render(true); },\n',
                 '    "hide-writing": () => guard(async () => updateDoc(doc(db, "groups", T.gid), { [`feedbackEx.${u}`]: arrayRemove(b.dataset.ex) })),\n',
                 '    "plan-as": () => setPlanAs(u, b.dataset.ex, b.dataset.as),\n',
                 '    "lesson-add": () => addLesson(),\n',
                 '    "lesson-del": () => deleteLesson(b.dataset.date),\n',
                 '    "att": () => toggleAbsent(b.dataset.date, b.dataset.uid),\n',
                 '    // Analytics: open the unit with this student\'s answers\n',
                 '    "view-unit-as": () => { T.viewAs = b.dataset.uid; location.hash = `#${T.unitId}`; },\n']:
        t = rep(t, line, "", label="handler " + line.strip()[:28])
    t = rep(t, '''    "prog-open": () => { T.progOpt.open = { uid: b.dataset.uid, key: b.dataset.key }; render(true); setTimeout(() => $("#prog-detail")?.scrollIntoView({ behavior: "smooth", block: "nearest" }), 30); },
''', "", label="handler prog-open")
    t = rep(t, '''    "prog-set": () => { T.progOpt.setting = b.dataset.set || ""; ls.set("progSet", T.progOpt.setting); T.progOpt.open = null; render(true); },
    "prog-student": () => { T.progOpt.student = b.dataset.uid || ""; T.progOpt.open = null; render(true); },
''', "", label="handler prog-set")
    t = rep(t, '''    "mist": () => {
      const id = b.dataset.ex;
      T.mistOpen.has(id) ? T.mistOpen.delete(id) : T.mistOpen.add(id);
      document.querySelectorAll(`[data-mi="${CSS.escape(id)}"]`).forEach((el) => (el.hidden = !T.mistOpen.has(id)));
    },
''', "", label="handler mist")
    t = rep(t, '''  if (e.target.id === "stats-submitted") { T.statsOnlySubmitted = e.target.checked; render(true); }
''', "", label="stats-submitted")

    # оценки без поправки на посещаемость
    t = rep(t, 'manual: prev[sub.uid]?.manual || {}, showCorrect: T.showCorrect, factors: factorsFor(sub.uid, unitId) });',
            'manual: prev[sub.uid]?.manual || {}, showCorrect: T.showCorrect });', label="releaseUnit factors")
    t = rep(t, '''    const f = factorsFor(st.uid, u.id), fN = Object.keys(f).length;
''', "", label="viewWorks factors")
    t = rep(t, '''      <td class="num">${auto ? `${fN ? adjustedAuto(auto, f) : auto.score} / ${auto.max}` : ""}${fN ? `<br><span class="pill warn" title="Absent: ${fN} in-class ${fN === 1 ? "exercise counts" : "exercises count"} ${Math.round(ABSENT_FACTOR * 100)}%">absent · ${fN}</span>` : ""}</td>''',
            '''      <td class="num">${auto ? `${auto.score} / ${auto.max}` : ""}</td>''', label="viewWorks auto cell")
    t = rep(t, '''“Auto” is a preliminary score against the keys (students do not see it until you release the results); for a student who was absent, in-class exercises of that lesson count ${Math.round(ABSENT_FACTOR * 100)}%. “Open” shows how many open answers you have already marked.''',
            '''“Auto” is a preliminary score against the keys (students do not see it until you release the results). “Open” shows how many open answers you have already marked.''', label="viewWorks lead")
    t = rep(t, '''  const u = unit(), n = unitNum(u);
  const f = factorsFor(uid, u.id);
''', '''  const u = unit(), n = unitNum(u);
''', label="studentDetail factors")
    t = rep(t, '''      answers: sub.answers?.[ex.id] || {},
      speech: sub.answers?._speech?.[ex.id],
      readOnly: true,
      auto: isAuto(ex) ? auto.items[ex.id] : undefined,
      factor: f[ex.id],
      manual: r?.manual?.[ex.id],
      grading: isManual(ex),
      itemExtra: T.exr?.[uid]?.feedback?.[ex.id] ? (itemId) => feedbackHTML(T.exr[uid].feedback[ex.id][itemId], { checkedAt: fmtTime(T.exr[uid].feedbackAt?.[ex.id]), teacher: true }) : null,
''', '''      answers: sub.answers?.[ex.id] || {},
      readOnly: true,
      auto: isAuto(ex) ? auto.items[ex.id] : undefined,
      manual: r?.manual?.[ex.id],
      grading: isManual(ex),
''', label="studentDetail renderExercise")
    t = rep(t, '''<span class="muted" style="font-size:16px">· auto-checked ${Object.keys(f).length ? adjustedAuto(auto, f) : auto.score}/${auto.max}</span>''',
            '''<span class="muted" style="font-size:16px">· auto-checked ${auto.score}/${auto.max}</span>''', label="studentDetail head")
    t = rep(t, 'const r = buildResult({ sub, content: data.content, keys: data.keys, manual, showCorrect, factors: factorsFor(uid, T.unitId) });',
            'const r = buildResult({ sub, content: data.content, keys: data.keys, manual, showCorrect });', label="saveGrades factors")

    # настройки курса
    t = rep(t, '''  const chk = (id, on, label, note, ok) => `<label class="set-chk ${ok ? "" : "na"}"><input type="checkbox" id="${id}" ${on ? "checked" : ""}> <span><b>${label}</b><br><span class="muted">${note}</span></span></label>`;
  const eng = feat.english();
  return pageHead("Teaching tools", "Course settings", "The name of the course, the language you teach and the automatic checks. Students see the changes after they reload the page.") + `''',
        '''  return pageHead("Teaching tools", "Course settings", "The name of the course and the language you teach. Students see the changes after they reload the page.") + `''', label="viewSettings head")
    t = rep(t, '''      <label class="bf"><span class="bf-l">Level (for the AI checker; can be empty)</span><input type="text" id="set-level" value="${esc(CS.level || "")}" placeholder="B1–B2"></label>
      <label class="bf"><span class="bf-l">Who the learners are (for the AI checker; can be empty)</span><input type="text" id="set-aud" value="${esc(CS.audience || "")}" placeholder="first-year university students of economics"></label>''',
        '''      <label class="bf"><span class="bf-l">Level of the course (can be empty)</span><input type="text" id="set-level" value="${esc(CS.level || "")}" placeholder="B1–B2"></label>
      <label class="bf"><span class="bf-l">Who the learners are (can be empty)</span><input type="text" id="set-aud" value="${esc(CS.audience || "")}" placeholder="first-year university students of economics"></label>''', label="viewSettings level")
    t = rep(t, '''<span class="bf-hint">LanguageTool uses it to find false friends; the AI checker is told about it.</span>''', "", label="viewSettings firstlang hint")
    t = rep(t, '''    <h3>Automatic checks of writing and speaking</h3>
    ${chk("set-gram", CS.grammarCheck !== false, "Grammar and spelling check", CS.lang === "none" ? "Not available: choose a language above." : `LanguageTool checks texts in ${esc(langName())} when you click “Check the writing now”${eng ? "; Harper checks them on your computer too" : ""}. The texts (without names) are sent to languagetool.org.`, CS.lang !== "none")}
    ${chk("set-rules", CS.courseRules !== false, "Typical mistakes of Russian-speaking learners of English", eng && CS.firstLang === "ru" ? "Extra rules written for this course engine (I am agree, explain me, depend from…)." : "Works when the course language is English and the learners' first language is Russian.", eng && CS.firstLang === "ru")}
    ${chk("set-levels", CS.levels !== false, "Vocabulary levels (CEFR)", eng ? "Words of each text are sorted by level A1–C2 (CEFR-J and Octanove word lists)." : "English only. In other languages the texts are still measured: words, lexical diversity, sentence length, unit phrases used.", eng)}
    ${chk("set-speech", CS.speech !== false, "Speech turned into text (Whisper in the student's browser)", eng ? "Students click Transcribe under a recording; you get the text, the speed and the pauses in Speaking progress." : "English only. In other languages students still record themselves, and type the text if you add such an exercise.", eng)}
''', "", label="viewSettings checks")
    t = rep(t, '''  <div class="box"><h3 style="margin-top:0">What is always collected</h3>
    <p class="muted" style="margin:0">Whatever the language, the course keeps the students' digital trace: every answer with the time of its last change, drafts before submission, Done marks, In-Class and HA marks, attendance, results of each exercise and test, texts and their feedback. See Analytics, Student work, Speaking progress and Writing progress; the progress pages have a CSV export for research.
    The first setup of the database is described in the <a href="setup.html" target="_blank">Setup guide</a>.</p></div>`;''',
        '''  <div class="box"><h3 style="margin-top:0">What is collected</h3>
    <p class="muted" style="margin:0">The course keeps every answer with the time of its last change, drafts before submission, Done marks and the results of every exercise and test. You see them in Student work.
    The first setup of the database is described in the <a href="setup.html" target="_blank">Setup guide</a>.</p></div>`;''', label="viewSettings collected")
    t = rep(t, '''      lang: $("#set-lang").value, firstLang: $("#set-first").value, level: $("#set-level").value.trim(), audience: $("#set-aud").value.trim(),
      grammarCheck: $("#set-gram").checked, courseRules: $("#set-rules").checked, levels: $("#set-levels").checked, speech: $("#set-speech").checked,
''', '''      lang: $("#set-lang").value, firstLang: $("#set-first").value, level: $("#set-level").value.trim(), audience: $("#set-aud").value.trim(),
''', label="saveCourseSettings flags")

    t = rep(t, """      const f = factorsFor(s.uid, unitId)[exId] ?? 1;      // absent from the lesson: 25% of the points
      batch.set(doc(db, "exerciseResults", subId(unitId, s.uid)), {
        uid: s.uid, groupId: gid, unitId,
        items: { [exId]: r.items }, scores: { [exId]: { score: r2(r.score * f), max: r.max } }, factors: { [exId]: f },""",
        """      batch.set(doc(db, "exerciseResults", subId(unitId, s.uid)), {
        uid: s.uid, groupId: gid, unitId,
        items: { [exId]: r.items }, scores: { [exId]: { score: r2(r.score), max: r.max } },""", label="checkExercise factor")

    # шапка файла
    t = rep(t, '''// Teacher's Edition: unit preview with keys, unit access per group, releasing results,
// manual assessment of open answers, analytics, content import, groups and students.''',
        '''// Teacher's Edition: unit preview with keys, unit access per group, releasing results,
// manual assessment of open answers, content import, groups and students.''', label="teacher header")
    return t

# ------------------------------------------------------------------ common.js
def patch_common(t):
    t = rep(t, 'import { metricsLine } from "./transcribe.js?v=20261115d";\n', "", label="common import")
    t = rep(t, '''    if (b.type === "speaking") return `<div class="block-spk">${speakingHTML(b, "blk-" + (b.id || hashStr(JSON.stringify(b))))}</div>`;
''', "", label="common speaking block")
    t = rep(t, '''      // "transcript": the text is written by the speech recogniser (speaking block with "transcribe"), not typed
      // (where speech recognition is not available for the language of the course, the student types the text)
      const tr = ex.transcript && it === ex.items[0] && feat.speech();
      let spLine = "";
      if (tr) { try { spLine = o.speech ? metricsLine(JSON.parse(o.speech)) : ""; } catch {} }
      const extra = tr ? `<input type="hidden" data-ex="_speech" data-item="${esc(ex.id)}" value="${esc(o.speech || "")}" ${dis}><div class="sp-line" data-sp-line="${esc(ex.id)}">${esc(spLine)}</div>` : "";
      const ph = o.readOnly ? "" : tr ? "Record your answer above and click Transcribe: the text will appear here." : "Type your answer here…";
      body = `${it.text}${model}<textarea class="open-answer ${tr ? "transcript" : ""}" rows="${it.rows || 5}" ${attrs} ${tr ? "readonly" : ""} ${NOAUTO} placeholder="${ph}">${esc(val)}</textarea>${extra}${wc}${o.itemExtra ? o.itemExtra(it.id) : ""}${grade}`;''',
        '''      const ph = o.readOnly ? "" : "Type your answer here…";
      body = `${it.text}${model}<textarea class="open-answer" rows="${it.rows || 5}" ${attrs} ${NOAUTO} placeholder="${ph}">${esc(val)}</textarea>${wc}${o.itemExtra ? o.itemExtra(it.id) : ""}${grade}`;''',
        label="common transcript")
    t = rep(t, "// speaking timers with a voice recorder: drawn by speaking.js (registered there)\n", "", label="common speaking comment")
    t = rep(t, '''let speakingImpl = () => "";
export function registerSpeaking(fn) { speakingImpl = fn; }
const speakingHTML = (t, key) => speakingImpl(t, key);
''', "", label="common speakingImpl")
    return t

# ------------------------------------------------------------------ student.js
def patch_student(t):
    t = rep(t, 'import { feedbackHTML } from "./writing.js?v=20261115d";\nimport "./speaking.js?v=20261115d";\n', "", label="student imports")
    t = rep(t, '''        itemExtra: fb ? (itemId) => feedbackHTML(fb[itemId], { checkedAt: fmtTime(fbAt) }) : null,
        answers: sub.answers?.[ex.id] || {},
        speech: sub.answers?._speech?.[ex.id],
''', '''        answers: sub.answers?.[ex.id] || {},
''', label="student itemExtra")
    t = rep(t, '''      const fbOn = (S.group.feedbackEx?.[unit.id] || []).includes(ex.id);
      const fb = fbOn && !res ? S.exr[unit.id]?.feedback?.[ex.id] : null;
      const fbAt = S.exr[unit.id]?.feedbackAt?.[ex.id];
''', "", label="student fb")
    t = rep(t, '''        tag: ex.check === "teacher" && !res ? (exDone ? "Checked" : fb ? "Feedback ready – you can correct your text" : "Checked by your teacher") : "",''',
            '''        tag: ex.check === "teacher" && !res ? (exDone ? "Checked" : "Checked by your teacher") : "",''', label="student tag")
    return t

# ------------------------------------------------------------------ builder.js
def patch_builder(t):
    t = rep(t, '''  ["speaking", "Speaking timer and recorder", "A countdown with a voice recorder"],
''', "", label="builder palette")
    t = rep(t, '''    case "speaking": return { type: "speaking", id: blockId(u), label: "", sec: 60 };
''', "", label="builder newBlock")
    t = rep(t, '''      ${disc ? "" : `<p class="bf-hint">The words on the cards become the vocabulary of the unit: the writing and speaking checks count how many of them a student used.</p>`}`;
  } else if (t === "speaking") {
    h += F("Label", "label", { ph: "Student A · compare the two pictures (1 minute)" }) + F("Time in seconds (0 = no countdown)", "sec", { as: "num" })
      + F("Voice recorder", "_rec", { as: "check", off: false, hint: " The recording stays in the student's browser; the student can listen to it and download it." });
    if (B.edit.isNew && !B.part.test) h += feat.speech()
      ? `<label class="bf check"><input type="checkbox" id="bf-transcript" checked> <span>Add an exercise for the text of the recording under this block<span class="bf-hint"> The student clicks Transcribe, the speech becomes text in the browser, and you get the text with speed and pauses for Speaking progress.</span></span></label>`
      : `<label class="bf check"><input type="checkbox" id="bf-transcript"> <span>Add an exercise under this block where the student types what was said<span class="bf-hint"> Automatic speech-to-text works in English courses only (Course settings: ${esc(langName())}).</span></span></label>`;
    if (d.transcribe) h += `<p class="bf-note">The text of this recording goes to exercise <code>${esc(d.transcribe)}</code> below it.</p>`;
  } else if (t === "image") {''',
        '''      ${disc ? "" : `<p class="bf-hint">The words on the cards become the vocabulary of the unit.</p>`}`;
  } else if (t === "image") {''', label="builder speaking form")
    t = rep(t, '''    h += (d.transcript ? `<p class="bf-note">This exercise receives the text of a recording (the speaking block above it). The first item is the text; do not delete it.</p>` : "")
      + `<div class="bf-rows">`''', '''    h += `<div class="bf-rows">`''', label="builder open note")
    t = rep(t, '''    + F(open ? `The automatic ${d.transcript ? "speaking" : "writing"} check is available (button “Check the ${d.transcript ? "speaking" : "writing"} now”); you give the marks in Student work` : "Students see the results when I click “Check this exercise now” (otherwise when I release the results of the whole unit)", "check", { as: "check", on: "teacher", off: undefined })''',
        '''    + F(open ? "You give the marks for this task in Student work" : "Students see the results when I click “Check this exercise now” (otherwise when I release the results of the whole unit)", "check", { as: "check", on: "teacher", off: undefined })''', label="builder check option")
    t = rep(t, '''    + F("Words and phrases this task practises, one per line", "vocab", { as: "lines", rows: 3, hint: "The writing and speaking checks count how many of them the student used. Empty: the vocabulary of the unit (flashcards) is used." });''',
        '''    + F("Words and phrases this task practises, one per line", "vocab", { as: "lines", rows: 3, hint: "Empty: the vocabulary of the unit (flashcards) is used." });''', label="builder vocab hint")
    t = rep(t, '''  if (t === "speaking") d._rec = b.record !== false;
''', "", label="builder draft rec")
    t = rep(t, '''  if (t === "speaking") { b.sec = Number(b.sec) || 0; if (b._rec === false) b.record = false; else delete b.record; delete b._rec; dropEmpty(b, ["label"]); return b; }
''', "", label="builder fromDraft")
    t = rep(t, '''      if (B.edit.isNew) {
        const add = [blk];
        // a speaking block may bring its exercise for the text of the recording
        if (B.edit.type === "speaking" && B.root.querySelector("#bf-transcript")?.checked) {
          const id = exId(B.unit);
          blk.transcribe = id;
          add.push({ type: "exercise", id, kind: "open", check: "teacher", transcript: true, max: 5, title: feat.speech() ? "Your answer as a text" : "What you said",
            rubric: feat.speech() ? "Record your answer above and click <b>Transcribe</b> under the recording. The text appears here." : "Record your answer above, listen to it and type what you said.",
            items: [{ id: "1", text: blk.label || "Your answer", rows: 6 }] });
        }
        list.splice(B.edit.index, 0, ...add);
      } else list[B.edit.index] = blk;''',
        '''      if (B.edit.isNew) list.splice(B.edit.index, 0, blk);
      else list[B.edit.index] = blk;''', label="builder save new")
    t = rep(t, '''    if (c.type === "exercise") { c.id = exId(B.unit); c.title = (c.title || "") + " (copy)"; delete c.transcript; }
    if (c.type === "speaking") { c.id = blockId(B.unit); delete c.transcribe; }
''', '''    if (c.type === "exercise") { c.id = exId(B.unit); c.title = (c.title || "") + " (copy)"; }
''', label="builder copy")
    t = rep(t, '''    list.splice(Number(b.dataset.i), 1);
    // a speaking block that pointed at a deleted transcript exercise loses the link
    if (blk.type === "exercise") list.forEach((x) => { if (x.type === "speaking" && x.transcribe === blk.id) delete x.transcribe; });
''', '''    list.splice(Number(b.dataset.i), 1);
''', label="builder delete")
    t = rep(t, '''// texts, pictures, audio, video, flashcards, speaking timers and exercises with their keys. No code and no files.''',
            '''// texts, pictures, audio, video, flashcards and exercises with their keys. No code and no files.''', label="builder header")
    return t

# ------------------------------------------------------------------ sample-unit.js
def patch_sample(t):
    t = rep(t, '''    { id: "speak-write", title: "Speaking and writing", subtitle: "Recorded answer and a short text", blocks: [
      { type: "html", html: "<p class=\\"rubric\\">Speak for one minute. <b>How do you organise your study time?</b> Say what works for you and what does not.</p>" },
      { type: "speaking", id: "sp1", label: "On your own · one minute", sec: 60, transcribe: "q5" },
      { type: "exercise", id: "q5", kind: "open", check: "teacher", transcript: true, max: 5, title: "Your answer as a text",
        rubric: "Record your answer above and click <b>Transcribe</b> under the recording. The text appears here.",
        vocab: ["meet a deadline", "put something off", "take a break", "distraction", "revise"],
        items: [{ id: "1", text: "How do you organise your study time?", rows: 6, answer: "I usually plan my week on Sunday evening. I try not to put things off, because I work badly under pressure. My phone is my biggest distraction, so I leave it in another room and take a break every hour." }] },
''', '''    { id: "speak-write", title: "Writing", subtitle: "A short text you mark yourself", blocks: [
''', label="sample speaking")
    return t

# ------------------------------------------------------------------ setup.js
def patch_setup(t):
    t = rep(t, '''      <li>Open the page of the course shell you were given and click <b>Use this template</b>, then <b>Create a new repository</b>. Give it a short Latin name without spaces (it becomes part of the address of your course), choose <b>Public</b> and click <b>Create repository</b>.<br>
        <span class="muted">Got the shell as a zip file instead? Create a new public repository, click <b>uploading an existing file</b>, unpack the zip on your computer and drag everything from the folder into the page, then <b>Commit changes</b>.</span></li>''',
        '''      <li>Click <b>New repository</b>. Give it a short Latin name without spaces (it becomes part of the address of your course), choose <b>Public</b> and click <b>Create repository</b>.</li>
      <li>Unpack the zip file you downloaded from the workshop page. In your new repository click <b>uploading an existing file</b>, drag the <b>docs</b> folder and the file <b>firestore.rules</b> into the page, and click <b>Commit changes</b>.</li>''',
        label="setup step 1")
    t = rep(t, '''      <ol><li>Open the <a href="https://console.firebase.google.com" target="_blank" rel="noopener">Firebase console</a> and click <b>Create a project</b> (or Add project). Any name; Google Analytics may be switched off. The free <b>Spark</b> plan is enough: do not upgrade.</li>''',
        '''      <p class="muted">If you typed your Firebase keys into the workshop page before you downloaded the files, this step is already green and you can go to step 3. Use the form below to move the course to another Firebase project.</p>
      <ol><li>Open the <a href="https://console.firebase.google.com" target="_blank" rel="noopener">Firebase console</a> and click <b>Create a project</b> (or Add project). Any name; Google Analytics may be switched off. The free <b>Spark</b> plan is enough: do not upgrade.</li>''',
        label="setup step 2")
    return t

PATCHERS = {"docs/js/teacher.js": patch_teacher, "docs/js/common.js": patch_common,
            "docs/js/student.js": patch_student, "docs/js/builder.js": patch_builder,
            "docs/js/sample-unit.js": patch_sample, "docs/js/setup.js": patch_setup}

for rel in COPY:
    dst = OUT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC / rel, dst)
for rel in PATCH:
    text = (SRC / rel).read_text(encoding="utf-8")
    out = PATCHERS[rel](text)
    dst = OUT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding="utf-8")
    print(f"{rel}: {len(text)} -> {len(out)} байт")

total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
print(f"Готово: {sum(1 for p in OUT.rglob('*') if p.is_file())} файлов, {total // 1024} КБ")
