'use client';

import { useState } from 'react';
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

const findings = [
  {
    level: 'สูง',
    kind: 'RULE',
    title: 'กำหนดผลงานเดิมสูงถึง 90%',
    detail:
      'เงื่อนไขประสบการณ์สูงผิดปกติเมื่อเทียบกับ TOR งานประเภทเดียวกัน อาจจำกัดการแข่งขัน',
    source: 'TOR หน้า 12 · ข้อ 6.3 คุณสมบัติผู้ยื่นข้อเสนอ',
    tone: 'danger',
  },
  {
    level: 'กลาง',
    kind: 'STAT',
    title: 'ระยะเวลายื่นข้อเสนอเพียง 6 วัน',
    detail:
      'สั้นกว่าค่ากลางของโครงการเทียบเคียง 11 วัน ทำให้ผู้ประกอบการเตรียมเอกสารได้ยาก',
    source: 'TOR หน้า 3 · กำหนดการจัดซื้อจัดจ้าง',
    tone: 'warning',
  },
  {
    level: 'เฝ้าระวัง',
    kind: 'ML',
    title: 'ชุดเงื่อนไขพบได้น้อยในโครงการคล้ายกัน',
    detail: 'โมเดลตรวจพบความผิดปกติ 0.71 จากราคา ระยะเวลา และข้อกำหนดร่วมกัน',
    source: 'เทียบกับ 284 โครงการในกลุ่มก่อสร้างอาคาร',
    tone: 'info',
  },
];

export default function Home() {
  const [running, setRunning] = useState(false);
  const [open, setOpen] = useState(0);
  function analyze() {
    setRunning(true);
    window.setTimeout(() => setRunning(false), 1400);
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
      <section className="workbench" id="analyze">
        <div className="document-panel">
          <div className="panel-head">
            <div>
              <span className="kicker">01 / INPUT</span>
              <h2>เอกสารที่ต้องการตรวจสอบ</h2>
            </div>
            <span className="filetype">PDF · 4.8 MB</span>
          </div>
          <label className="upload-zone">
            <input type="file" accept="application/pdf" />
            <span className="upload-icon">
              <Upload size={21} />
            </span>
            <span>
              <b>วางไฟล์ TOR ที่นี่</b>
              <small>หรือคลิกเพื่อเลือก PDF · สูงสุด 25 MB</small>
            </span>
          </label>
          <div className="file-row">
            <FileText size={22} />
            <div>
              <b>TOR_ก่อสร้างอาคารศูนย์บริการ.pdf</b>
              <small>38 หน้า · ตัวอย่างข้อมูลสำหรับ Prototype</small>
            </div>
            <span className="ready">พร้อมวิเคราะห์</span>
          </div>
          <button
            className="analyze-button"
            onClick={analyze}
            disabled={running}
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
          <p className="privacy">
            <ShieldCheck size={14} />
            ไฟล์ตัวอย่างไม่ถูกบันทึกหรือส่งต่อใน Prototype นี้
          </p>
        </div>
        <div className="scan-rail" aria-label="กระบวนการวิเคราะห์">
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
        </div>
        <div className="results-panel">
          <div className="panel-head">
            <div>
              <span className="kicker">02 / FINDINGS</span>
              <h2>สัญญาณที่ควรตรวจสอบต่อ</h2>
            </div>
            <span className="risk-count">3 ประเด็น</span>
          </div>
          <div className="score">
            <div>
              <span>ความเสี่ยงโดยรวม</span>
              <strong>72</strong>
              <small>/100</small>
            </div>
            <div className="meter">
              <i />
            </div>
            <p>สูงกว่าค่ากลางของโครงการประเภทเดียวกัน</p>
          </div>
          <div className="findings">
            {findings.map((f, i) => (
              <article className={`finding ${f.tone}`} key={f.title}>
                <button
                  onClick={() => setOpen(open === i ? -1 : i)}
                  aria-expanded={open === i}
                >
                  <span className="severity">
                    <AlertTriangle size={16} />
                    {f.level}
                  </span>
                  <span className="finding-title">
                    <small>{f.kind}</small>
                    <b>{f.title}</b>
                  </span>
                  <ChevronDown
                    className={open === i ? 'rotate' : ''}
                    size={18}
                  />
                </button>
                {open === i && (
                  <div className="evidence">
                    <p>{f.detail}</p>
                    <span>
                      <FileSearch size={15} />
                      {f.source}
                    </span>
                  </div>
                )}
              </article>
            ))}
          </div>
          <p className="disclaimer">
            <b>หมายเหตุ:</b> ผลลัพธ์เป็นสัญญาณเพื่อช่วยจัดลำดับการตรวจสอบ
            ไม่ใช่คำตัดสินการทุจริต
          </p>
        </div>
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
        <p>Prototype สำหรับการสาธิต · ข้อมูลและผลการวิเคราะห์ทั้งหมดเป็นตัวอย่าง</p>
      </footer>
    </main>
  );
}
