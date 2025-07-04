"""
KGD CAPTCHA Solver Module

This module provides CAPTCHA solving functionality using 2captcha service.
It can be integrated with the main KGD tax parser.

Requirements:
    pip install 2captcha-python requests

Usage:
    from kgd_captcha_solver import CaptchaSolver
    
    solver = CaptchaSolver("your_2captcha_api_key")
    result = await solver.solve_captcha_from_page(page)
"""

import asyncio
import base64
import time
from typing import Optional

import requests
from playwright.async_api import Page

class CaptchaSolver:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "http://2captcha.com"
        
    async def solve_captcha_from_page(self, page: Page) -> Optional[str]:
        """
        Solve CAPTCHA from a Playwright page
        
        Args:
            page: Playwright page object
            
        Returns:
            CAPTCHA solution text or None if failed
        """
        try:
            # Find CAPTCHA image
            captcha_img = await page.query_selector('img[src*="captcha"]')
            if not captcha_img:
                return None
                
            # Get CAPTCHA image source
            captcha_src = await captcha_img.get_attribute('src')
            if not captcha_src:
                return None
                
            # Download CAPTCHA image
            if captcha_src.startswith('data:'):
                # Handle data URL
                image_data = captcha_src.split(',')[1]
                image_bytes = base64.b64decode(image_data)
            else:
                # Handle regular URL
                if captcha_src.startswith('/'):
                    captcha_url = f"https://kgd.gov.kz{captcha_src}"
                else:
                    captcha_url = captcha_src
                    
                response = requests.get(captcha_url)
                if response.status_code != 200:
                    return None
                image_bytes = response.content
            
            # Solve CAPTCHA using 2captcha
            solution = await self.solve_captcha_image(image_bytes)
            return solution
            
        except Exception as e:
            print(f"❌ Error solving CAPTCHA: {e}")
            return None
    
    async def solve_captcha_image(self, image_bytes: bytes) -> Optional[str]:
        """
        Solve CAPTCHA using 2captcha service
        
        Args:
            image_bytes: CAPTCHA image as bytes
            
        Returns:
            CAPTCHA solution text or None if failed
        """
        try:
            # Submit CAPTCHA to 2captcha
            captcha_id = await self.submit_captcha(image_bytes)
            if not captcha_id:
                return None
                
            # Wait for solution
            solution = await self.get_captcha_result(captcha_id)
            return solution
            
        except Exception as e:
            print(f"❌ Error solving CAPTCHA image: {e}")
            return None
    
    async def submit_captcha(self, image_bytes: bytes) -> Optional[str]:
        """Submit CAPTCHA image to 2captcha service"""
        try:
            # Encode image to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Prepare request data
            data = {
                'method': 'base64',
                'key': self.api_key,
                'body': image_base64,
                'phrase': 0,  # 0 - one word, 1 - two or more words
                'case': 0,    # 0 - not case sensitive, 1 - case sensitive
                'numeric': 0, # 0 - not numeric, 1 - numeric only, 2 - letters only
                'min_len': 0, # minimum length
                'max_len': 0, # maximum length
                'lang': 'en'  # language
            }
            
            # Submit request
            response = requests.post(f"{self.base_url}/in.php", data=data)
            
            if response.status_code != 200:
                print(f"❌ Failed to submit CAPTCHA: HTTP {response.status_code}")
                return None
                
            result = response.text
            if result.startswith('OK|'):
                captcha_id = result.split('|')[1]
                print(f"📤 CAPTCHA submitted successfully. ID: {captcha_id}")
                return captcha_id
            else:
                print(f"❌ Failed to submit CAPTCHA: {result}")
                return None
                
        except Exception as e:
            print(f"❌ Error submitting CAPTCHA: {e}")
            return None
    
    async def get_captcha_result(self, captcha_id: str, max_wait: int = 120) -> Optional[str]:
        """Get CAPTCHA solution from 2captcha service"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                # Check if solution is ready
                response = requests.get(
                    f"{self.base_url}/res.php",
                    params={
                        'key': self.api_key,
                        'action': 'get',
                        'id': captcha_id
                    }
                )
                
                if response.status_code != 200:
                    print(f"❌ Failed to get CAPTCHA result: HTTP {response.status_code}")
                    return None
                
                result = response.text
                
                if result == 'CAPCHA_NOT_READY':
                    print("⏳ CAPTCHA solution not ready yet, waiting...")
                    await asyncio.sleep(5)
                    continue
                elif result.startswith('OK|'):
                    solution = result.split('|')[1]
                    print(f"✅ CAPTCHA solved: {solution}")
                    return solution
                else:
                    print(f"❌ Failed to get CAPTCHA result: {result}")
                    return None
            
            print("⏰ Timeout waiting for CAPTCHA solution")
            return None
            
        except Exception as e:
            print(f"❌ Error getting CAPTCHA result: {e}")
            return None
    
    def get_balance(self) -> Optional[float]:
        """Get account balance from 2captcha"""
        try:
            response = requests.get(
                f"{self.base_url}/res.php",
                params={
                    'key': self.api_key,
                    'action': 'getbalance'
                }
            )
            
            if response.status_code == 200:
                balance = float(response.text)
                return balance
            else:
                return None
                
        except Exception as e:
            print(f"❌ Error getting balance: {e}")
            return None


# Alternative CAPTCHA solving methods for manual handling
class ManualCaptchaSolver:
    """Manual CAPTCHA solver for development and testing"""
    
    async def solve_captcha_from_page(self, page: Page) -> Optional[str]:
        """
        Manual CAPTCHA solving - requires user input
        
        Args:
            page: Playwright page object
            
        Returns:
            CAPTCHA solution text or None if failed
        """
        try:
            # Check if CAPTCHA is present
            captcha_img = await page.query_selector('img[src*="captcha"]')
            if not captcha_img:
                return None
                
            print("🔍 CAPTCHA detected!")
            print("📸 Please look at the browser window and solve the CAPTCHA manually.")
            print("⌨️ Enter the CAPTCHA text below:")
            
            # Wait for user input
            solution = input("CAPTCHA solution: ").strip()
            
            if solution:
                print(f"✅ CAPTCHA solution entered: {solution}")
                return solution
            else:
                print("❌ No CAPTCHA solution provided")
                return None
                
        except Exception as e:
            print(f"❌ Error with manual CAPTCHA solving: {e}")
            return None


# OCR-based CAPTCHA solver (experimental)
class OCRCaptchaSolver:
    """OCR-based CAPTCHA solver using Tesseract (experimental)"""
    
    def __init__(self):
        try:
            import pytesseract
            from PIL import Image
            self.pytesseract = pytesseract
            self.Image = Image
            self.available = True
        except ImportError:
            print("⚠️ OCR CAPTCHA solver requires: pip install pytesseract pillow")
            print("⚠️ Also install Tesseract OCR engine: https://github.com/tesseract-ocr/tesseract")
            self.available = False
    
    async def solve_captcha_from_page(self, page: Page) -> Optional[str]:
        """
        OCR-based CAPTCHA solving (experimental)
        
        Args:
            page: Playwright page object
            
        Returns:
            CAPTCHA solution text or None if failed
        """
        if not self.available:
            return None
            
        try:
            # Find CAPTCHA image
            captcha_img = await page.query_selector('img[src*="captcha"]')
            if not captcha_img:
                return None
                
            # Take screenshot of CAPTCHA
            captcha_bytes = await captcha_img.screenshot()
            
            # Convert to PIL Image
            image = self.Image.open(io.BytesIO(captcha_bytes))
            
            # Preprocess image (optional)
            image = image.convert('L')  # Convert to grayscale
            
            # Use OCR to extract text
            solution = self.pytesseract.image_to_string(
                image, 
                config='--psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            ).strip()
            
            if solution:
                print(f"🔍 OCR CAPTCHA solution: {solution}")
                return solution
            else:
                print("❌ OCR failed to solve CAPTCHA")
                return None
                
        except Exception as e:
            print(f"❌ Error with OCR CAPTCHA solving: {e}")
            return None


# Factory function to create appropriate solver
def create_captcha_solver(api_key: Optional[str] = None, method: str = "auto") -> object:
    """
    Create appropriate CAPTCHA solver based on available resources
    
    Args:
        api_key: 2captcha API key (optional)
        method: Solver method - 'auto', '2captcha', 'manual', 'ocr'
        
    Returns:
        CAPTCHA solver instance
    """
    if method == "2captcha" and api_key:
        return CaptchaSolver(api_key)
    elif method == "manual":
        return ManualCaptchaSolver()
    elif method == "ocr":
        return OCRCaptchaSolver()
    elif method == "auto":
        # Auto-select based on available resources
        if api_key:
            return CaptchaSolver(api_key)
        else:
            return ManualCaptchaSolver()
    else:
        return ManualCaptchaSolver() 