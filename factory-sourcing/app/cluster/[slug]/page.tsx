import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { clusterName, clusterSlug, getClusters, getEnterprises, sectorName } from '../../../lib/hebei';

export async function generateStaticParams() {
  const data = await getClusters();
  return data.items.map((c) => ({ slug: clusterSlug(c) }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const data = await getClusters();
  const c = data.items.find((item) => clusterSlug(item) === slug);
  if (!c) return { title: '产业带' };
  return { title: clusterName(c), description: c.introZh || c.intro || `${clusterName(c)}产业带、产地与代表企业信息。` };
}

export default async function ClusterPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [clusters, enterpriseData] = await Promise.all([getClusters(), getEnterprises()]);
  const c = clusters.items.find((item) => clusterSlug(item) === slug);
  if (!c) notFound();
  const enterprises = enterpriseData.items.filter((e) => e.clusterSlug === slug);
  return <main className="pageMain"><div className="container detailWrap">
    <div className="breadcrumbs"><Link href="/">首页</Link><span>/</span><Link href="/industries">产业带</Link><span>/</span><span>{clusterName(c)}</span></div>
    <section className="detailHero"><div><span className="pill">{sectorName(c.sector)}</span><h1>{clusterName(c)}</h1><p>{[c.city, c.county].filter(Boolean).join(' · ') || '河北省'}</p></div><div className="detailStat"><small>相关代表企业</small><strong>{enterprises.length || c.enterprises || '持续补充'}</strong></div></section>
    <div className="detailGrid"><article className="contentCard"><h2>产业介绍</h2><p>{c.introZh || c.intro || '该产业带资料正在持续补充与核验。'}</p>{c.output && <><h2>产业规模</h2><p>{c.output}</p></>}{c.honor && <><h2>产业荣誉</h2><p>{c.honor}</p></>}</article>
      <aside className="sideCard"><h3>采购提示</h3><ul><li>先核验营业执照与实际经营地址</li><li>大货前先打样或小单测试</li><li>明确含税、物流、售后与交期</li><li>平台展示不等于交易担保</li></ul></aside>
    </div>
    <section className="detailSection"><div className="sectionHead"><div><h2>相关企业</h2><p>公开来源整理的代表企业。</p></div></div>
      {enterprises.length ? <div className="enterpriseGrid">{enterprises.map((e) => <Link className="enterpriseCard" href={`/enterprise/${e.id}`} key={e.id}><div className="companyBadge">{e.name.slice(0,1)}</div><div><h3>{e.name}</h3><p>{e.address || [e.city,e.county].filter(Boolean).join(' · ')}</p><div className="tags">{e.products?.slice(0,4).map((p)=><span key={p}>{p}</span>)}</div></div></Link>)}</div> : <div className="emptyPanel">暂无已关联代表企业，后续由工厂入驻与人工审核补充。</div>}
    </section>
  </div></main>;
}
