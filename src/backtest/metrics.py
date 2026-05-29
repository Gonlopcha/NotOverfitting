"""
Módulo de cálculo de métricas de backtesting.
Basado en la Sección 7.2 del Plan de Estudios.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 252 * 24) -> float:
    """
    Calcula el ratio de Sharpe anualizado.
    Por defecto usa 252*24 periodos (aprox H1).
    """
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    excess_returns = returns - (risk_free_rate / periods_per_year)
    return np.sqrt(periods_per_year) * (excess_returns.mean() / excess_returns.std())

def calculate_maximum_drawdown(equity_curve: pd.Series) -> float:
    """Calcula el Maximum Drawdown histórico."""
    if len(equity_curve) == 0:
        return 0.0
    peak = equity_curve.expanding(min_periods=1).max()
    drawdown = (peak - equity_curve) / peak
    return drawdown.max()

def calculate_profit_factor(trades: pd.DataFrame) -> float:
    """Calcula el Profit Factor (Gross Profit / Gross Loss)."""
    if trades.empty:
        return 0.0
    gross_profit = trades[trades['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(trades[trades['pnl'] < 0]['pnl'].sum())
    
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0
    return gross_profit / gross_loss

def calculate_win_rate(trades: pd.DataFrame) -> float:
    """Calcula el porcentaje de operaciones ganadoras."""
    if trades.empty:
        return 0.0
    winning_trades = len(trades[trades['pnl'] > 0])
    return winning_trades / len(trades)

def calculate_deflated_sharpe_ratio(
    observed_sharpe: float, 
    num_trials: int, 
    variance_of_trials: float = 1.0, 
) -> float:
    """
    Calcula el Deflated Sharpe Ratio estimado (simplificado) ajustando
    por el número de ensayos/backtests ejecutados (López de Prado).
    Penaliza fuertemente probar cientos de parámetros (num_trials alto).
    """
    if num_trials <= 1:
        return observed_sharpe
        
    # Expected maximum Sharpe from multiple trials
    expected_max_sr = np.sqrt(2 * np.log(num_trials))
    
    # Simplified DSR approximation
    adjusted_sharpe = observed_sharpe - (expected_max_sr * np.sqrt(variance_of_trials))
    return max(0.0, adjusted_sharpe)

def calculate_all_metrics(equity_curve: pd.Series, trades: pd.DataFrame, num_trials: int = 1) -> Dict[str, Any]:
    """Calcula el reporte completo de métricas."""
    returns = equity_curve.pct_change().dropna()
    
    sharpe = calculate_sharpe_ratio(returns)
    
    return {
        'Total Trades': len(trades),
        'Win Rate (%)': calculate_win_rate(trades) * 100,
        'Profit Factor': calculate_profit_factor(trades),
        'Max Drawdown (%)': calculate_maximum_drawdown(equity_curve) * 100,
        'Sharpe Ratio': sharpe,
        'Deflated Sharpe Ratio': calculate_deflated_sharpe_ratio(sharpe, num_trials)
    }
