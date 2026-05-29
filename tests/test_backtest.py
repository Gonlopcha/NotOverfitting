import unittest
import pandas as pd
import numpy as np
from src.backtest.portfolio import Portfolio
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import calculate_all_metrics

class TestBacktestLayer(unittest.TestCase):
    
    def setUp(self):
        # Datos de prueba
        self.dates = pd.date_range('2023-01-01', periods=10, freq='H')
        self.df = pd.DataFrame({
            'time': self.dates,
            'close': [100, 105, 110, 105, 100, 95, 90, 95, 100, 105]
        })
        self.df.set_index('time', inplace=True)
        
        # Señales de prueba: Comprar en index 0, mantener, luego Vender todo en index 3
        # Luego Short en index 4, mantener, cubrir en index 7
        signals_array = [1, 0, 0, -1, -1, 0, 0, 1, 0, 0]
        self.signals = pd.Series(signals_array, index=self.dates)
        
    def test_portfolio_and_engine(self):
        portfolio = Portfolio(initial_capital=10000.0)
        # Sin slippage y comisión 0% para facilitar cálculo mental
        engine = BacktestEngine(portfolio, commission_pct=0.0, slippage_pips=0.0)
        
        engine.run(self.df, self.signals, 'AAPL')
        
        # Verificamos trades
        summary = portfolio.get_summary()
        self.assertEqual(len(summary), 3)  # Tres trades: Long, Short, Long
        
        # Trade 1: Long en 100, Cierra en 105 -> PnL: +5
        self.assertEqual(summary.iloc[0]['entry_price'], 100)
        self.assertEqual(summary.iloc[0]['exit_price'], 105)
        self.assertEqual(summary.iloc[0]['pnl'], 5)
        self.assertEqual(summary.iloc[0]['direction'], 1)
        
        # Trade 2: Short en 105, Cierra en 95 -> PnL: +10
        self.assertEqual(summary.iloc[1]['entry_price'], 105)
        self.assertEqual(summary.iloc[1]['exit_price'], 95)
        self.assertEqual(summary.iloc[1]['pnl'], 10)
        self.assertEqual(summary.iloc[1]['direction'], -1)
        
        # Trade 3: Long en 95, Cierra en 100 -> PnL: +5
        self.assertEqual(summary.iloc[2]['entry_price'], 95)
        self.assertEqual(summary.iloc[2]['exit_price'], 100)
        self.assertEqual(summary.iloc[2]['pnl'], 5)
        self.assertEqual(summary.iloc[2]['direction'], 1)
        
        # Capital final esperado
        # 10000 + 5 + 10 + 5 = 10020
        final_equity = portfolio.equity_curve[-1]
        self.assertEqual(final_equity, 10020)
        
    def test_metrics_calculation(self):
        portfolio = Portfolio(initial_capital=10000.0)
        engine = BacktestEngine(portfolio, commission_pct=0.0, slippage_pips=0.0)
        engine.run(self.df, self.signals, 'AAPL')
        
        metrics = calculate_all_metrics(pd.Series(portfolio.equity_curve), portfolio.get_summary())
        
        self.assertEqual(metrics['Total Trades'], 3)
        self.assertEqual(metrics['Win Rate (%)'], 100.0) # Ambos trades ganaron
        self.assertTrue(metrics['Profit Factor'] == float('inf')) # Cero perdidas
        self.assertEqual(metrics['Max Drawdown (%)'], 0.0) # Nunca bajó del capital inicial
        
if __name__ == '__main__':
    unittest.main()
