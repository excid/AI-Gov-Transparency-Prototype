'use client';

import { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  BrainCircuit,
  ChevronDown,
  FileSearch,
  FileText,
  Scale,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Upload,
} from 'lucide-react';
import { getCachedAnalysis, IndexedDbAnalysisStore, putCachedAnalysis } from '../lib/analysis-cache';
import { decodeProgressLines, type ProgressEvent } from '../lib/progress-stream';

type Finding = { category: string; severity: 'low' | 'medium' | 'high'; source: 'rule' | 'llm'; evidence: string; page: number; reason: string; confidence: number };
type Analysis = { summary: string; pageCount: number; ocrPages: number; findings: Finding[]; model: { abstained: boolean; reason: string; percentile?: number | null; cohort_size: number; comparable_criteria: string[] }; warnings: string[]; disclaimer: string };
const categoryLabels: Record<string, string> = { previous_work_percentage: 'สัดส่วนผลงานเดิม', brand_specific: 'ระบุยี่ห้อหรือรุ่น', unnecessary_certificate: 'ใบรับรองเฉพาะ', narrow_technical_requirement: 'ข้อกำหนดทางเทคนิคแคบ', experience_or_personnel: 'ประสบการณ์หรือบุคลากร', other_lock_spec: 'เงื่อนไขจำกัดอื่น' };
const analysisUrl = process.env.NEXT_PUBLIC_ANALYSIS_URL ?? '/api/analyze-tor';
const pipelineVersion = 'paddle-th-rules-ml-qwen-v3-thai-output';
const stageLabels: Record<string, string> = {
  preparing: 'กำลังเตรียมไฟล์',
  received: 'อัปโหลดไฟล์สำเร็จ',
  ocr: 'กำลังอ่านทุกหน้าด้วย OCR',
  screening: 'กำลังตรวจด้วยกฎและ ML',
  llm: 'กำลังวิเคราะห์บริบทด้วย LLM',
  complete: 'วิเคราะห์เสร็จแล้ว',
};

export default function Home() {
  const [running, setRunning] = useState(false);
  const [open, setOpen] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<Analysis | null>(null);
  const [error, setError] = useState('');
  const [fromCache, setFromCache] = useState(false);
  const [progress, setProgress] = useState({ stage: '', percent: 0 });
  const [elapsed, setElapsed] = useState(0);
  const cacheStore = useRef<IndexedDbAnalysisStore | null>(null);
  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  async function analyze(force = false) {
    if (!file) return;
    setRunning(true);
    setError('');
    setResult(null);
    setFromCache(false);
    setElapsed(0);
    setProgress({ stage: 'preparing', percent: 2 });
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      cacheStore.current ??= new IndexedDbAnalysisStore();
      if (!force) {
        try {
          const cached = await getCachedAnalysis<Analysis>(cacheStore.current, bytes, pipelineVersion);
          if (cached) {
            setProgress({ stage: 'complete', percent: 100 });
            setResult(cached);
            setFromCache(true);
            return;
          }
        } catch {
          // Private browsing or storage restrictions must not block analysis.
        }
      }
      const form = new FormData(); form.set('file', file);
      const response = await fetch(`${analysisUrl.replace(/\/$/, '')}/stream`, { method: 'POST', body: form });
      if (!response.ok || !response.body) {
        const failure = await response.json().catch(() => ({})) as { detail?: string };
        throw new Error(failure.detail ?? 'วิเคราะห์ไม่สำเร็จ');
      }
      const reader = response.body.getReader();
      const textDecoder = new TextDecoder();
      const eventDecoder = decodeProgressLines();
      let body: Analysis | null = null;
      const accept = (event: ProgressEvent) => {
        if (event.type === 'progress') setProgress({ stage: event.stage, percent: event.percent });
        if (event.type === 'result') body = event.data as Analysis;
        if (event.type === 'error') throw new Error(event.message);
      };
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        eventDecoder.push(textDecoder.decode(value, { stream: true })).forEach(accept);
      }
      eventDecoder.push(textDecoder.decode()).forEach(accept);
      eventDecoder.finish().forEach(accept);
      if (!body) throw new Error('การเชื่อมต่อสิ้นสุดก่อนรับผลวิเคราะห์');
      setResult(body);
      try {
        await putCachedAnalysis(cacheStore.current, bytes, pipelineVersion, body);
      } catch {
        // The analysis remains valid even when browser storage is unavailable.
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'วิเคราะห์ไม่สำเร็จ');
    } finally {
      setRunning(false);
    }
  }
  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="AI-GOV Transparency">
          <span className="brandmark">
            <ShieldCheck size={19} />
          </span>
          <span>
            AI-GOV <b>TRANSPARENCY</b>
          </span>
        </a>
        <nav>
          <a href="#analyze">วิเคราะห์ TOR</a>
          <a href="#method">วิธีการทำงาน</a>
          <span className="prototype">PROTOTYPE</span>
        </nav>
      </header>
      <section className="hero" id="top">
        <div className="eyebrow">
          <span />
          ระบบคัดกรองความเสี่ยงจัดซื้อจัดจ้างภาครัฐ
        </div>
        <h1>
          เห็นสัญญาณเสี่ยง
          <br />
          <em>ก่อนความเสียหายเกิดขึ้น</em>
        </h1>
        <p>
          วิเคราะห์ TOR ด้วย AI กฎตรวจสอบ และข้อมูลโครงการเทียบเคียง
          พร้อมหลักฐานที่ตรวจย้อนกลับได้
        </p>
      </section>
      <section className={`workbench ${result ? 'result-mode' : 'upload-mode'}`} id="analyze">
        {!result && <div className="document-panel">
          <div className="panel-head">
            <div>
              <span className="kicker">01 / INPUT</span>
              <h2>เอกสารที่ต้องการตรวจสอบ</h2>
            </div>
            <span className="filetype">{file ? `PDF · ${(file.size / 1024 / 1024).toFixed(1)} MB` : 'PDF · สูงสุด 50 MB'}</span>
          </div>
          <label className="upload-zone">
            <input type="file" accept="application/pdf,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <span className="upload-icon">
              <Upload size={21} />
            </span>
            <span>
              <b>วางไฟล์ TOR ที่นี่</b>
              <small>หรือคลิกเพื่อเลือก PDF · สูงสุด 50 MB</small>
            </span>
          </label>
          {file && <div className="file-row">
            <FileText size={22} />
            <div>
              <b>{file.name}</b>
              <small>{(file.size / 1024 / 1024).toFixed(2)} MB · พร้อมตรวจข้อความด้วย PaddleOCR ภาษาไทย</small>
            </div>
            <span className="ready">พร้อมวิเคราะห์</span>
          </div>}
          <button
            className="analyze-button"
            onClick={() => analyze()}
            disabled={running || !file}
          >
            {running ? (
              <>
                <span className="spinner" />
                กำลังตรวจสอบหลักฐาน…
              </>
            ) : (
              <>
                <ScanSearch size={19} />
                เริ่มวิเคราะห์ความเสี่ยง
              </>
            )}
          </button>
          {running && <output className="analysis-progress" aria-live="polite">
            <div className="progress-copy">
              <b>{stageLabels[progress.stage] ?? 'กำลังวิเคราะห์'}</b>
              <span>{progress.percent}% · {elapsed} วินาที</span>
            </div>
            <div className={`progress-track ${progress.stage === 'ocr' ? 'is-ocr' : ''}`}>
              <i style={{ width: `${progress.percent}%` }} />
            </div>
            {progress.stage === 'ocr' && <small>OCR ใช้เวลาตามจำนวนหน้าและคุณภาพเอกสาร</small>}
          </output>}
          <p className="privacy">
            <ShieldCheck size={14} />
            ไม่เก็บไฟล์ PDF · เก็บเฉพาะผลวิเคราะห์ในเบราว์เซอร์ของคุณ
          </p>
          {error && <p className="analysis-error" role="alert">{error}</p>}
        </div>}
        {!result && <div className="scan-rail" aria-label="กระบวนการวิเคราะห์">
          <span className="rail-line" />
          {[
            [BrainCircuit, 'LLM', 'ดึงข้อมูล'],
            [Scale, 'RULES', 'ตรวจเงื่อนไข'],
            [Sparkles, 'ML', 'เทียบความผิดปกติ'],
          ].map(([Icon, code, label]) => {
            const C = Icon as typeof BrainCircuit;
            return (
              <div className="stage" key={String(code)}>
                <span>
                  <C size={18} />
                </span>
                <b>{String(code)}</b>
                <small>{String(label)}</small>
              </div>
            );
          })}
        </div>}
        {!result && <aside className="results-panel waiting-panel">
          <span className="kicker">02 / WHAT YOU GET</span>
          <h2>ผลลัพธ์ที่ตรวจย้อนกลับได้</h2>
          <p>ระบบจะแสดงข้อความหลักฐาน หน้าเอกสาร วิธีที่ตรวจพบ ความมั่นใจ และกลุ่มโครงการที่ใช้เปรียบเทียบ โดยไม่สรุปว่าเป็นการทุจริต</p>
          <ol><li><BrainCircuit size={18} /><span><b>LLM</b> อ่านบริบทและอธิบายข้อกำหนด</span></li><li><Scale size={18} /><span><b>RULES</b> ตรวจหกกลุ่มเงื่อนไขล็อกสเปก</span></li><li><Sparkles size={18} /><span><b>ML</b> เปรียบเทียบกับข้อมูล GovSpending แบบ unsupervised</span></li></ol>
        </aside>}
        {result && <div className="results-panel">
          <div className="panel-head">
            <div>
              <span className="kicker">02 / FINDINGS</span>
              <h2>สัญญาณที่ควรตรวจสอบต่อ</h2>
              <small className="result-meta">{result.pageCount} หน้า · OCR {result.ocrPages} หน้า{fromCache ? ' · ผลจากแคชในอุปกรณ์' : ''}</small>
            </div>
            <span className="risk-count">{result.findings.length} ประเด็น</span>
          </div>
          <div className="score">
            <div>
              <span>ความผิดปกติเทียบโครงการใกล้เคียง</span>
              <strong>{result.model.abstained ? '—' : Math.round(result.model.percentile ?? 0)}</strong>
              {!result.model.abstained && <small>/100</small>}
            </div>
            {!result.model.abstained && <div className="meter"><i style={{ width: `${result.model.percentile ?? 0}%` }} /></div>}
            <p>{result.model.abstained ? `ML งดให้คะแนน: ${result.model.reason}` : `เทียบกับ ${result.model.cohort_size} โครงการ · ${result.model.comparable_criteria.join(' · ')}`}</p>
          </div>
          <p className="analysis-summary">{result.summary}</p>
          <div className="findings">
            {result.findings.map((f, i) => (
              <article className={`finding ${f.severity === 'high' ? 'danger' : f.severity === 'medium' ? 'warning' : 'info'}`} key={`${f.category}-${f.page}-${i}`}>
                <button
                  onClick={() => setOpen(open === i ? -1 : i)}
                  aria-expanded={open === i}
                >
                  <span className="severity">
                    <AlertTriangle size={16} />
                    {f.severity === 'high' ? 'สูง' : f.severity === 'medium' ? 'กลาง' : 'เฝ้าระวัง'}
                  </span>
                  <span className="finding-title">
                    <small>{f.source === 'rule' ? 'RULE' : 'LLM'} · หน้า {f.page}</small>
                    <b>{categoryLabels[f.category] ?? f.category}</b>
                  </span>
                  <ChevronDown
                    className={open === i ? 'rotate' : ''}
                    size={18}
                  />
                </button>
                {open === i && (
                  <div className="evidence">
                    <blockquote>“{f.evidence}”</blockquote>
                    <p>{f.reason}</p>
                    <span>
                      <FileSearch size={15} />
                      TOR หน้า {f.page} · ความมั่นใจ {Math.round(f.confidence * 100)}%
                    </span>
                  </div>
                )}
              </article>
            ))}
            {result.findings.length === 0 && <div className="empty-findings">ยังไม่พบเงื่อนไขที่เข้ากฎคัดกรองจากข้อความที่ OCR อ่านได้</div>}
          </div>
          <p className="disclaimer">
            <b>หมายเหตุ:</b> ผลลัพธ์เป็นสัญญาณเพื่อช่วยจัดลำดับการตรวจสอบ
            ไม่ใช่คำตัดสินการทุจริต
          </p>
          {result.warnings.length > 0 && <details className="warnings"><summary>ข้อจำกัดของผลลัพธ์ ({result.warnings.length})</summary><ul>{result.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></details>}
          {fromCache && <button className="new-analysis" onClick={() => analyze(true)} disabled={running}>{running ? 'กำลังวิเคราะห์ใหม่…' : 'ข้ามแคชและวิเคราะห์ไฟล์นี้ใหม่'}</button>}
          <button className="new-analysis" onClick={() => { setResult(null); setFile(null); setError(''); setOpen(0); }}>วิเคราะห์เอกสารใหม่</button>
        </div>}
      </section>
      <section className="method" id="method">
        <div>
          <span className="kicker">HOW IT WORKS</span>
          <h2>หนึ่งเอกสาร สามชั้นการตรวจสอบ</h2>
          <p>ทุกข้อสังเกตต้องแสดงที่มา เหตุผล และข้อจำกัด เพื่อให้มนุษย์ตัดสินใจบนหลักฐาน</p>
        </div>
        <ol>
          <li>
            <span>01</span>
            <BrainCircuit />
            <div>
              <b>LLM Extraction</b>
              <p>อ่าน TOR และแปลงข้อกำหนดสำคัญเป็นข้อมูลที่ตรวจสอบได้</p>
            </div>
          </li>
          <li>
            <span>02</span>
            <Scale />
            <div>
              <b>Rule-based Screening</b>
              <p>ตรวจเงื่อนไขล็อกสเปก ระยะเวลา และเกณฑ์ที่จำกัดการแข่งขัน</p>
            </div>
          </li>
          <li>
            <span>03</span>
            <Sparkles />
            <div>
              <b>ML Comparison</b>
              <p>เปรียบเทียบกับโครงการคล้ายกันเพื่อค้นหารูปแบบผิดปกติ</p>
            </div>
          </li>
        </ol>
      </section>
      <footer>
        <span>AI-GOV Transparency</span>
        <p>Prototype สำหรับการสาธิต · ผลลัพธ์เป็นสัญญาณเพื่อให้มนุษย์ตรวจสอบต่อ</p>
      </footer>
    </main>
  );
}
