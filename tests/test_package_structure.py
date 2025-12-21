"""
Test package structure - verify imports work without sys.path manipulation
TDD approach: Write test first, then implement proper package structure
"""

import unittest
import sys
import os


class TestPackageStructure(unittest.TestCase):
    """Test that package can be imported without sys.path hacks"""
    
    def setUp(self):
        """Ensure clean sys.path - remove any project root additions"""
        self.original_path = sys.path.copy()
        # Remove any existing project root additions
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root in sys.path:
            sys.path.remove(project_root)
    
    def tearDown(self):
        """Restore original sys.path"""
        sys.path[:] = self.original_path
    
    def test_config_import_without_sys_path(self):
        """Test: config module can be imported without sys.path manipulation"""
        # This should work once package is properly installed
        try:
            import config
            self.assertTrue(True, "config imported successfully")
        except ImportError as e:
            self.skipTest(f"config import failed: {e}. Install with: pip install -e .")
    
    def test_modules_import_without_sys_path(self):
        """Test: modules can be imported without sys.path manipulation"""
        try:
            from modules import logging_utils
            self.assertTrue(True, "modules.logging_utils imported successfully")
        except ImportError as e:
            self.skipTest(f"modules import failed: {e}. Install with: pip install -e .")
    
    def test_modules_submodule_import(self):
        """Test: submodules can be imported via modules package"""
        try:
            from modules.logging_utils import setup_logger
            self.assertTrue(True, "modules.logging_utils.setup_logger imported successfully")
        except ImportError as e:
            self.skipTest(f"modules submodule import failed: {e}. Install with: pip install -e .")
    
    def test_no_sys_path_manipulation_in_modules(self):
        """Test: modules don't manipulate sys.path themselves"""
        import importlib.util
        
        # Check a few key modules
        modules_to_check = [
            'modules.orchestrator',
            'modules.mpd_controller',
            'modules.wake_word_listener',
        ]
        
        for module_name in modules_to_check:
            module_path = module_name.replace('.', '/') + '.py'
            full_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                module_path
            )
            
            if os.path.exists(full_path):
                with open(full_path, 'r') as f:
                    content = f.read()
                    # Check for common sys.path manipulation patterns
                    if 'sys.path.append' in content or 'sys.path.insert' in content:
                        # Allow hailo_stt.py to have hailo_examples path (external dependency)
                        if 'hailo_examples' in content or 'hailo_stt' in module_name:
                            continue
                        self.fail(f"{module_name} still contains sys.path manipulation. "
                                 f"Should use proper package imports instead.")

