import type { Metadata } from 'next';
import './globals.css';
import Header from '../components/Header';

export const metadata: Metadata = {
  title: { default: '源厂河北｜河北产业带与源头工厂', template: '%s｜源厂河北' },
  description: '按产品、城市和产业带查找河北源头工厂与特色制造产业，服务采购、选品与产业研究。',
  keywords: ['河北工厂', '源头工厂', '河北产业带', '采购', '工厂直供', '制造业'],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <Header />
        {children}
        <footer className="footer">
          <div className="container footerGrid">
            <div><b>源厂河北</b><p>把河北制造业做成可搜索、可验证、可联系的采购入口。</p></div>
            <div><b>数据说明</b><p>首版产业与企业基础数据引用“河北内卷网《河北产业开放数据》”，CC BY 4.0。平台后续将逐步建设自有审核与入驻数据。</p></div>
          </div>
        </footer>
      </body>
    </html>
  );
}
