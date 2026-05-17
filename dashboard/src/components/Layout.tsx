import { Link, Outlet } from 'react-router-dom';
import './Layout.css';

export default function Layout() {
  return (
    <div className="layout">
      <nav className="sidebar">
        <h1>量化系统</h1>
        <ul>
          <li>
            <Link to="/">策略管理</Link>
          </li>
          <li>
            <Link to="/backtest">回测分析</Link>
          </li>
          <li>
            <Link to="/performance">性能监控</Link>
          </li>
          <li>
            <Link to="/signals">信号查询</Link>
          </li>
          <li>
            <Link to="/charts">图表可视化</Link>
          </li>
        </ul>
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
