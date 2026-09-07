import Link from 'next/link';
import SearchBox from '../components/SearchBox';
import { clusterName, clusterSlug, getClusters, getEnterprises, sectorName } from '../lib/hebei';

export default async function HomePage() {
  const [clusterData, enterpriseData] = await Promise.all([getClusters(), getEnterprises()]);
  const clusters = clusterData.items;
  const enterprises = enterpriseData.items;
  const searchItems = [
    ...clusters.map((c) => ({ type: 'cluster' as const, title: clusterName(c), subtitle: [c.city, c.county, sectorName(c.sector)].filter(Boolean).join(' · '), keywords: `${c.introZh || c.intro || ''} ${c.output || ''} ${c.honor || ''}`, href: `/cluster/${clusterSlug(c)}` })),
    ...enterprises.map((e) => ({ type: 'enterprise' as const, title: e.name, subtitle: [e.city, e.county, e.cluster].filter(Boolean).join(' · '), keywords: `${e.products?.join(' ') || ''} ${e.intro || ''}`, href: `/enterprise/${e.id}` }))
  ];

  return (
    <main>
      <section className="hero">
        <div className="container heroInner">
          <div className="eyebrow">河北制造 · 采购入口</div>
          <h1>找产业带，找源头工厂<br />从一张河北制造地图开始</h1>
          <p className="heroText">面向采购商、电商卖家和产业研究者，按产品、产地、产业带快速找到河北制造资源。</p>
          <SearchBox items={searchItems} />
          <div className="hotSearch"><span>热门：</span><Link href="/industries">白沟箱包</Link><Link href="/industries">安平丝网</Link><Link href="/industries">永年标准件</Link><Link href="/industries">清河羊绒</Link></div>
        </div>
      </section>

      <section className="stats"><div className="container statsGrid">
        <div><strong>{clusterData.count ?? clusters.length}</strong><span>精选产业带</span></div>
        <div><strong>{enterpriseData.count ?? enterprises.length}</strong><span>代表企业</span></div>
        <div><strong>11</strong><span>地级市覆盖</span></div>
        <div><strong>每日</strong><span>数据可更新</span></div>
      </div></section>

      <section className="section container">
        <div className="sectionHead"><div><span className="sectionKicker">INDUSTRIAL CLUSTERS</span><h2>热门产业带</h2><p>先从产业聚集地切入，再定位对应企业与产品。</p></div><Link className="textLink" href="/industries">查看全部 →</Link></div>
        <div className="cardGrid">
          {clusters.slice(0, 8).map((c) => <Link className="clusterCard" href={`/cluster/${clusterSlug(c)}`} key={c.id}>
            <div className="cardTop"><span className="pill">{sectorName(c.sector)}</span><span className="arrow">↗</span></div>
            <h3>{clusterName(c)}</h3><p>{[c.city, c.county].filter(Boolean).join(' · ') || '河北'}</p>
            <div className="cardMeta"><span>{c.output || '产业规模持续更新'}</span></div>
          </Link>)}
        </div>
      </section>

      <section className="section alt"><div className="container">
        <div className="sectionHead"><div><span className="sectionKicker">VERIFIED ENTERPRISES</span><h2>代表企业</h2><p>公开来源整理，详情页保留核验时间、来源与企业信息。</p></div><Link className="textLink" href="/enterprises">查看企业库 →</Link></div>
        <div className="enterpriseGrid">
          {enterprises.slice(0, 6).map((e) => <Link className="enterpriseCard" href={`/enterprise/${e.id}`} key={e.id}>
            <div className="companyBadge">{e.name.slice(0, 1)}</div><div><h3>{e.name}</h3><p>{[e.city, e.county, e.cluster].filter(Boolean).join(' · ')}</p><div className="tags">{e.products?.slice(0, 3).map((p) => <span key={p}>{p}</span>)}</div></div>
          </Link>)}
        </div>
      </div></section>

      <section className="section container"><div className="cta">
        <div><span className="sectionKicker">FACTORY ONBOARDING</span><h2>你是河北工厂？</h2><p>首阶段免费登记。后续可补充主营产品、工厂能力、联系方式、实拍图和资质信息。</p></div><Link className="primaryBtn" href="/join">申请入驻</Link>
      </div></section>
    </main>
  );
}
