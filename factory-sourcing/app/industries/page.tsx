import type { Metadata } from 'next';
import Link from 'next/link';
import { clusterName, clusterSlug, getClusters, sectorName } from '../../lib/hebei';

export const metadata: Metadata = { title: '河北产业带', description: '浏览河北特色制造产业带，按城市、区县和行业发现采购产地。' };

export default async function IndustriesPage() {
  const data = await getClusters();
  return <main className="pageMain"><div className="container">
    <div className="pageTitle"><span className="sectionKicker">INDUSTRIAL CLUSTERS</span><h1>河北产业带</h1><p>当前收录 {data.count ?? data.items.length} 个精选产业带。点击进入可查看产地、产业规模及相关企业。</p></div>
    <div className="cardGrid">
      {data.items.map((c) => <Link className="clusterCard" href={`/cluster/${clusterSlug(c)}`} key={c.id}>
        <div className="cardTop"><span className="pill">{sectorName(c.sector)}</span><span className="arrow">↗</span></div><h3>{clusterName(c)}</h3><p>{[c.city, c.county].filter(Boolean).join(' · ') || '河北'}</p><div className="cardMeta"><span>{c.output || c.honor || '查看产业详情'}</span></div>
      </Link>)}
    </div>
  </div></main>;
}
