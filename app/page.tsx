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
import { findingPresentation } from '../lib/finding-display';
import { projectTitle } from '../lib/project-display';
import { decodeProgressLines, type ProgressEvent } from '../lib/progress-stream';

type Finding = { category: string; severity: 'low' | 'medium' | 'high'; source: 'rule' | 'llm'; evidence: string; page: number; reason: string; confidence: number };
type ProjectSummary = { project_name: string | null; fiscal_year: number | null; budget_baht: number | null; reference_price_baht: number | null; purchase_method: string | null; project_type: string | null; duration_days: number | null };
type SimilarProject = { project_id: string; project_name: string | null; department: string; fiscal_year: number | null; budget_baht: number | null; purchase_method: string; project_type: string; duration_days: number | null; similarity_percent: number };
type Analysis = { summary: string; pageCount: number; ocrPages: number; findings: Finding[]; current_project?: ProjectSummary; model: { abstained: boolean; reason: string; percentile?: number | null; cohort_size: number; comparable_criteria: string[]; similar_projects: SimilarProject[] }; warnings: string[]; disclaimer: string };
const categoryLabels: Record<string, string> = { previous_work_percentage: 'สัดส่วนผลงานเดิม', brand_specific: 'ระบุยี่ห้อหรือรุ่น', unnecessary_certificate: 'ใบรับรองเฉพาะ', narrow_technical_requirement: 'ข้อกำหนดทางเทคนิคแคบ', experience_or_personnel: 'ประสบการณ์หรือบุคลากร', other_lock_spec: 'เงื่อนไขจำกัดอื่น' };
const analysisUrl =
  process.env.NEXT_PUBLIC_ANALYSIS_URL ??
  'http://127.0.0.1:8000/analyze-tor';
const pipelineVersion = 'paddle-th-rules-ml-qwen-v7-llm-project-name';
const stageLabels: Record<string, string> = {
  preparing: 'เตรียมไฟล์',
  received: 'รับไฟล์แล้ว',
  ocr: 'อ่านข้อความจากเอกสาร',
  screening: 'ตรวจเงื่อนไขและเทียบข้อมูล',
  llm: 'วิเคราะห์บริบทของ TOR',
  complete: 'วิเคราะห์เสร็จ',
};

export default function Home() {
  const [running, setRunning] = useState(false);
  const [open, setOpen] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<Analysis | null>(null);
  const [error, setError] = useState('');
  const [fromCache, setFromCache] = useState(false);
  const [resultTab, setResultTab] = useState<'findings' | 'similar'>('findings');
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
    setResultTab('findings');
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
          เครื่องมือช่วยตรวจ TOR ภาครัฐ
        </div>
        <h1>
          ตรวจ TOR ก่อนตัดสินใจ
        </h1>
        <p>
          ระบบชี้ข้อกำหนดที่อาจจำกัดการแข่งขัน พร้อมระบุหน้า เหตุผล
          และโครงการเปรียบเทียบ
        </p>
      </section>
      <section className={`workbench ${result ? 'result-mode' : 'upload-mode'}`} id="analyze">
        {!result && <div className="document-panel">
          <div className="panel-head">
            <div>
              <span className="kicker">01 / INPUT</span>
              <h2>อัปโหลดเอกสาร TOR</h2>
            </div>
            <span className="filetype">{file ? `PDF · ${(file.size / 1024 / 1024).toFixed(1)} MB` : 'PDF · สูงสุด 50 MB'}</span>
          </div>
          <label className="upload-zone">
            <input type="file" accept="application/pdf,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <span className="upload-icon">
              <Upload size={21} />
            </span>
            <span>
              <b>วางไฟล์ TOR หรือเลือกจากเครื่อง</b>
              <small>รองรับ PDF ขนาดไม่เกิน 50 MB</small>
            </span>
          </label>
          {file && <div className="file-row">
            <FileText size={22} />
            <div>
              <b>{file.name}</b>
              <small>{(file.size / 1024 / 1024).toFixed(2)} MB · ระบบใช้ OCR เมื่อ PDF ไม่มีข้อความให้อ่าน</small>
            </div>
            <span className="ready">ไฟล์พร้อม</span>
          </div>}
          <button
            className="analyze-button"
            onClick={() => analyze()}
            disabled={running || !file}
          >
            {running ? (
              <>
                <span className="spinner" />
                กำลังวิเคราะห์…
              </>
            ) : (
              <>
                <ScanSearch size={19} />
                ตรวจ TOR
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
            {progress.stage === 'ocr' && <small>เวลาประมวลผลขึ้นอยู่กับจำนวนหน้าและคุณภาพไฟล์</small>}
          </output>}
          <p className="privacy">
            <ShieldCheck size={14} />
            ระบบไม่เก็บไฟล์ PDF · ผลวิเคราะห์อยู่ในเบราว์เซอร์นี้
          </p>
          {error && <p className="analysis-error" role="alert">{error}</p>}
        </div>}
        {!result && <div className="scan-rail" aria-label="กระบวนการวิเคราะห์">
          <span className="rail-line" />
          {[
            [BrainCircuit, 'LLM', 'อ่านบริบท'],
            [Scale, 'กฎ', 'ตรวจข้อกำหนด'],
            [Sparkles, 'ML', 'เทียบโครงการ'],
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
          <h2>ผลตรวจพร้อมที่มา</h2>
          <p>แต่ละประเด็นระบุเหตุผล หน้าเอกสาร วิธีตรวจ และระดับความมั่นใจ ผู้ตรวจจึงเปิดเอกสารต้นฉบับเพื่อยืนยันได้</p>
          <ol><li><BrainCircuit size={18} /><span><b>LLM</b> อ่านบริบทและสรุปข้อกำหนด</span></li><li><Scale size={18} /><span><b>กฎตรวจสอบ</b> ตรวจเงื่อนไขที่อาจจำกัดการแข่งขัน</span></li><li><Sparkles size={18} /><span><b>ML</b> เทียบข้อมูลกับโครงการใน GovSpending</span></li></ol>
        </aside>}
        {result && <div className="results-panel">
          <div className="panel-head">
            <div>
              <span className="kicker">02 / FINDINGS</span>
              <h2>ประเด็นที่ควรตรวจต่อ</h2>
              <small className="result-meta">{result.pageCount} หน้า · ใช้ OCR {result.ocrPages} หน้า{fromCache ? ' · ใช้ผลเดิมในเครื่อง' : ''}</small>
            </div>
            <span className="risk-count">{result.findings.length} ประเด็น</span>
          </div>
          {result.current_project && <article className="current-project-card" aria-label="ข้อมูลโครงการที่กำลังวิเคราะห์">
            <div className="current-project-heading">
              <span><FileText size={16} />โครงการที่กำลังวิเคราะห์</span>
              <h3>{result.current_project.project_name || 'ไม่พบชื่อโครงการใน TOR'}</h3>
            </div>
            <div className="current-project-details">
              <span><b>ปีงบประมาณ</b>{result.current_project.fiscal_year ?? 'ไม่พบในเอกสาร'}</span>
              <span><b>วงเงิน</b>{result.current_project.budget_baht == null ? 'ไม่พบในเอกสาร' : `${result.current_project.budget_baht.toLocaleString('th-TH')} บาท`}</span>
              <span><b>ราคากลาง</b>{result.current_project.reference_price_baht == null ? 'ไม่พบในเอกสาร' : `${result.current_project.reference_price_baht.toLocaleString('th-TH')} บาท`}</span>
              <span><b>วิธีจัดซื้อ</b>{result.current_project.purchase_method ?? 'ไม่พบในเอกสาร'}</span>
              <span><b>ประเภท</b>{result.current_project.project_type ?? 'ไม่พบในเอกสาร'}</span>
              <span><b>ระยะเวลา</b>{result.current_project.duration_days == null ? 'ไม่พบในเอกสาร' : `${result.current_project.duration_days} วัน`}</span>
            </div>
          </article>}
          <div className="score">
            <div>
              <span>ระดับความผิดปกติเมื่อเทียบโครงการคล้ายกัน</span>
              <strong>{result.model.abstained ? '—' : Math.round(result.model.percentile ?? 0)}</strong>
              {!result.model.abstained && <small>/100</small>}
            </div>
            {!result.model.abstained && <div className="meter"><i style={{ width: `${result.model.percentile ?? 0}%` }} /></div>}
            <p>{result.model.abstained ? `ระบบไม่ประเมินด้วย ML: ${result.model.reason}` : `เทียบกับ ${result.model.cohort_size} โครงการ · ${result.model.comparable_criteria.join(' · ')}`}</p>
          </div>
          <p className="analysis-summary">{result.summary}</p>
          <div className="result-tabs" role="tablist" aria-label="ผลการวิเคราะห์">
            <button role="tab" aria-selected={resultTab === 'findings'} onClick={() => setResultTab('findings')}>
              ประเด็นที่พบ <span>{result.findings.length}</span>
            </button>
            <button role="tab" aria-selected={resultTab === 'similar'} onClick={() => setResultTab('similar')}>
              โครงการเปรียบเทียบ <span>{result.model.similar_projects?.length ?? 0}</span>
            </button>
          </div>
          {resultTab === 'findings' && <div className="findings" role="tabpanel">
            {result.findings.map((f, i) => {
              const presentation = findingPresentation(f);
              return (
              <article className={`finding ${f.severity === 'high' ? 'danger' : f.severity === 'medium' ? 'warning' : 'info'}`} key={`${f.category}-${f.page}-${i}`}>
                <button
                  onClick={() => setOpen(open === i ? -1 : i)}
                  aria-expanded={open === i}
                >
                  <span className="severity">
                    <AlertTriangle size={16} />
                    {f.severity === 'high' ? 'สูง' : f.severity === 'medium' ? 'กลาง' : 'ต่ำ'}
                  </span>
                  <span className="finding-title">
                    <small>{presentation.sourceLabel} · {presentation.pageLabel}</small>
                    <b>{categoryLabels[f.category] ?? f.category}</b>
                  </span>
                  <ChevronDown
                    className={open === i ? 'rotate' : ''}
                    size={18}
                  />
                </button>
                {open === i && (
                  <div className="evidence">
                    <p className="finding-summary">{f.reason}</p>
                    <span className="finding-reference">
                      <FileSearch size={15} />
                      {presentation.pageLabel} · {presentation.sourceLabel} · {presentation.confidenceLabel}
                    </span>
                    {presentation.lowConfidence && <small className="ocr-warning">ระบบอ่านข้อความส่วนนี้ได้ไม่ชัด โปรดตรวจหน้าต้นฉบับ</small>}
                    <details className="source-evidence">
                      <summary>อ่านข้อความที่ระบบดึงจากเอกสาร</summary>
                      <blockquote>“{f.evidence}”</blockquote>
                    </details>
                  </div>
                )}
              </article>
              );
            })}
            {result.findings.length === 0 && <div className="empty-findings">ไม่พบประเด็นจากข้อความที่ระบบอ่านได้</div>}
          </div>}
          {resultTab === 'similar' && <div className="similar-projects" role="tabpanel">
            {(result.model.similar_projects ?? []).map((project, index) => (
              <article className="similar-card" key={project.project_id}>
                <div className="similar-rank">{String(index + 1).padStart(2, '0')}</div>
                <div className="similar-main">
                  <small>รหัสโครงการ {project.project_id}</small>
                  <h3>{projectTitle(project)}</h3>
                  <div className="similar-details">
                    <span><b>หน่วยงาน</b>{project.department}</span>
                    <span><b>ปีงบประมาณ</b>{project.fiscal_year ?? 'ไม่ระบุ'}</span>
                    <span><b>วงเงิน</b>{project.budget_baht == null ? 'ไม่ระบุ' : `${project.budget_baht.toLocaleString('th-TH')} บาท`}</span>
                    <span><b>วิธีจัดซื้อ</b>{project.purchase_method}</span>
                    <span><b>ประเภท</b>{project.project_type}</span>
                    <span><b>ระยะเวลา</b>{project.duration_days == null ? 'ไม่ระบุ' : `${Math.round(project.duration_days)} วัน`}</span>
                  </div>
                </div>
                <div className="similar-score"><strong>{Math.round(project.similarity_percent)}%</strong><small>ใกล้เคียง</small></div>
              </article>
            ))}
            {(result.model.similar_projects?.length ?? 0) === 0 && <div className="empty-findings">ข้อมูลยังไม่พอสำหรับหาโครงการเปรียบเทียบ</div>}
            <p className="similar-note">คะแนนนี้แสดงความคล้ายของประเภท วิธีจัดซื้อ วงเงิน และระยะเวลาเท่านั้น</p>
          </div>}
          <p className="disclaimer">
            <b>ข้อควรทราบ:</b> ผู้ตรวจต้องยืนยันจากเอกสารต้นฉบับก่อนนำผลไปใช้
          </p>
          {result.warnings.length > 0 && <details className="warnings"><summary>ข้อควรตรวจสอบ ({result.warnings.length})</summary><ul>{result.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></details>}
          {fromCache && <button className="new-analysis" onClick={() => analyze(true)} disabled={running}>{running ? 'กำลังวิเคราะห์ใหม่…' : 'วิเคราะห์อีกครั้งโดยไม่ใช้ผลเดิม'}</button>}
          <button className="new-analysis" onClick={() => { setResult(null); setFile(null); setError(''); setOpen(0); setResultTab('findings'); }}>ตรวจเอกสารฉบับอื่น</button>
        </div>}
      </section>
      <section className="method" id="method">
        <div>
          <span className="kicker">HOW IT WORKS</span>
          <h2>ระบบตรวจ TOR อย่างไร</h2>
          <p>ระบบแยกผลจาก LLM กฎตรวจสอบ และแบบจำลอง ML พร้อมระบุที่มาของแต่ละประเด็น</p>
        </div>
        <ol>
          <li>
            <span>01</span>
            <BrainCircuit />
            <div>
              <b>อ่านบริบทด้วย LLM</b>
              <p>ดึงข้อกำหนดสำคัญ พร้อมข้อความอ้างอิงและเลขหน้า</p>
            </div>
          </li>
          <li>
            <span>02</span>
            <Scale />
            <div>
              <b>ตรวจด้วยกฎ</b>
              <p>ตรวจเงื่อนไขที่อาจเจาะจงผู้ขายหรือจำกัดการแข่งขัน</p>
            </div>
          </li>
          <li>
            <span>03</span>
            <Sparkles />
            <div>
              <b>เทียบโครงการด้วย ML</b>
              <p>เทียบวงเงิน ระยะเวลา และข้อมูลโครงการกับ GovSpending</p>
            </div>
          </li>
        </ol>
      </section>
      <footer>
        <span>AI-GOV Transparency</span>
        <p>ต้นแบบสำหรับการสาธิต · ผู้ตรวจต้องยืนยันทุกประเด็นจากเอกสารต้นฉบับ</p>
      </footer>
    </main>
  );
}
