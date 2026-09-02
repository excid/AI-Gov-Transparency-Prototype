import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'AI-GOV Transparency | TOR Risk Screening',
  description: 'ระบบคัดกรองสัญญาณความเสี่ยงใน TOR ด้วย AI กฎตรวจสอบ และข้อมูลเทียบเคียง',
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <body>{children}</body>
    </html>
  );
}
