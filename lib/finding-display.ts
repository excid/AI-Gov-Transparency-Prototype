export type FindingPresentationInput = {
  source: 'rule' | 'llm';
  page: number;
  confidence: number;
};

export function findingPresentation(finding: FindingPresentationInput) {
  return {
    sourceLabel: finding.source === 'llm' ? 'สรุปโดย AI' : 'กฎตรวจสอบ',
    pageLabel: `TOR หน้า ${finding.page}`,
    confidenceLabel: `ความมั่นใจ ${Math.round(finding.confidence * 100)}%`,
    lowConfidence: finding.confidence < 0.5,
  };
}
