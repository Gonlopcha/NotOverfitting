import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

from src.data.schemas import validate_ohlcv_dataframe, OHLCVRecord
from src.data.cache_manager import CacheManager
from src.data.data_manager import DataManager

class TestDataLayer(unittest.TestCase):

    def test_schemas_validation(self):
        # Create a valid DataFrame
        df = pd.DataFrame({
            'time': [datetime(2023, 1, 1), datetime(2023, 1, 2)],
            'open': [1.1000, 1.1050],
            'high': [1.1050, 1.1100],
            'low': [1.0950, 1.1000],
            'close': [1.1020, 1.1080],
            'volume': [1000, 1500]
        })
        
        result = validate_ohlcv_dataframe(df)
        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        
    def test_cache_manager(self):
        cache = CacheManager()
        df = pd.DataFrame({'time': [datetime(2023, 1, 1)]})
        from_date = datetime(2023, 1, 1)
        to_date = datetime(2023, 1, 2)
        
        cache.update('EURUSD', 'H1', df, from_date, to_date)
        
        # Checking if data is available
        cached_df = cache.get_data('EURUSD', 'H1', from_date, to_date)
        self.assertIsNotNone(cached_df)
        self.assertEqual(len(cached_df), 1)

    @patch('src.data.data_manager.MT5Connector')
    @patch('src.data.data_manager.DataStore')
    @patch('src.data.data_manager.CacheManager')
    def test_data_manager_orchestration(self, mock_cache, mock_store, mock_mt5):
        # Setup mocks
        mt5_instance = mock_mt5.return_value
        cache_instance = mock_cache.return_value
        store_instance = mock_store.return_value
        
        # Simulate cache miss
        cache_instance.get_data.return_value = None
        cache_instance.get_missing_ranges.return_value = [(datetime(2023,1,1), datetime(2023,1,2))]
        
        # Simulate MT5 download
        df_mock = pd.DataFrame({
            'time': [datetime(2023, 1, 1)],
            'open': [1.1], 'high': [1.2], 'low': [1.0], 'close': [1.15], 'volume': [100]
        })
        mt5_instance.download_ohlc.return_value = df_mock
        
        dm = DataManager(mt5_connector=mt5_instance, cache_manager=cache_instance, data_store=store_instance)
        
        # Call download
        result_df = dm.download('EURUSD', 'H1', datetime(2023, 1, 1), datetime(2023, 1, 2))
        
        # Check that it did at least hit the store and mt5
        mt5_instance.download_ohlc.assert_called()
        store_instance.store.assert_called()
        cache_instance.update.assert_called()

if __name__ == '__main__':
    unittest.main()
