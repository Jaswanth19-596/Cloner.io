from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from typing import Dict, Any, List, Optional
from datetime import datetime
import base64
import asyncio
import json
import re
import os
import traceback
from openai import AsyncOpenAI
from playwright.async_api import async_playwright
import logging
from dotenv import load_dotenv
import os

load_dotenv()  

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Website Cloner", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Supported models
SUPPORTED_MODELS = ["gpt-4o", "gpt-4o-mini"]

class ScrapeRequest(BaseModel):
    url: str
    capture_screenshot: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    wait_time: int = 8000

class CloneRequest(BaseModel):
    scraped_data: Dict[str, Any]
    model: str = "gpt-4o"
    include_responsive: bool = True
    include_interactions: bool = True
    
    @validator('model')
    def validate_model(cls, v):
        if v not in SUPPORTED_MODELS:
            return "gpt-4o"
        return v

class WebScraper:
    async def scrape_website(self, request: ScrapeRequest) -> Dict[str, Any]:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": request.viewport_width, "height": request.viewport_height}
                )
                page = await context.new_page()
                
                logger.info(f"Loading URL: {request.url}")
                await page.goto(request.url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(request.wait_time)
                
                # Get basic page info
                title = await page.title()
                final_url = page.url
                
                # Extract page structure
                structure_data = await self._extract_structure(page)
                
                # Capture screenshot
                screenshot_b64 = None
                if request.capture_screenshot:
                    try:
                        screenshot_buffer = await page.screenshot(full_page=True, type='png')
                        screenshot_b64 = base64.b64encode(screenshot_buffer).decode('utf-8')
                    except Exception as e:
                        logger.warning(f"Screenshot failed: {e}")
                
                # Get images
                images = await self._extract_images(page)
                
                await browser.close()
                
                return {
                    "url": final_url,
                    "title": title,
                    "screenshot": screenshot_b64,
                    "structure": structure_data,
                    "assets": {"images": images},
                    "stats": {
                        "images_found": len(images),
                        "has_screenshot": screenshot_b64 is not None,
                        "css_rules": 0,  # Simplified
                        "dom_elements": structure_data.get("element_count", 0)
                    },
                    "timestamp": datetime.now().isoformat(),
                    "status": "success"
                }
                
        except Exception as e:
            logger.error(f"Scraping failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")
    
    async def _extract_structure(self, page):
        """Extract page structure information"""
        try:
            return await page.evaluate("""
                () => {
                    return {
                        h1: document.querySelector('h1')?.textContent?.trim() || '',
                        h2: document.querySelector('h2')?.textContent?.trim() || '',
                        navigation: !!document.querySelector('nav, .nav, .navbar'),
                        footer: !!document.querySelector('footer, .footer'),
                        sidebar: !!document.querySelector('aside, .sidebar'),
                        element_count: document.querySelectorAll('*').length
                    };
                }
            """)
        except Exception as e:
            logger.warning(f"Structure extraction failed: {e}")
            return {"h1": "", "h2": "", "navigation": False, "footer": False, "sidebar": False, "element_count": 0}

    async def _extract_images(self, page):
        """Extract image information"""
        try:
            return await page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('img')).map(img => ({
                        src: img.src,
                        alt: img.alt || '',
                        width: img.naturalWidth || img.width || 0,
                        height: img.naturalHeight || img.height || 0
                    })).slice(0, 20);
                }
            """)
        except Exception as e:
            logger.warning(f"Image extraction failed: {e}")
            return []

class LLMCloner:
    def __init__(self):
        self.openai_client = openai_client
    
    async def clone_website(self, scraped_data: Dict[str, Any], model: str = "gpt-4o", 
                          include_responsive: bool = True, include_interactions: bool = True) -> str:
        """Clone website using GPT-4 Vision"""
        try:
            if not self.openai_client:
                raise HTTPException(status_code=500, detail="OpenAI client not initialized")
            
            # Build context
            context = self._build_context(scraped_data)
            
            # Create system prompt
            system_prompt = self._create_system_prompt(include_responsive, include_interactions)
            
            # Prepare message content
            message_content = [
                {
                    "type": "text",
                    "text": f"{system_prompt}\n\nWebsite to recreate:\n{context}\n\nCreate a complete HTML file:"
                }
            ]
            
            # Add screenshot if available
            if scraped_data.get("screenshot"):
                message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{scraped_data['screenshot']}",
                        "detail": "high"
                    }
                })
            
            # Call OpenAI API
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": message_content
                }],
                max_tokens=4000,
                temperature=0.1
            )
            
            html_content = response.choices[0].message.content
            html_content = self._clean_html(html_content)
            
            return html_content
            
        except Exception as e:
            logger.error(f"LLM cloning failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"AI cloning failed: {str(e)}")
    
    def _create_system_prompt(self, include_responsive: bool, include_interactions: bool) -> str:
        """Create system prompt for AI"""
        prompt = """You are a helpful AI web developer assistant. Your task is to recreate a simple, static HTML version of a public web page for educational and non-commercial purposes.

    The goal is to help a student learn about HTML structure, CSS layout, and responsive design by analyzing existing pages.

    REQUIREMENTS:
    1. Provide a complete HTML5 document with <!DOCTYPE html>, <head>, and <body>
    2. Embed all CSS styles within <style> tags in the <head> (no external CSS)
    3. Match the layout and visual structure shown in the screenshot
    4. Use clean, semantic HTML5 tags (e.g., <header>, <nav>, <main>, <footer>)
    5. Ensure the layout is responsive for mobile and desktop using CSS media queries"""

        if include_interactions:
            prompt += "\n6. Add simple hover effects and smooth transitions using CSS"

        prompt += """

    Do not include any scripts, tracking codes, or external resources.
    Avoid using copyrighted text or images. Use placeholder text or simple generic content.

    OUTPUT: Provide ONLY the complete HTML code (no explanations or markdown formatting)."""

        return prompt

    def _build_context(self, scraped_data: Dict[str, Any]) -> str:
        """Build context for AI model"""
        context_parts = [
            f"URL: {scraped_data.get('url', 'N/A')}",
            f"Title: {scraped_data.get('title', 'N/A')}"
        ]
        
        structure = scraped_data.get('structure', {})
        if structure.get('h1'):
            context_parts.append(f"Main heading: {structure['h1']}")
        
        features = []
        if structure.get('navigation'): features.append("Navigation")
        if structure.get('footer'): features.append("Footer")
        if structure.get('sidebar'): features.append("Sidebar")
        
        if features:
            context_parts.append(f"Layout features: {', '.join(features)}")
        
        images = scraped_data.get('assets', {}).get('images', [])
        if images:
            context_parts.append(f"Contains {len(images)} images")
        
        return "\n".join(context_parts)
    
    def _clean_html(self, html_content: str) -> str:
        """Clean HTML response"""
        # Remove markdown formatting
        if "```html" in html_content:
            match = re.search(r'```html(.*?)```', html_content, re.DOTALL)
            if match:
                html_content = match.group(1).strip()
        elif "```" in html_content:
            match = re.search(r'```(.*?)```', html_content, re.DOTALL)
            if match:
                html_content = match.group(1).strip()
        
        # Add DOCTYPE if missing
        if not html_content.strip().startswith('<!DOCTYPE'):
            html_content = '<!DOCTYPE html>\n' + html_content
        
        return html_content.strip()

# Initialize services
scraper = WebScraper()
cloner = LLMCloner()

@app.post("/scrape")
async def scrape_website(request: ScrapeRequest):
    """Scrape website and extract data"""
    try:
        logger.info(f"Scraping: {request.url}")
        result = await scraper.scrape_website(request)
        return result
    except Exception as e:
        logger.error(f"Scrape error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clone")
async def clone_website(request: CloneRequest):
    """Generate HTML using AI"""
    try:
        logger.info(f"Cloning with model: {request.model}")
        
        html_content = await cloner.clone_website(
            request.scraped_data, 
            request.model,
            request.include_responsive,
            request.include_interactions
        )
        
        return {
            "status": "success",
            "model_used": request.model,
            "html_content": html_content,
            "processing_info": {
                "context_length": len(str(request.scraped_data)),
                "has_screenshot": bool(request.scraped_data.get("screenshot")),
                "images_processed": len(request.scraped_data.get("assets", {}).get("images", []))
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Clone error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "supported_models": SUPPORTED_MODELS
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Website Cloner API",
        "version": "1.0.0",
        "endpoints": {
            "scrape": "POST /scrape",
            "clone": "POST /clone", 
            "health": "GET /health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


