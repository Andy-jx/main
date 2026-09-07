import Link from 'next/link';

export default function Header() {
  return (
    <header className="siteHeader">
      <div className="container navWrap">
        <Link className="brand" href="/">
          <span className="brandMark">源</span>
          <span><b>源厂河北</b><small>河北产业带与源头工厂</small></span>
        </Link>
        <nav className="nav">
          <Link href="/industries">产业带</Link>
          <Link href="/enterprises">找工厂</Link>
          <Link href="/join">工厂入驻</Link>
        </nav>
      </div>
    </header>
  );
}
