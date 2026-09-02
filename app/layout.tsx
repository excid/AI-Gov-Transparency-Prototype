import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'AI-GOV Transparency | TOR Risk Screening',
  description: 'เครื่องมือช่วยตรวจข้อกำหนดใน TOR พร้อมเหตุผล เลขหน้า และโครงการเปรียบเทียบ',
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
