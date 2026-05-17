import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import StrategiesPage from './pages/StrategiesPage';
import BacktestPage from './pages/BacktestPage';
import PerformancePage from './pages/PerformancePage';
import SignalsPage from './pages/SignalsPage';
import ChartsPage from './pages/ChartsPage';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<StrategiesPage />} />
          <Route path="backtest" element={<BacktestPage />} />
          <Route path="performance" element={<PerformancePage />} />
          <Route path="signals" element={<SignalsPage />} />
          <Route path="charts" element={<ChartsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
