const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

// Get the URL from command line arguments
const url = process.argv[2];
if (!url) {
  console.error('Please provide a URL as an argument');
  process.exit(1);
}

// Set up paths
const dataDir = path.join(__dirname, '../data');
const logsPath = path.join(dataDir, 'network_logs.json');
const errorLogPath = path.join(dataDir, 'puppeteer_error.log');
const screenshotPath = path.join(dataDir, 'screenshot.png');

// Function to log errors
const logError = (message) => {
  const timestamp = new Date().toISOString();
  const logMessage = `${timestamp} - ${message}\n`;
  fs.appendFileSync(errorLogPath, logMessage);
  console.error(logMessage.trim());
};

(async () => {
  try {
    // Make sure data directory exists
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }

    console.log(`Starting analysis of ${url}`);
    
    // Launch browser
    const browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    // Create a new page
    const page = await browser.newPage();
    
    // Enable request interception
    await page.setRequestInterception(true);
    
    // Track all network activity
    const networkRequests = [];
    
    // Handle requests
    page.on('request', request => {
      const requestData = {
        url: request.url(),
        method: request.method(),
        resourceType: request.resourceType(),
        headers: request.headers(),
        timestamp: Date.now()
      };
      
      networkRequests.push(requestData);
      request.continue();
    });
    
    // Handle responses
    page.on('response', async response => {
      const request = response.request();
      const url = request.url();
      
      try {
        // Find the corresponding request
        const requestEntry = networkRequests.find(req => req.url === url);
        if (requestEntry) {
          requestEntry.status_code = response.status();
          requestEntry.response_headers = await response.headers();
          requestEntry.response_time = Date.now() - requestEntry.timestamp;
          
          // Try to get content type
          const contentType = response.headers()['content-type'];
          if (contentType) {
            requestEntry.content_type = contentType;
          }
        }
      } catch (error) {
        logError(`Error processing response for ${url}: ${error.message}`);
      }
    });
    
    // Navigate to the URL
    console.log(`Navigating to ${url}`);
    await page.goto(url, {
      waitUntil: 'networkidle2',
      timeout: 60000
    });
    
    // Take a screenshot
    await page.screenshot({ path: screenshotPath, fullPage: true });
    
    // Wait a bit for any additional requests to complete
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Save collected network logs
    fs.writeFileSync(logsPath, JSON.stringify(networkRequests, null, 2));
    console.log(`Saved ${networkRequests.length} network requests to ${logsPath}`);
    
    // Close browser
    await browser.close();
    
    console.log('Analysis complete');
  } catch (error) {
    logError(`Error analyzing ${url}: ${error.message}`);
    logError(error.stack);
    process.exit(1);
  }
})();