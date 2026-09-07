import type { Metadata } from 'next';
import Link from 'next/link';
import { getEnterprises } from '../../lib/hebei';

export const metadata: Metadata = { title: '河北工厂企业库', description: '查找河北产业带代表企业、主营产品、地址、官网与公开核验来源。' };

export default async function EnterprisesPage() {
  const data = await getEnterprises();
  return <main className="pageMain"><div className="container">
    <div className="pageTitle"><span className="sectionKicker">FACTORY DIRECTORY</span><h1>河北工厂企业库</h1><p>当前收录 {data.count ?? data.items.length} 家公开可核验代表企业。企业信息需以工商登记和企业官方信息为准。</p></div>
    <div className="enterpriseGrid">
      {data.items.map((e) => <Link className="enterpriseCard" href={`/enterprise/${e.id}`} key={e.id}>
        <div className="companyBadge">{e.name.slice(0, 1)}</div><div><h3>{e.name}</h3><p>{[e.city, e.county, e.cluster].filter(Boolean).join(' · ')}</p><div className="tags">{e.products?.slice(0, 4).map((p) => <span key={p}>{p}</span>)}</div></div>
      </Link>)}
    </div>
  </div></main>;
}
