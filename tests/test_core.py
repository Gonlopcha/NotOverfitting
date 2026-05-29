import unittest
from unittest.mock import patch, MagicMock
from src.core.config_manager import ConfigManager
from src.core.event_bus import EventBus
from src.core.registry import Registry
from src.core.mt5_connector import MT5Connector

class TestCoreLayer(unittest.TestCase):
    
    def test_config_manager_singleton_and_setters(self):
        config1 = ConfigManager()
        config2 = ConfigManager()
        self.assertIs(config1, config2, "ConfigManager must be a Singleton")
        
        # Test setter and getter
        config1.set('test.key', 'value')
        self.assertEqual(config1.get('test.key'), 'value')
        self.assertEqual(config1.get_str('test.key'), 'value')
        
    def test_event_bus_pub_sub(self):
        bus = EventBus()
        received = []
        
        def dummy_callback(**kwargs):
            received.append(kwargs)
            
        bus.subscribe('test.event', dummy_callback)
        bus.emit('test.event', source='test', data=123)
        
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]['data'], 123)
        
    def test_registry_registration(self):
        registry = Registry('features')
        
        class DummyFeature:
            pass
            
        registry.register('test_feature', DummyFeature)
        self.assertTrue(registry.exists('test_feature'))
        
    @patch('src.core.mt5_connector.mt5')
    def test_mt5_connector_singleton(self, mock_mt5):
        # Ensure mt5 is not really called
        mock_mt5.initialize.return_value = True
        
        conn1 = MT5Connector()
        conn2 = MT5Connector()
        self.assertIs(conn1, conn2, "MT5Connector must be a Singleton")

if __name__ == '__main__':
    unittest.main()
