// pages/index.tsx or app/page.tsx (depending on your Next.js version)
'use client';

import React, { useState } from 'react';
import {
  Globe,
  Download,
  Eye,
  AlertCircle,
  CheckCircle,
  Loader2,
  Copy,
  ExternalLink,
} from 'lucide-react';
import Head from 'next/head';

interface ScrapedData {
  url: string;
  title: string;
  screenshot?: string;
  structure: {
    h1: string;
    h2: string;
    navigation: boolean;
    footer: boolean;
    sidebar: boolean;
  };
  assets: {
    images: Array<{
      src: string;
      alt: string;
      width: number;
      height: number;
    }>;
  };
  stats: {
    images_found: number;
    has_screenshot: boolean;
    css_rules: number;
    dom_elements: number;
  };
  timestamp: string;
  status: string;
}

interface CloneResult {
  status: string;
  model_used: string;
  html_content: string;
  timestamp: string;
  processing_info: {
    context_length: number;
    has_screenshot: boolean;
    images_processed: number;
  };
}

export default function WebsiteCloner() {
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [scrapedData, setScrapedData] = useState<ScrapedData | null>(null);
  const [cloneResult, setCloneResult] = useState<CloneResult | null>(null);
  const [error, setError] = useState('');
  const [previewUrl, setPreviewUrl] = useState('');
  const [currentStep, setCurrentStep] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  // Advanced options
  const [viewportWidth, setViewportWidth] = useState(1280);
  const [viewportHeight, setViewportHeight] = useState(720);
  const [waitTime, setWaitTime] = useState(8000);

  const validateUrl = (inputUrl: string): boolean => {
    try {
      const urlObj = new URL(inputUrl);
      return urlObj.protocol === 'http:' || urlObj.protocol === 'https:';
    } catch {
      return false;
    }
  };

  const addHttpsIfNeeded = (inputUrl: string): string => {
    if (!inputUrl.startsWith('http://') && !inputUrl.startsWith('https://')) {
      return 'https://' + inputUrl;
    }
    return inputUrl;
  };

  const executeCloning = async () => {
    if (!url.trim()) {
      setError('Please enter a website URL');
      return;
    }

    const processedUrl = addHttpsIfNeeded(url.trim());

    if (!validateUrl(processedUrl)) {
      setError('Please enter a valid URL (e.g., https://example.com)');
      return;
    }

    setIsLoading(true);
    setError('');
    setScrapedData(null);
    setCloneResult(null);
    setPreviewUrl('');

    try {
      // Step 1: Enhanced scraping
      setCurrentStep(
        '🔍 Analyzing website structure and capturing screenshots...'
      );

      const scrapeResponse = await fetch('http://localhost:8000/scrape', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: processedUrl,
          capture_screenshot: true,
          viewport_width: viewportWidth,
          viewport_height: viewportHeight,
          wait_time: waitTime,
        }),
      });

      if (!scrapeResponse.ok) {
        const errorData = await scrapeResponse.json();
        throw new Error(errorData.detail || 'Website scraping failed');
      }

      const scraped = await scrapeResponse.json();
      setScrapedData(scraped);

      // Step 2: AI-powered cloning
      setCurrentStep('🤖 AI analyzing design and generating HTML clone...');

      const cloneResponse = await fetch('http://localhost:8000/clone', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'gpt-4o', // ✅ Changed from 'gpt-4-vision-preview'
          include_responsive: true,
          include_interactions: true,
          scraped_data: scraped,
        }),
      });

      if (!cloneResponse.ok) {
        const errorData = await cloneResponse.json();
        throw new Error(errorData.detail || 'AI cloning failed');
      }

      const cloneData = await cloneResponse.json();
      setCloneResult(cloneData);

      if (cloneData.html_content) {
        // Create preview URL
        const blob = new Blob([cloneData.html_content], { type: 'text/html' });
        const previewUrl = URL.createObjectURL(blob);
        setPreviewUrl(previewUrl);
      }

      setCurrentStep('✅ Website cloning completed successfully!');
      setTimeout(() => setCurrentStep(''), 3000);
    } catch (error) {
      console.error('Cloning error:', error);
      setError(`Failed to clone website: ${(error as Error).message}`);
      setCurrentStep('');
    } finally {
      setIsLoading(false);
    }
  };

  const downloadHtml = () => {
    if (!cloneResult?.html_content) return;

    const blob = new Blob([cloneResult.html_content], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `cloned-${new Date().getTime()}.html`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const copyToClipboard = async () => {
    if (!cloneResult?.html_content) return;

    try {
      await navigator.clipboard.writeText(cloneResult.html_content);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  const openPreview = () => {
    if (previewUrl) {
      window.open(previewUrl, '_blank');
    }
  };

  const resetForm = () => {
    setUrl('');
    setScrapedData(null);
    setCloneResult(null);
    setError('');
    setPreviewUrl('');
    setCurrentStep('');
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
  };

  return (
    <>
      <Head>
        <title>AI Website Cloner - Clone Any Website Instantly</title>
        <meta
          name="description"
          content="Clone any website instantly using AI-powered analysis and HTML generation"
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
        {/* Background Pattern */}
        <div className="absolute inset-0 bg-grid-pattern opacity-5"></div>

        <div className="relative max-w-6xl mx-auto px-4 py-8">
          {/* Header */}
          <div className="text-center mb-12">
            <div className="flex items-center justify-center mb-6">
              <div className="relative">
                <Globe className="w-16 h-16 text-indigo-600 animate-pulse" />
                <div className="absolute -top-1 -right-1 w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-xs font-bold">AI</span>
                </div>
              </div>
            </div>
            <h1 className="text-5xl font-bold text-gray-800 mb-4">
              AI Website Cloner
            </h1>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Transform any website into clean, responsive HTML using advanced
              AI analysis. Just paste a URL and watch the magic happen.
            </p>
          </div>

          {/* Main Input Card */}
          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8 mb-8">
            <div className="space-y-6">
              {/* URL Input */}
              <div>
                <label
                  htmlFor="url"
                  className="block text-sm font-semibold text-gray-700 mb-3"
                >
                  Website URL
                </label>
                <div className="flex flex-col lg:flex-row gap-4">
                  <div className="flex-1">
                    <input
                      id="url"
                      type="text"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      placeholder="Enter website URL (e.g., example.com)"
                      className="w-full px-4 py-4 border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all text-lg"
                      disabled={isLoading}
                      onKeyPress={(e) =>
                        e.key === 'Enter' && !isLoading && executeCloning()
                      }
                    />
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={executeCloning}
                      disabled={isLoading || !url.trim()}
                      className="px-8 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl hover:from-indigo-700 hover:to-purple-700 disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed flex items-center justify-center font-semibold transition-all shadow-lg hover:shadow-xl"
                    >
                      {isLoading ? (
                        <>
                          <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                          Cloning...
                        </>
                      ) : (
                        <>
                          <Globe className="w-5 h-5 mr-2" />
                          Clone Website
                        </>
                      )}
                    </button>
                    {(scrapedData || cloneResult) && (
                      <button
                        onClick={resetForm}
                        className="px-6 py-4 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-all"
                      >
                        Reset
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Advanced Options */}
              <div>
                <button
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                >
                  {showAdvanced ? '▼' : '▶'} Advanced Options
                </button>

                {showAdvanced && (
                  <div className="mt-4 p-4 bg-gray-50 rounded-lg grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Viewport Width
                      </label>
                      <input
                        type="number"
                        value={viewportWidth}
                        onChange={(e) =>
                          setViewportWidth(Number(e.target.value))
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                        min="800"
                        max="1920"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Viewport Height
                      </label>
                      <input
                        type="number"
                        value={viewportHeight}
                        onChange={(e) =>
                          setViewportHeight(Number(e.target.value))
                        }
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                        min="600"
                        max="1080"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Wait Time (ms)
                      </label>
                      <input
                        type="number"
                        value={waitTime}
                        onChange={(e) => setWaitTime(Number(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
                        min="3000"
                        max="15000"
                        step="1000"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Loading Status */}
          {isLoading && currentStep && (
            <div className="bg-blue-50 border-2 border-blue-200 rounded-xl p-6 mb-8">
              <div className="flex items-center">
                <Loader2 className="w-6 h-6 text-blue-600 animate-spin mr-4" />
                <div>
                  <p className="text-blue-800 font-semibold text-lg">
                    {currentStep}
                  </p>
                  <p className="text-blue-600 text-sm mt-1">
                    This process typically takes 30-90 seconds depending on
                    website complexity
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="bg-red-50 border-2 border-red-200 rounded-xl p-6 mb-8">
              <div className="flex items-start">
                <AlertCircle className="w-6 h-6 text-red-600 mr-4 mt-0.5" />
                <div>
                  <p className="text-red-800 font-semibold text-lg">
                    Oops! Something went wrong
                  </p>
                  <p className="text-red-700 mt-1">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Results */}
          {scrapedData && cloneResult && (
            <div className="space-y-8">
              {/* Success Header */}
              <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-200 rounded-xl p-6">
                <div className="flex items-center">
                  <CheckCircle className="w-8 h-8 text-green-600 mr-4" />
                  <div>
                    <h2 className="text-2xl font-bold text-green-800">
                      Website Successfully Cloned! 🎉
                    </h2>
                    <p className="text-green-700 mt-1">
                      Your website has been analyzed and converted to clean HTML
                    </p>
                  </div>
                </div>
              </div>

              {/* Stats Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="text-2xl font-bold text-indigo-600">
                    {scrapedData.stats.images_found}
                  </div>
                  <div className="text-sm text-gray-600">Images Found</div>
                </div>
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="text-2xl font-bold text-purple-600">
                    {scrapedData.stats.dom_elements}
                  </div>
                  <div className="text-sm text-gray-600">DOM Elements</div>
                </div>
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="text-2xl font-bold text-blue-600">
                    {Math.round(cloneResult.html_content.length / 1024)}KB
                  </div>
                  <div className="text-sm text-gray-600">Generated HTML</div>
                </div>
                <div className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="text-2xl font-bold text-green-600">
                    {cloneResult.processing_info.images_processed}
                  </div>
                  <div className="text-sm text-gray-600">Images Processed</div>
                </div>
              </div>

              {/* Website Info */}
              <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-6">
                <h3 className="text-xl font-bold text-gray-800 mb-4">
                  Original Website Details
                </h3>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">
                      <strong>URL:</strong>
                    </p>
                    <p className="text-gray-800 break-all">{scrapedData.url}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 mb-1">
                      <strong>Title:</strong>
                    </p>
                    <p className="text-gray-800">{scrapedData.title}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 mb-1">
                      <strong>Main Heading:</strong>
                    </p>
                    <p className="text-gray-800">
                      {scrapedData.structure.h1 || 'Not found'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600 mb-1">
                      <strong>Features:</strong>
                    </p>
                    <div className="flex gap-2 flex-wrap">
                      {scrapedData.structure.navigation && (
                        <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
                          Navigation
                        </span>
                      )}
                      {scrapedData.structure.footer && (
                        <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                          Footer
                        </span>
                      )}
                      {scrapedData.structure.sidebar && (
                        <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs rounded">
                          Sidebar
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-6">
                <h3 className="text-xl font-bold text-gray-800 mb-4">
                  Your Cloned Website
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <button
                    onClick={openPreview}
                    className="px-6 py-4 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-lg hover:from-green-600 hover:to-emerald-600 flex items-center justify-center font-semibold transition-all shadow-lg hover:shadow-xl"
                  >
                    <Eye className="w-5 h-5 mr-2" />
                    Live Preview
                  </button>
                  <button
                    onClick={downloadHtml}
                    className="px-6 py-4 bg-gradient-to-r from-blue-500 to-indigo-500 text-white rounded-lg hover:from-blue-600 hover:to-indigo-600 flex items-center justify-center font-semibold transition-all shadow-lg hover:shadow-xl"
                  >
                    <Download className="w-5 h-5 mr-2" />
                    Download HTML
                  </button>
                  <button
                    onClick={copyToClipboard}
                    className={`px-6 py-4 rounded-lg flex items-center justify-center font-semibold transition-all shadow-lg hover:shadow-xl ${
                      copySuccess
                        ? 'bg-green-500 text-white'
                        : 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600'
                    }`}
                  >
                    <Copy className="w-5 h-5 mr-2" />
                    {copySuccess ? 'Copied!' : 'Copy Code'}
                  </button>
                </div>

                {/* HTML Preview */}
                <div className="mt-6">
                  <details className="bg-gray-50 rounded-lg border">
                    <summary className="p-4 font-medium text-gray-800 cursor-pointer hover:bg-gray-100 rounded-lg flex items-center justify-between">
                      <span>
                        View Generated HTML Code (
                        {cloneResult.html_content.length.toLocaleString()}{' '}
                        characters)
                      </span>
                      <ExternalLink className="w-4 h-4" />
                    </summary>
                    <div className="p-4 border-t border-gray-200">
                      <pre className="text-xs bg-white p-4 rounded border overflow-auto max-h-96 text-gray-700 whitespace-pre-wrap">
                        {cloneResult.html_content}
                      </pre>
                    </div>
                  </details>
                </div>
              </div>
            </div>
          )}

          {/* Features Section - Only show when not processing */}
          {!isLoading && !scrapedData && (
            <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-8">
              <h3 className="text-2xl font-bold text-gray-800 text-center mb-8">
                How It Works
              </h3>
              <div className="grid md:grid-cols-3 gap-8">
                <div className="text-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-indigo-100 to-indigo-200 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span className="text-2xl font-bold text-indigo-600">
                      1
                    </span>
                  </div>
                  <h4 className="text-lg font-semibold mb-3">
                    Smart Website Analysis
                  </h4>
                  <p className="text-gray-600">
                    Our advanced scraper captures screenshots, extracts images,
                    analyzes CSS, and maps the DOM structure
                  </p>
                </div>
                <div className="text-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-purple-100 to-purple-200 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span className="text-2xl font-bold text-purple-600">
                      2
                    </span>
                  </div>
                  <h4 className="text-lg font-semibold mb-3">
                    AI-Powered Design Recognition
                  </h4>
                  <p className="text-gray-600">
                    GPT-4 Vision analyzes the visual design, layout patterns,
                    and component structure to understand the website
                  </p>
                </div>
                <div className="text-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-green-100 to-green-200 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span className="text-2xl font-bold text-green-600">3</span>
                  </div>
                  <h4 className="text-lg font-semibold mb-3">
                    Clean HTML Generation
                  </h4>
                  <p className="text-gray-600">
                    Generates responsive, semantic HTML with embedded CSS,
                    animations, and proper accessibility features
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
