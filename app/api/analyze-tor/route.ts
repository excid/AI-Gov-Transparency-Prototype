const MAX_BYTES = 50 * 1024 * 1024;

export async function POST(request: Request) {
  let form: FormData;
  try { form = await request.formData(); } catch { return Response.json({ error: 'ระบบอ่านข้อมูลที่อัปโหลดไม่ได้' }, { status: 400 }); }
  const file = form.get('file');
  if (!(file instanceof File) || !file.name.toLowerCase().endsWith('.pdf')) return Response.json({ error: 'กรุณาเลือกไฟล์ PDF' }, { status: 400 });
  if (file.size > MAX_BYTES) return Response.json({ error: 'PDF ต้องมีขนาดไม่เกิน 50 MB' }, { status: 413 });
  const serviceUrl = process.env.ML_SERVICE_URL ?? 'http://127.0.0.1:8000';
  try {
    const upstream = new FormData(); upstream.set('file', file, file.name);
    const response = await fetch(`${serviceUrl}/analyze-tor`, { method: 'POST', body: upstream, signal: AbortSignal.timeout(300_000) });
    const result = await response.json() as Record<string, unknown>;
    const detail = typeof result.detail === 'string' ? result.detail : 'ระบบวิเคราะห์ PDF ไม่สำเร็จ';
    if (!response.ok) return Response.json({ error: detail }, { status: response.status });
    return Response.json(result, { headers: { 'Cache-Control': 'no-store' } });
  } catch { return Response.json({ error: 'เชื่อมต่อระบบวิเคราะห์ TOR ไม่ได้ โปรดลองอีกครั้ง' }, { status: 503 }); }
}
