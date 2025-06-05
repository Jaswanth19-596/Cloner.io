from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
from typing import Dict, Any, List, Optional
from datetime import datetime
import base64
import aiohttp
import asyncio
import json
import re
import os
import traceback
from openai import AsyncOpenAI
from playwright.async_api import async_playwright
import logging
from PIL import Image
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Enhanced Website Cloning API", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client with environment variable for security
openai_client = AsyncOpenAI(api_key="")

# Supported OpenAI models
SUPPORTED_MODELS = ["gpt-4o", "gpt-4o-mini"]

class ScrapeRequest(BaseModel):
    url: str
    capture_screenshot: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    wait_time: int = 5000
    capture_sections: bool = False
    full_page_screenshot: bool = True

class CloneRequest(BaseModel):
    scraped_data: Dict[str, Any]
    model: str = "gpt-4o"
    include_responsive: bool = True
    include_interactions: bool = True
    style_approach: str = "embedded"  # "embedded", "inline", or "mixed"
    
    @validator('model')
    def validate_model(cls, v):
        if v not in SUPPORTED_MODELS:
            return "gpt-4o"
        return v

class WebScraper:
    async def scrape_website(self, request: ScrapeRequest) -> Dict[str, Any]:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
                )
                
                context = await browser.new_context(
                    viewport={"width": request.viewport_width, "height": request.viewport_height},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                page = await context.new_page()
                
                logger.info(f"Loading URL: {request.url}")
                
                # Navigate to page with better error handling
                try:
                    await page.goto(request.url, wait_until='networkidle', timeout=30000)
                    await page.wait_for_timeout(request.wait_time)
                except Exception as e:
                    logger.warning(f"Navigation issues, trying with domcontentloaded: {e}")
                    await page.goto(request.url, wait_until='domcontentloaded', timeout=20000)
                    await page.wait_for_timeout(request.wait_time)
                
                # Get page title and basic info
                title = await page.title()
                final_url = page.url
                
                # Enhanced content extraction
                enhanced_data = await self._extract_enhanced_data(page)
                
                # Capture screenshot with better error handling
                screenshot_b64 = None
                if request.capture_screenshot:
                    try:
                        screenshot_options = {
                            'full_page': request.full_page_screenshot,
                            'type': 'png',
                            'quality': 90 if not request.full_page_screenshot else None
                        }
                        screenshot_buffer = await page.screenshot(**screenshot_options)
                        screenshot_b64 = base64.b64encode(screenshot_buffer).decode('utf-8')
                        logger.info(f"Screenshot captured: {len(screenshot_buffer)} bytes")
                    except Exception as e:
                        logger.warning(f"Screenshot capture failed: {e}")
                
                # Extract CSS styles
                css_data = await self._extract_css_styles(page)
                
                # Get page content (limited for performance)
                content = await page.content()
                
                await browser.close()
                
                return {
                    "url": final_url,
                    "original_url": request.url,
                    "title": title,
                    "screenshot": screenshot_b64,
                    "content": content[:15000],  # Increased limit
                    "enhanced_data": enhanced_data,
                    "css_data": css_data,
                    "viewport": {
                        "width": request.viewport_width,
                        "height": request.viewport_height
                    },
                    "stats": {
                        "content_length": len(content),
                        "has_screenshot": screenshot_b64 is not None,
                        "css_rules_found": css_data.get("rules_count", 0),
                        "images_found": len(enhanced_data.get("images", [])),
                        "dom_elements": enhanced_data.get("element_count", 0)
                    },
                    "timestamp": datetime.now().isoformat(),
                    "status": "success"
                }
                
        except Exception as e:
            logger.error(f"Scraping failed: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")
    
    async def _extract_enhanced_data(self, page):
        """Extract comprehensive page information"""
        try:
            return await page.evaluate("""
                () => {
                    // Helper function to get element styles
                    const getElementStyles = (element) => {
                        const computed = window.getComputedStyle(element);
                        return {
                            display: computed.display,
                            position: computed.position,
                            width: computed.width,
                            height: computed.height,
                            backgroundColor: computed.backgroundColor,
                            color: computed.color,
                            fontSize: computed.fontSize,
                            fontFamily: computed.fontFamily,
                            margin: computed.margin,
                            padding: computed.padding,
                            border: computed.border
                        };
                    };

                    // Extract text content with hierarchy
                    const extractTextContent = () => {
                        const textElements = [];
                        const walker = document.createTreeWalker(
                            document.body,
                            NodeFilter.SHOW_TEXT,
                            null,
                            false
                        );
                        
                        let node;
                        while (node = walker.nextNode()) {
                            const text = node.textContent.trim();
                            if (text.length > 0) {
                                textElements.push({
                                    text: text.substring(0, 200),
                                    parent: node.parentElement.tagName.toLowerCase()
                                });
                            }
                        }
                        return textElements.slice(0, 50);
                    };

                    // Extract layout structure
                    const extractLayoutInfo = () => {
                        const layoutElements = [];
                        const selectors = ['header', 'nav', 'main', 'aside', 'footer', '.header', '.nav', '.navbar', '.sidebar', '.footer', '.main', '.content'];
                        
                        selectors.forEach(selector => {
                            const elements = document.querySelectorAll(selector);
                            elements.forEach(el => {
                                layoutElements.push({
                                    selector: selector,
                                    tagName: el.tagName.toLowerCase(),
                                    className: el.className,
                                    id: el.id,
                                    styles: getElementStyles(el)
                                });
                            });
                        });
                        
                        return layoutElements;
                    };

                    return {
                        title: document.title,
                        meta: {
                            description: document.querySelector('meta[name="description"]')?.content || '',
                            keywords: document.querySelector('meta[name="keywords"]')?.content || '',
                            viewport: document.querySelector('meta[name="viewport"]')?.content || ''
                        },
                        headings: {
                            h1: Array.from(document.querySelectorAll('h1')).map(h => ({
                                text: h.textContent?.trim(),
                                styles: getElementStyles(h)
                            })).filter(h => h.text).slice(0, 10),
                            h2: Array.from(document.querySelectorAll('h2')).map(h => ({
                                text: h.textContent?.trim(),
                                styles: getElementStyles(h)
                            })).filter(h => h.text).slice(0, 10),
                            h3: Array.from(document.querySelectorAll('h3')).map(h => ({
                                text: h.textContent?.trim(),
                                styles: getElementStyles(h)
                            })).filter(h => h.text).slice(0, 10)
                        },
                        links: Array.from(document.querySelectorAll('a')).map(a => ({
                            text: a.textContent?.trim()?.substring(0, 100),
                            href: a.href,
                            target: a.target,
                            styles: getElementStyles(a)
                        })).filter(l => l.text && l.href).slice(0, 20),
                        images: Array.from(document.querySelectorAll('img')).map(img => ({
                            src: img.src,
                            alt: img.alt,
                            width: img.naturalWidth || img.width,
                            height: img.naturalHeight || img.height,
                            styles: getElementStyles(img)
                        })).slice(0, 20),
                        structure: {
                            hasNav: !!document.querySelector('nav, .nav, .navbar'),
                            hasHeader: !!document.querySelector('header, .header'),
                            hasFooter: !!document.querySelector('footer, .footer'),
                            hasSidebar: !!document.querySelector('aside, .sidebar'),
                            hasMain: !!document.querySelector('main, .main, .content'),
                            layout: extractLayoutInfo()
                        },
                        colors: {
                            background: window.getComputedStyle(document.body).backgroundColor,
                            text: window.getComputedStyle(document.body).color,
                            primary: document.querySelector('[class*="primary"]') ? 
                                window.getComputedStyle(document.querySelector('[class*="primary"]')).color : null
                        },
                        typography: {
                            bodyFont: window.getComputedStyle(document.body).fontFamily,
                            bodySize: window.getComputedStyle(document.body).fontSize,
                            headingFont: document.querySelector('h1') ? 
                                window.getComputedStyle(document.querySelector('h1')).fontFamily : null
                        },
                        textContent: extractTextContent(),
                        element_count: document.querySelectorAll('*').length,
                        forms: Array.from(document.querySelectorAll('form')).map(form => ({
                            action: form.action,
                            method: form.method,
                            fields: Array.from(form.querySelectorAll('input, textarea, select')).length
                        })).slice(0, 5)
                    };
                }
            """)
        except Exception as e:
            logger.warning(f"Enhanced data extraction failed: {e}")
            return {}

    async def _extract_css_styles(self, page):
        """Extract CSS information"""
        try:
            return await page.evaluate("""
                () => {
                    const styleSheets = [];
                    const inlineStyles = [];
                    let rulesCount = 0;

                    // Extract external stylesheets
                    for (let sheet of document.styleSheets) {
                        try {
                            if (sheet.href) {
                                styleSheets.push({
                                    href: sheet.href,
                                    rules: sheet.cssRules ? sheet.cssRules.length : 0
                                });
                            }
                            
                            if (sheet.cssRules) {
                                rulesCount += sheet.cssRules.length;
                            }
                        } catch (e) {
                            // Cross-origin stylesheet access blocked
                        }
                    }

                    // Extract inline styles
                    const elementsWithStyles = document.querySelectorAll('[style]');
                    elementsWithStyles.forEach(el => {
                        inlineStyles.push({
                            tag: el.tagName.toLowerCase(),
                            style: el.style.cssText,
                            className: el.className
                        });
                    });

                    return {
                        external_stylesheets: styleSheets,
                        inline_styles: inlineStyles.slice(0, 20),
                        rules_count: rulesCount,
                        custom_properties: Array.from(document.documentElement.style).filter(prop => prop.startsWith('--'))
                    };
                }
            """)
        except Exception as e:
            logger.warning(f"CSS extraction failed: {e}")
            return {"rules_count": 0}

class LLMCloner:
    def __init__(self):
        self.openai_client = openai_client
    
    async def clone_website(self, scraped_data: Dict[str, Any], model: str = "gpt-4o", 
                          include_responsive: bool = True, include_interactions: bool = True,
                          style_approach: str = "embedded") -> str:
        """Clone website using GPT-4 Vision with enhanced prompting"""
        try:
            if not self.openai_client:
                raise HTTPException(status_code=500, detail="OpenAI client not initialized")
            
            # Build comprehensive context
            context = self._build_comprehensive_context(scraped_data)
            
            # Create enhanced system prompt
            system_prompt = self._create_enhanced_system_prompt(include_responsive, include_interactions, style_approach)
            
            # Prepare message content
            message_content = [
                {
                    "type": "text",
                    "text": f"{system_prompt}\n\nWebsite Analysis:\n{context}\n\nPlease recreate this website as a complete HTML file with embedded CSS and any necessary JavaScript:"
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
            
            # Call OpenAI API with better parameters
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": message_content
                }],
                max_tokens=4000,
                temperature=0.05,  # Lower temperature for more consistent output
                top_p=0.9
            )
            
            html_content = response.choices[0].message.content
            
            # Enhanced HTML cleaning and validation
            html_content = self._clean_and_validate_html(html_content)
            
            return html_content
            
        except Exception as e:
            logger.error(f"LLM cloning failed: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"AI cloning failed: {str(e)}")
    
    def _create_enhanced_system_prompt(self, include_responsive: bool, include_interactions: bool, style_approach: str) -> str:
        """Create a comprehensive system prompt"""
        prompt = """You are an expert web developer specializing in pixel-perfect website recreation. Your task is to create a complete, self-contained HTML file that exactly replicates the provided website.

CRITICAL REQUIREMENTS:
1. **Complete HTML Structure**: Create a full HTML document with DOCTYPE, head, and body
2. **Embedded CSS**: All styles must be in a <style> tag within <head> - NO external stylesheets
3. **Self-contained**: The file must work independently when opened in any browser
4. **Pixel-perfect recreation**: Match colors, fonts, spacing, and layout exactly
5. **Semantic HTML**: Use proper HTML5 semantic elements (header, nav, main, section, footer)

TECHNICAL SPECIFICATIONS:"""

        if include_responsive:
            prompt += """
6. **Responsive Design**: Implement mobile-first responsive design with appropriate breakpoints
7. **Flexible Layout**: Use CSS Grid and Flexbox for modern, flexible layouts"""

        if include_interactions:
            prompt += """
8. **Interactive Elements**: Add hover effects, transitions, and basic JavaScript interactions
9. **Form Functionality**: Make forms functional with basic validation"""

        if style_approach == "embedded":
            prompt += """
10. **Style Organization**: Organize CSS with clear sections: reset, typography, layout, components, utilities"""

        prompt += """

LAYOUT ANALYSIS:
- Carefully analyze the screenshot for exact spacing, colors, and typography
- Pay attention to navigation structure, content hierarchy, and footer design
- Replicate any visual effects, shadows, gradients, or animations
- Ensure proper font choices and text styling

OUTPUT FORMAT:
Provide ONLY the complete HTML code - no explanations, no markdown code blocks, just the raw HTML that can be saved as a .html file and opened directly in a browser."""

        return prompt

    def _build_comprehensive_context(self, scraped_data: Dict[str, Any]) -> str:
        """Build detailed context for AI model"""
        try:
            context_parts = []
            
            # Basic info
            context_parts.append(f"URL: {scraped_data.get('url', 'N/A')}")
            context_parts.append(f"Title: {scraped_data.get('title', 'N/A')}")
            
            enhanced_data = scraped_data.get('enhanced_data', {})
            
            # Meta information
            meta = enhanced_data.get('meta', {})
            if meta.get('description'):
                context_parts.append(f"Description: {meta['description']}")
            
            # Structure analysis
            structure = enhanced_data.get('structure', {})
            structure_info = []
            if structure.get('hasHeader'): structure_info.append("Header")
            if structure.get('hasNav'): structure_info.append("Navigation")
            if structure.get('hasMain'): structure_info.append("Main Content")
            if structure.get('hasSidebar'): structure_info.append("Sidebar")
            if structure.get('hasFooter'): structure_info.append("Footer")
            
            if structure_info:
                context_parts.append(f"Layout Sections: {', '.join(structure_info)}")
            
            # Typography and colors
            colors = enhanced_data.get('colors', {})
            if colors:
                context_parts.append(f"Color Scheme - Background: {colors.get('background', 'N/A')}, Text: {colors.get('text', 'N/A')}")
            
            typography = enhanced_data.get('typography', {})
            if typography:
                context_parts.append(f"Typography - Body: {typography.get('bodyFont', 'N/A')}, Size: {typography.get('bodySize', 'N/A')}")
            
            # Content structure
            headings = enhanced_data.get('headings', {})
            if headings.get('h1'):
                h1_texts = [h['text'] for h in headings['h1'][:3]]
                context_parts.append(f"Main Headings: {', '.join(h1_texts)}")
            
            if headings.get('h2'):
                h2_texts = [h['text'] for h in headings['h2'][:5]]
                context_parts.append(f"Subheadings: {', '.join(h2_texts)}")
            
            # Images
            images = enhanced_data.get('images', [])
            if images:
                context_parts.append(f"Images Found: {len(images)} images")
                img_info = []
                for img in images[:5]:
                    if img.get('alt'):
                        img_info.append(f"'{img['alt']}'")
                if img_info:
                    context_parts.append(f"Image Descriptions: {', '.join(img_info)}")
            
            # Links and navigation
            links = enhanced_data.get('links', [])
            if links:
                nav_links = [link['text'] for link in links[:10] if link.get('text')]
                if nav_links:
                    context_parts.append(f"Navigation Links: {', '.join(nav_links)}")
            
            # Text content sample
            text_content = enhanced_data.get('textContent', [])
            if text_content:
                sample_texts = [t['text'][:100] for t in text_content[:3] if t.get('text')]
                if sample_texts:
                    context_parts.append(f"Sample Content: {' | '.join(sample_texts)}")
            
            # Technical stats
            stats = scraped_data.get('stats', {})
            context_parts.append(f"Page Stats - Elements: {stats.get('dom_elements', 0)}, Images: {stats.get('images_found', 0)}, CSS Rules: {stats.get('css_rules_found', 0)}")
            
            return "\n".join(context_parts)
        except Exception as e:
            logger.warning(f"Context building failed: {e}")
            return f"Basic website analysis for {scraped_data.get('url', 'unknown URL')}"
    
    def _clean_and_validate_html(self, html_content: str) -> str:
        """Clean and validate HTML response"""
        try:
            # Remove markdown formatting
            if "```html" in html_content:
                html_match = re.search(r'```html\s*(.*?)\s*```', html_content, re.DOTALL)
                if html_match:
                    html_content = html_match.group(1)
            elif "```" in html_content:
                html_match = re.search(r'```\s*(.*?)\s*```', html_content, re.DOTALL)
                if html_match:
                    html_content = html_match.group(1)
            
            # Clean up any extra text before/after HTML
            html_start = html_content.find('<!DOCTYPE html>')
            if html_start == -1:
                html_start = html_content.find('<html')
            if html_start == -1:
                html_start = 0
            
            html_end = html_content.rfind('</html>')
            if html_end != -1:
                html_end += 7
                html_content = html_content[html_start:html_end]
            else:
                html_content = html_content[html_start:]
            
            # Add DOCTYPE if missing
            if not html_content.strip().startswith('<!DOCTYPE'):
                html_content = '<!DOCTYPE html>\n' + html_content
            
            # Basic validation - ensure html and body tags exist
            if '<html' not in html_content:
                html_content = html_content.replace('<!DOCTYPE html>', '<!DOCTYPE html>\n<html lang="en">')
                html_content += '\n</html>'
            
            if '<body' not in html_content and '</body>' not in html_content:
                # Wrap content in body tags if they're missing
                head_end = html_content.find('</head>')
                if head_end != -1:
                    before_body = html_content[:head_end + 7]
                    after_head = html_content[head_end + 7:]
                    html_content = before_body + '\n<body>\n' + after_head + '\n</body>'
            
            return html_content.strip()
        except Exception as e:
            logger.warning(f"HTML cleaning failed: {e}")
            return html_content

# Initialize services
scraper = WebScraper()
cloner = LLMCloner()

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

@app.post("/scrape")
async def scrape_website(request: ScrapeRequest):
    """Scrape website with enhanced data extraction"""
    try:
        logger.info(f"Scraping request for: {request.url}")
        result = await scraper.scrape_website(request)
        logger.info(f"Successfully scraped {request.url}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in scrape endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clone")
async def clone_website(request: CloneRequest):
    """Clone website using AI with enhanced features"""
    try:
        logger.info(f"Cloning request with model: {request.model}")
        
        if request.model not in SUPPORTED_MODELS:
            raise HTTPException(status_code=400, detail=f"Unsupported model: {request.model}")
        
        html_content = await cloner.clone_website(
            request.scraped_data, 
            request.model,
            request.include_responsive,
            request.include_interactions,
            request.style_approach
        )
        
        logger.info("Cloning completed successfully")
        
        return {
            "status": "success",
            "model_used": request.model,
            "html_content": html_content,
            "processing_info": {
                "context_length": len(str(request.scraped_data)),
                "has_screenshot": bool(request.scraped_data.get("screenshot")),
                "images_processed": len(request.scraped_data.get("enhanced_data", {}).get("images", [])),
                "responsive": request.include_responsive,
                "interactive": request.include_interactions
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in clone endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scrape-and-clone")
async def scrape_and_clone(request: ScrapeRequest):
    """Enhanced combined scrape and clone operation"""
    try:
        logger.info(f"Starting enhanced combined operation for {request.url}")
        
        # Scrape the website with enhanced data
        scraped_data = await scraper.scrape_website(request)
        
        # Clone with AI using enhanced prompting
        html_content = await cloner.clone_website(
            scraped_data, 
            "gpt-4o",
            include_responsive=True,
            include_interactions=True,
            style_approach="embedded"
        )
        
        logger.info(f"Enhanced combined operation completed for {request.url}")
        
        return {
            "status": "success",
            "url": request.url,
            "scraped_data": scraped_data,
            "html_content": html_content,
            "enhanced_features": {
                "responsive_design": True,
                "interactive_elements": True,
                "embedded_styles": True,
                "semantic_html": True
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in enhanced combined endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "3.1.0",
        "supported_models": SUPPORTED_MODELS,
        "features": {
            "enhanced_scraping": True,
            "css_extraction": True,
            "responsive_cloning": True,
            "interactive_elements": True,
            "semantic_html": True
        },
        "openai_configured": bool(os.getenv("OPENAI_API_KEY"))
    }

@app.get("/")
async def root():
    """Enhanced root endpoint"""
    return {
        "message": "Enhanced Website Cloning API v3.1",
        "version": "3.1.0",
        "description": "AI-powered website cloning with advanced scraping and enhanced HTML generation",
        "endpoints": {
            "scrape": "POST /scrape - Enhanced website data extraction",
            "clone": "POST /clone - AI-powered HTML generation with advanced features",
            "scrape_and_clone": "POST /scrape-and-clone - Complete cloning pipeline",
            "health": "GET /health - Comprehensive health check"
        },
        "features": [
            "Enhanced data extraction with CSS analysis",
            "Improved AI prompting for better results",
            "Responsive design generation",
            "Interactive element recreation",
            "Semantic HTML structure",
            "Embedded styling approach"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)